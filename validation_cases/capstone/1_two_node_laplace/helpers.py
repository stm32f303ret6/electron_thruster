#!/usr/bin/env python3
"""Stage-local geometry and configuration for capstone.two_node_laplace.

The chipsat capstone's conducting-can Geometry (transcribed verbatim from
capstone/2_floating_body/helpers.py, which transcribed electron_contactor geometry.py: the EB
implicit function and the piecewise two-node potential string), plus a slim
config: this stage solves the VACUUM Laplace problem for that geometry with
BODY and CATHODE pinned at fixed potentials -- no plasma, no beam, no pump.

The geometry numbers in config.yaml are IDENTICAL to the capstone's; the
cross-stage check ``two_node_matches_capstone_geometry`` hash-compares the
frozen geometry+dx of both stages, so what is validated here is exactly what
the capstone runs.

No pywarpx/PICMI, matplotlib, or openPMD here, and no run/analysis lifecycle
(that is ladder_contract).
"""

from __future__ import annotations

import functools
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

import numpy as np
import yaml
from scipy import constants as scc

STAGE_ID = "capstone.two_node_laplace"

EPS0 = scc.epsilon_0

_SCHEMA: dict[str, tuple[str, ...]] = {
    "electrical": ("phi_body", "cathode_offset"),
    "geometry": ("r_probe", "wall_thickness", "lid_thickness",
                 "floor_thickness", "z_bot", "z_top", "r_slit", "r_cathode",
                 "emit_radius"),
    "domain": ("rmax", "aspect", "zmargin_lo", "zmargin_hi"),
    "numerics": ("dx", "dt", "max_steps"),
}


class ConfigError(ValueError):
    """A malformed or physically invalid stage configuration."""


def _reject_unknown(raw: Mapping[str, Any]) -> None:
    allowed_top = set(_SCHEMA) | {"stage_id"}
    unknown = set(raw) - allowed_top
    if unknown:
        raise ConfigError(f"unknown top-level config keys: {sorted(unknown)}")
    for section, keys in _SCHEMA.items():
        if section not in raw:
            raise ConfigError(f"missing config section '{section}'")
        block = raw[section]
        if not isinstance(block, Mapping):
            raise ConfigError(f"config section '{section}' must be a mapping")
        unknown = set(block) - set(keys)
        if unknown:
            raise ConfigError(f"unknown keys in '{section}': {sorted(unknown)}")
        missing = set(keys) - set(block)
        if missing:
            raise ConfigError(f"missing keys in '{section}': {sorted(missing)}")


def _f(section: Mapping[str, Any], key: str) -> float:
    value = float(section[key])
    if not math.isfinite(value):
        raise ConfigError(f"non-finite value for '{key}': {section[key]!r}")
    return value


def _i(section: Mapping[str, Any], key: str) -> int:
    return int(section[key])


# ======================================================================
# geometry (capstone/2_floating_body/helpers.py, transcribed verbatim)
# ======================================================================

def _disk(zlo, zhi, R):
    """Solid where z in [zlo,zhi] and r < R (a filled disk / cylinder)."""
    return f"min(z-({zlo:.10g}), min(({zhi:.10g})-z, ({R:.10g})-x))"


def _ring(zlo, zhi, rin, rout):
    """Solid where z in [zlo,zhi] and r in [rin,rout] (an annulus / tube)."""
    return (f"min(z-({zlo:.10g}), min(({zhi:.10g})-z, "
            f"min(x-({rin:.10g}), ({rout:.10g})-x)))")


class Geometry:
    """The conducting can and its two electrical nodes, as WarpX EB expressions.

    Identical to the capstone's Geometry (see capstone/2_floating_body/helpers.py for the full
    labelled cross-section).  Two nodes only:
      BODY    = wall + perforated lid + floor annulus
      CATHODE = central disk on the floor
    separated by a >= 2*dx insulating gap so no EB cut-cell straddles both.
    """

    def __init__(self, *, dx: float, r_probe: float, wall_thickness: float,
                 lid_thickness: float, floor_thickness: float, z_bot: float,
                 z_top: float, r_slit: float, r_cathode: float,
                 emit_radius: float):
        self.dx = dx
        self.pad = 0.5 * dx
        self.r_p = r_probe
        self.tw = wall_thickness
        self.z_bot = z_bot
        self.z_top = z_top
        self.tfloor = floor_thickness
        self.tlid = lid_thickness
        self.we = emit_radius
        self.r_slit = r_slit
        self.r_cath = r_cathode

        # derived
        self.r_in = self.r_p - self.tw                 # inner cavity radius
        self.zfloort = self.z_bot + self.tfloor        # cathode (floor top) surface
        self.zlidb = self.z_top - self.tlid            # lid bottom
        self.r_cath_out = self.r_cath + 2.0 * dx       # BODY floor-annulus inner radius
        self.z_emit = self.zfloort + 2.0 * dx
        self.d_gap = self.zlidb - self.zfloort         # cathode top -> lid front

        self._validate()

    def _validate(self) -> None:
        dx = self.dx

        def req(cond: bool, msg: str) -> None:
            if not cond:
                raise ConfigError(f"geometry: {msg}")

        req(self.we < self.r_slit, "emission spot must clear the lid hole")
        req(self.r_slit < self.r_p - 2 * dx,
            "lid ring has no metal (r_slit too close to wall)")
        req(self.z_emit < self.zlidb,
            "cathode must be below the lid (open exhaust path, beam +z)")
        req(self.we < self.r_cath, "emission spot must fit on the cathode disk")
        req(self.r_cath > 2 * dx, "cathode disk not resolved")
        req((self.r_cath_out - self.r_cath) >= 2 * dx - 1e-12,
            "cathode/body-floor gap < 2 cells")
        req(self.r_cath_out < self.r_p - 2 * dx, "body floor annulus has no metal")

    # ---- solid region (implicit function): union (max) of all conductors ----
    def implicit_function(self) -> str:
        regions = [
            _ring(self.z_bot, self.z_top, self.r_in, self.r_p),           # can wall (BODY)
            _disk(self.z_bot, self.zfloort, self.r_cath),                 # CATHODE disk
            _ring(self.z_bot, self.zfloort, self.r_cath_out, self.r_p),   # BODY floor annulus
            _ring(self.zlidb, self.z_top, self.r_slit, self.r_p),         # perforated lid (BODY)
        ]
        return functools.reduce(lambda acc, r: f"max({acc}, {r})", regions)

    # ---- boolean membership expressions (0/1) for each node ----
    def _body_bools(self) -> str:
        p = self.pad
        wall = (f"(z>{self.z_bot-p:.10g})*(z<{self.z_top+p:.10g})"
                f"*(x>{self.r_in-p:.10g})*(x<{self.r_p+p:.10g})")
        floor_ann = (f"(z>{self.z_bot-p:.10g})*(z<{self.zfloort+p:.10g})"
                     f"*(x>{self.r_cath_out-p:.10g})*(x<{self.r_p+p:.10g})")
        lid = (f"(z>{self.zlidb-p:.10g})*(z<{self.z_top+p:.10g})"
               f"*(x>{self.r_slit-p:.10g})*(x<{self.r_p+p:.10g})")
        return f"({wall}+{floor_ann}+{lid})"

    def _cathode_bools(self) -> str:
        p = self.pad
        return (f"((z>{self.z_bot-p:.10g})*(z<{self.zfloort+p:.10g})"
                f"*(x<{self.r_cath+p:.10g}))")

    def potential_string(self, phi_body: float, phi_cathode: float) -> str:
        """Piecewise EB Dirichlet potential: BODY -> phi_body, CATHODE -> phi_cathode."""
        return (f"(({self._body_bools()})>0.5)*({phi_body:.10g}) + "
                f"(({self._cathode_bools()})>0.5)*({phi_cathode:.10g})")

    # ---- exact (unpadded) node classification for field analysis ----
    def node_masks(self, r, z) -> dict:
        """Boolean masks over a (r, z) meshgrid of field sample points:
        which points lie inside each metal region (nominal bounds, no padding).
        Returns dict(body=..., cathode=...); everything else is vacuum."""
        r = np.asarray(r)
        z = np.asarray(z)
        wall = ((z >= self.z_bot) & (z <= self.z_top)
                & (r >= self.r_in) & (r <= self.r_p))
        zfloor = (z >= self.z_bot) & (z <= self.zfloort)
        cathode = zfloor & (r <= self.r_cath)
        floor_ann = zfloor & (r >= self.r_cath_out) & (r <= self.r_p)
        lid = ((z >= self.zlidb) & (z <= self.z_top)
               & (r >= self.r_slit) & (r <= self.r_p))
        return dict(body=(wall | floor_ann | lid), cathode=cathode)

    def describe(self) -> str:
        return (f"can r<{self.r_p*1e3:.1f} mm, z in [{self.z_bot*1e3:.1f},"
                f"{self.z_top*1e3:.1f}] mm; cathode disk r<{self.r_cath*1e3:.2f} mm, "
                f"lid hole r<{self.r_slit*1e3:.2f} mm; accel gap {self.d_gap*1e3:.2f} mm")


# ======================================================================
# config
# ======================================================================

@dataclass(frozen=True)
class Config:
    """Typed view of the two-node Laplace config plus derived grid numbers.

    The grid derivation (snap-to-8 cells) is transcribed from the capstone's
    Config so both stages produce the identical 200x440 mesh from the same
    geometry/domain numbers.
    """
    stage_id: str
    phi_body: float
    cathode_offset: float
    # geometry (raw numbers; the Geometry object is built on demand)
    r_probe: float
    wall_thickness: float
    lid_thickness: float
    floor_thickness: float
    z_bot: float
    z_top: float
    r_slit: float
    r_cathode: float
    emit_radius: float
    # domain
    rmax_requested: float
    aspect: float
    zmargin_lo: float
    zmargin_hi: float
    # numerics
    dx: float
    dt: float
    max_steps: int
    scenario: Any = None  # single-run stage (uniform stage API)

    @property
    def phi_cathode(self) -> float:
        """The cathode node potential: body + supply offset (the capstone's
        cathode_value() with the supply on)."""
        return self.phi_body + self.cathode_offset

    def geometry(self) -> Geometry:
        return Geometry(
            dx=self.dx, r_probe=self.r_probe,
            wall_thickness=self.wall_thickness, lid_thickness=self.lid_thickness,
            floor_thickness=self.floor_thickness, z_bot=self.z_bot,
            z_top=self.z_top, r_slit=self.r_slit, r_cathode=self.r_cathode,
            emit_radius=self.emit_radius)

    # ---- grid (capstone Config, transcribed: snap up to multiples of 8) ----
    @property
    def nr(self) -> int:
        return int(math.ceil(self.rmax_requested / self.dx / 8.0)) * 8

    @property
    def rmax(self) -> float:
        return self.nr * self.dx

    @property
    def _zbounds_raw(self) -> tuple[float, float]:
        zspan_can = self.z_top - self.z_bot
        zmargin = max(self.zmargin_lo,
                      (self.aspect * self.rmax_requested - zspan_can) / 2.0)
        zmin = self.z_bot - zmargin
        zmax = self.z_top + max(zmargin, self.zmargin_hi)
        return zmin, zmax

    @property
    def nz(self) -> int:
        zmin, zmax = self._zbounds_raw
        return int(math.ceil((zmax - zmin) / self.dx / 8.0)) * 8

    @property
    def zmin(self) -> float:
        return self._zbounds_raw[0]

    @property
    def zmax(self) -> float:
        return self.zmin + self.nz * self.dx

    # ---- serialization ----
    def effective_config(self) -> dict:
        return {
            "stage_id": self.stage_id,
            "electrical": {
                "phi_body": self.phi_body,
                "cathode_offset": self.cathode_offset,
            },
            "geometry": {
                "r_probe": self.r_probe, "wall_thickness": self.wall_thickness,
                "lid_thickness": self.lid_thickness,
                "floor_thickness": self.floor_thickness,
                "z_bot": self.z_bot, "z_top": self.z_top,
                "r_slit": self.r_slit, "r_cathode": self.r_cathode,
                "emit_radius": self.emit_radius,
            },
            "domain": {
                "rmax": self.rmax_requested, "aspect": self.aspect,
                "zmargin_lo": self.zmargin_lo, "zmargin_hi": self.zmargin_hi,
            },
            "numerics": {
                "dx": self.dx, "dt": self.dt, "max_steps": self.max_steps,
            },
        }

    def validate(self) -> None:
        if self.cathode_offset >= 0.0:
            raise ConfigError(
                "electrical.cathode_offset must be negative (the cathode is the "
                f"most-negative node); got {self.cathode_offset:+g} V")
        if self.z_top <= self.z_bot:
            raise ConfigError("geometry.z_top must be above z_bot (inverted can)")
        if self.dx <= 0 or self.dt <= 0:
            raise ConfigError("numerics.dx and dt must be positive")
        if self.max_steps < 2:
            raise ConfigError(
                "numerics.max_steps must be >= 2 (the rewrite-idempotency gate "
                "compares the first and last two-node solves)")
        self.geometry()                 # runs the geometric invariants
        if self.r_probe >= self.rmax - 2 * self.dx:
            raise ConfigError("can radius reaches the radial boundary")
        if not (self.zmin < self.z_bot and self.z_top < self.zmax):
            raise ConfigError("can is not inside the axial domain")


def load_config(path: Path | str, scenario: str | None = None) -> Config:
    """Parse, coerce, and validate a config.yaml (or a frozen config_used.yaml)."""
    if scenario is not None:
        raise ConfigError("capstone.two_node_laplace has no scenarios")
    raw = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    if not isinstance(raw, Mapping):
        raise ConfigError(f"config {path} is not a mapping")
    _reject_unknown(raw)
    ele, geo = raw["electrical"], raw["geometry"]
    dom, num = raw["domain"], raw["numerics"]
    stage_id = str(raw.get("stage_id", ""))
    if stage_id != STAGE_ID:
        raise ConfigError(f"stage_id {stage_id!r} != expected {STAGE_ID!r}")
    cfg = Config(
        stage_id=stage_id,
        phi_body=_f(ele, "phi_body"),
        cathode_offset=_f(ele, "cathode_offset"),
        r_probe=_f(geo, "r_probe"),
        wall_thickness=_f(geo, "wall_thickness"),
        lid_thickness=_f(geo, "lid_thickness"),
        floor_thickness=_f(geo, "floor_thickness"),
        z_bot=_f(geo, "z_bot"), z_top=_f(geo, "z_top"),
        r_slit=_f(geo, "r_slit"), r_cathode=_f(geo, "r_cathode"),
        emit_radius=_f(geo, "emit_radius"),
        rmax_requested=_f(dom, "rmax"), aspect=_f(dom, "aspect"),
        zmargin_lo=_f(dom, "zmargin_lo"), zmargin_hi=_f(dom, "zmargin_hi"),
        dx=_f(num, "dx"), dt=_f(num, "dt"), max_steps=_i(num, "max_steps"),
    )
    cfg.validate()
    return cfg
