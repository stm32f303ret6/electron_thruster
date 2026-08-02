#!/usr/bin/env python3
"""Stage-local physics and configuration for capstone.mission_envelope.

The typed config, the plasma/gun derivations and the conducting-can Geometry are
DUPLICATED VERBATIM from ``capstone/2_chipsat_thruster/helpers.py`` -- the same
deck, run at two mission operating points instead of one.  The duplication is
deliberate: this repository has no shared physics framework, and a rung that
imported another rung's deck could not be audited on its own.

What is new here, and only here:

  * a TWO-FORM config.  The live ``config.yaml`` lists every scenario and needs
    one selected; a run's frozen ``config_used.yaml`` carries a single resolved
    scenario inline.  ``load_config`` reads either (the pattern from
    ``electron_gun/2_electron_gun``).
  * ``law_anchor`` + per-scenario ``predicted``/``provenance``: the frozen design
    model and its pre-registered predictions.  They ride in the hashed run config
    so a run cannot be re-interpreted against a different model afterwards.

No pywarpx/PICMI, matplotlib, or openPMD here, and no run/analysis lifecycle
(that is ladder_contract).  numpy-free too: the geometry masks work on any
array-like via operator broadcasting.
"""

from __future__ import annotations

import functools
import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping, Optional

import yaml
from scipy import constants as scc

STAGE_ID = "capstone.mission_envelope"

BEAM, AMB_E, AMB_I = "beam_electrons", "ambient_electrons", "ambient_ions"

E = scc.e
ME = scc.m_e
EPS0 = scc.epsilon_0
KB = scc.k

#: Sections whose keys are identical in both config forms.
_SHARED_SCHEMA: dict[str, tuple[str, ...]] = {
    "electrical": ("phi_body_init", "t_supply"),
    "beam": ("t_on", "rms_velocity", "flux_correction"),
    "geometry": ("r_probe", "wall_thickness", "lid_thickness",
                 "floor_thickness", "z_bot", "z_top", "r_slit", "r_cathode",
                 "emit_radius"),
    "reservoir": ("enabled", "frac", "every"),
    "domain": ("rmax", "aspect", "zmargin_lo", "zmargin_hi", "edge_phi_max"),
    "numerics": ("dx", "dt", "ppc", "ppc_beam"),
    "run": ("t_end", "max_steps", "diag_period_frac", "phi_ceiling",
            "choke_sustain"),
    "compute": ("gpu_arena_bytes",),
}

#: The frozen design constants.  Every one must be present -- a stage that ran
#: with a partial model could not have its predictions reproduced.
_LAW_ANCHOR_KEYS = ("k", "ke_ledger", "f_esc", "beta", "area_m2",
                    "capacitance_F", "anchored_to", "metrics_sha256",
                    "laws_sha256")

_SCENARIO_KEYS = ("name", "plasma", "cathode_offset", "i_beam",
                  "drag_target_N", "predicted", "provenance", "reported", "note")
_PLASMA_KEYS = ("n0", "Te_K", "Ti_K", "ion_mass_me")
_PREDICTED_KEYS = ("phi_body_V", "f_beam_nN", "exhaust_ke_eV", "binding")
_PROVENANCE_REQUIRED = ("orbit_case", "csv_sha256", "timestamp_utc", "row_index")

# Research knobs that exist in electron_contactor but are NOT migrated (the
# stage is the float200 deck at mission operating points); reject them with a
# pointer.
_NOT_MIGRATED = ("probe", "shroud", "fields", "checkpoint")


class ConfigError(ValueError):
    """A malformed or physically invalid stage configuration."""


def _reject_unknown(raw: Mapping[str, Any], extra_top: set[str],
                    extra_section: Mapping[str, tuple[str, ...]] = {}) -> None:
    for group in _NOT_MIGRATED:
        if group in raw:
            raise ConfigError(
                f"config group '{group}' is not migrated -- research variants "
                f"(probe/shroud/Bz/ram-drift/restart) live in the "
                f"electron_contactor repo, not the validation ladder")
    allowed_top = set(_SHARED_SCHEMA) | {"stage_id", "law_anchor"} | extra_top
    unknown = set(raw) - allowed_top
    if unknown:
        raise ConfigError(f"unknown top-level config keys: {sorted(unknown)}")
    for section, keys in _SHARED_SCHEMA.items():
        if section not in raw:
            raise ConfigError(f"missing config section '{section}'")
        block = raw[section]
        if not isinstance(block, Mapping):
            raise ConfigError(f"config section '{section}' must be a mapping")
        allowed = set(keys) | set(extra_section.get(section, ()))
        unknown = set(block) - allowed
        if unknown:
            raise ConfigError(f"unknown keys in '{section}': {sorted(unknown)}")
        missing = set(keys) - set(block)
        if missing:
            raise ConfigError(f"missing keys in '{section}': {sorted(missing)}")


def _check_law_anchor(raw: Mapping[str, Any]) -> dict:
    """The frozen design model: present, complete, and physically sane.

    This is the only place the stage learns what the model believes.  A missing
    or malformed anchor is a hard error rather than a default, because a run
    whose predictions cannot be reproduced is not evidence about a model.
    """
    anchor = raw.get("law_anchor")
    if not isinstance(anchor, Mapping):
        raise ConfigError(
            "missing 'law_anchor' block -- this stage validates a design model, "
            "so the constants it was run against must be frozen with the run")
    missing = set(_LAW_ANCHOR_KEYS) - set(anchor)
    if missing:
        raise ConfigError(f"law_anchor is missing {sorted(missing)}")
    unknown = set(anchor) - set(_LAW_ANCHOR_KEYS)
    if unknown:
        raise ConfigError(f"unknown law_anchor keys: {sorted(unknown)}")
    out = {}
    for key in ("k", "ke_ledger", "f_esc", "beta", "area_m2", "capacitance_F"):
        value = _f(anchor, key)
        if value <= 0.0:
            raise ConfigError(f"law_anchor.{key} must be positive, got {value}")
        out[key] = value
    if not 0.0 < out["f_esc"] <= 1.0:
        raise ConfigError(f"law_anchor.f_esc must be in (0, 1], got {out['f_esc']}")
    for key in ("anchored_to", "metrics_sha256", "laws_sha256"):
        text = str(anchor[key]).strip()
        if not text:
            raise ConfigError(f"law_anchor.{key} must not be empty")
        out[key] = text
    if len(out["metrics_sha256"]) != 64 or len(out["laws_sha256"]) != 64:
        raise ConfigError("law_anchor sha256 fields must be 64 hex characters")
    return out


def _check_scenario(sc: Mapping[str, Any]) -> None:
    """One scenario entry: complete plasma, a pre-registration, and provenance."""
    unknown = set(sc) - set(_SCENARIO_KEYS)
    if unknown:
        raise ConfigError(f"unknown scenario keys: {sorted(unknown)}")
    for key in ("name", "plasma", "cathode_offset", "i_beam", "drag_target_N",
                "predicted", "provenance"):
        if key not in sc:
            raise ConfigError(f"scenario {sc.get('name', '?')!r} is missing '{key}'")
    plasma = sc["plasma"]
    if not isinstance(plasma, Mapping) or set(plasma) != set(_PLASMA_KEYS):
        raise ConfigError(
            f"scenario {sc['name']!r} plasma must have exactly {list(_PLASMA_KEYS)}")
    pred = sc["predicted"]
    if not isinstance(pred, Mapping) or set(pred) != set(_PREDICTED_KEYS):
        raise ConfigError(
            f"scenario {sc['name']!r} predicted must have exactly "
            f"{list(_PREDICTED_KEYS)} -- the pre-registration is not optional")
    prov = sc["provenance"]
    if not isinstance(prov, Mapping):
        raise ConfigError(f"scenario {sc['name']!r} provenance must be a mapping")
    missing = set(_PROVENANCE_REQUIRED) - set(prov)
    if missing:
        raise ConfigError(
            f"scenario {sc['name']!r} provenance is missing {sorted(missing)} -- "
            f"a mission row that cannot be traced back to a CSV row is invented, "
            f"not measured")


def _f(section: Mapping[str, Any], key: str) -> float:
    value = float(section[key])
    if not math.isfinite(value):
        raise ConfigError(f"non-finite value for '{key}': {section[key]!r}")
    return value


def _i(section: Mapping[str, Any], key: str) -> int:
    return int(section[key])


# ======================================================================
# geometry (electron_contactor geometry.py, transcribed)
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

    Cross-section (RZ; the EB/flux parsers use x->r, z axial; metres):

          r=0 (axis)                         r_probe
      z_top    +---hole---+------------------+   <- lid (BODY): washer r in [r_slit, r_probe]
               | r_slit   |                  |
               |          ^ beam (+z)        |   <- can wall (BODY)
      z_bot    +--CATHODE--+ gap +-----------+   <- floor: cathode disk r < r_cathode
               |  phi_body + offset | BODY   |      + body floor annulus r > r_cathode+2dx,
               +-----------+----+---+--------+      separated by a >=2-cell insulating gap.

    Two nodes only:
      BODY    = wall + perforated lid + floor annulus -> phi_body (floats)
      CATHODE = central emitting disk                 -> phi_body + cathode_offset

    Float and fixed metal are inset by >= 2*dx so no EB cut-cell straddles two
    potentials.
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
        # Emit 2 cells ABOVE the cathode top: launching on the EB face itself puts
        # macroparticles in the covered cut-cell, where WarpX scrapes them at once.
        self.z_emit = self.zfloort + 2.0 * dx
        # accelerating gap (no anode): cathode top -> lid front
        self.d_gap = self.zlidb - self.zfloort

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

    # ---- classify scraped (r,z) EB hits into electrode regions ----
    def regions(self, r, z) -> dict:
        """A scraped particle sits up to ~1 cell outside the nominal metal, so pad
        every bound by tol = dx.  The >=2*dx BODY/CATHODE separation keeps the masks
        disjoint even after padding.  Returns dict of boolean masks."""
        t = self.dx
        wall = ((z > self.z_bot - t) & (z < self.z_top + t)
                & (r > self.r_in - t) & (r < self.r_p + t))
        zfloor = (z > self.z_bot - t) & (z < self.zfloort + t)
        cathode = zfloor & (r < self.r_cath + t)                             # emitter disk
        floor_ann = zfloor & (r > self.r_cath_out - t) & (r < self.r_p + t)  # BODY annulus
        lid = ((z > self.zlidb - t) & (z < self.z_top + t)
               & (r > self.r_slit - t) & (r < self.r_p + t))
        return dict(wall=wall, floor_ann=floor_ann, cathode=cathode, lid=lid)

    def describe(self) -> str:
        return (f"can r<{self.r_p*1e3:.1f} mm, z in [{self.z_bot*1e3:.1f},"
                f"{self.z_top*1e3:.1f}] mm; cathode disk r<{self.r_cath*1e3:.2f} mm, "
                f"lid hole r<{self.r_slit*1e3:.2f} mm; emit r<{self.we*1e3:.2f} mm; "
                f"accel gap {self.d_gap*1e3:.2f} mm")


# ======================================================================
# config
# ======================================================================

@dataclass(frozen=True)
class Config:
    """Typed config for ONE resolved scenario, plus every derived numeric.

    The physics derivations are transcribed from capstone.floating_body (which
    took them from electron_contactor config.py); max_steps is floored to a
    multiple of diag_period so the final dump lands exactly on the last
    iteration.  What is added here is the scenario identity, the frozen design
    constants, and the pre-registered predictions.
    """
    stage_id: str
    # electrical
    cathode_offset: float
    phi_body_init: float
    t_supply: float
    # beam
    i_beam: float
    t_on: float
    rms_velocity: float
    flux_correction: float
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
    # plasma
    n0: float
    Te_K: float
    Ti_K: float
    ion_mass_me: float
    # reservoir
    reservoir_enabled: bool
    reservoir_frac: float
    reservoir_every: int
    # domain
    rmax_requested: float
    aspect: float
    zmargin_lo: float
    zmargin_hi: float
    edge_phi_max: float
    # numerics
    dx: float
    dt_explicit: Optional[float]
    ppc: int
    ppc_beam: int
    # run
    t_end: float
    max_steps_cap: int
    diag_period_frac: int
    phi_ceiling: Optional[float]
    choke_sustain: float
    # compute
    gpu_arena_bytes: int
    # scenario identity + the frozen design model
    scenario: Optional[str] = None
    drag_target_N: float = 0.0
    law_anchor: Mapping[str, Any] = field(default_factory=dict)
    predicted: Mapping[str, Any] = field(default_factory=dict)
    provenance: Mapping[str, Any] = field(default_factory=dict)
    reported: Mapping[str, Any] = field(default_factory=dict)
    note: Optional[str] = None
    _scenarios: tuple[dict, ...] = ()   # the full study table, when known

    # ---- plasma derivations (contactor _derive_plasma) ----
    @property
    def m_ion(self) -> float:
        return self.ion_mass_me * ME

    @property
    def vth_e(self) -> float:
        return math.sqrt(KB * self.Te_K / ME)

    @property
    def vth_i(self) -> float:
        return math.sqrt(KB * self.Ti_K / self.m_ion)

    @property
    def flux_e(self) -> float:
        """One-sided Maxwellian face flux n*vth/sqrt(2*pi) (== n*vbar/4)."""
        return self.n0 * self.vth_e / math.sqrt(2.0 * math.pi)

    @property
    def flux_i(self) -> float:
        return self.n0 * self.vth_i / math.sqrt(2.0 * math.pi)

    @property
    def lamD(self) -> float:
        return math.sqrt(EPS0 * KB * self.Te_K / (self.n0 * E**2))

    @property
    def wpe(self) -> float:
        return math.sqrt(self.n0 * E**2 / (ME * EPS0))

    @property
    def kTe_eV(self) -> float:
        return KB * self.Te_K / E

    @property
    def V_GAP(self) -> float:
        """The gun gap: the cathode tracks the body at a fixed offset, so the
        accelerating voltage is |offset| regardless of where the body floats."""
        return abs(self.cathode_offset)

    # ---- geometry ----
    def geometry(self) -> Geometry:
        return Geometry(
            dx=self.dx, r_probe=self.r_probe,
            wall_thickness=self.wall_thickness, lid_thickness=self.lid_thickness,
            floor_thickness=self.floor_thickness, z_bot=self.z_bot,
            z_top=self.z_top, r_slit=self.r_slit, r_cathode=self.r_cathode,
            emit_radius=self.emit_radius)

    # ---- beam / gun derivations (contactor finalize) ----
    @property
    def d_gap(self) -> float:
        return self.geometry().d_gap

    @property
    def I_CL(self) -> float:
        """Planar Child-Langmuir scale for the accel gap over the spot (a rough
        SCALE for a non-planar geometry; printed, never gated -- plan C8)."""
        j = (4.0 / 9.0) * EPS0 * math.sqrt(2.0 * E / ME) \
            * self.V_GAP**1.5 / self.d_gap**2
        return j * math.pi * self.emit_radius**2

    @property
    def flux0(self) -> float:
        return self.i_beam / (math.pi * self.emit_radius**2 * E)

    @property
    def flux0_used(self) -> float:
        return self.flux0 / self.flux_correction

    @property
    def v_beam(self) -> float:
        return math.sqrt(2.0 * E * self.V_GAP / ME)

    @property
    def vmax(self) -> float:
        return self.v_beam + 4.0 * self.vth_e

    @property
    def dt(self) -> float:
        return self.dt_explicit if self.dt_explicit else 0.3 * self.dx / self.vmax

    @property
    def cfl(self) -> float:
        return self.dt * self.vmax / self.dx

    # ---- grid (contactor finalize; snap up to multiples of 8 cells) ----
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

    @property
    def R_res(self) -> float:
        """Inner radius of the reservoir recycle shell."""
        return self.r_probe + self.reservoir_frac * (self.rmax - self.r_probe)

    # ---- step count (deviation: floored to a diag_period multiple) ----
    @property
    def _max_steps_raw(self) -> int:
        return min(int(math.ceil(self.t_end / self.dt)), self.max_steps_cap)

    @property
    def diag_period(self) -> int:
        return max(1, self._max_steps_raw // self.diag_period_frac)

    @property
    def max_steps(self) -> int:
        floored = (self._max_steps_raw // self.diag_period) * self.diag_period
        return max(self.diag_period, floored)

    # ---- the frozen design model ----
    @property
    def scenario_names(self) -> tuple[str, ...]:
        return tuple(str(s["name"]) for s in self._scenarios)

    def model_prediction(self) -> dict:
        """Recompute the predictions from the FROZEN constants and this run's
        own (V, I, n_e, Te).

        The analysis compares this against the frozen ``predicted:`` block. They
        must agree to round-off: a disagreement means this stage's opmodel.py
        and design_sims/opmodel.py have drifted apart, which would make the
        pre-registration describe a model neither side is running.
        """
        import opmodel
        a = self.law_anchor
        return opmodel.predict(
            n_e=self.n0, Te_K=self.Te_K, v_drive=self.V_GAP, i_beam_A=self.i_beam,
            k=float(a["k"]), ke_ledger=float(a["ke_ledger"]),
            f_esc=float(a["f_esc"]), beta=float(a["beta"]),
            area_m2=float(a["area_m2"]))

    def predicted_settle_time_s(self) -> float:
        import opmodel
        return opmodel.settle_time_s(float(self.predicted["phi_body_V"]),
                                     self.i_beam,
                                     float(self.law_anchor["capacitance_F"]))

    # ---- serialization ----
    def effective_config(self) -> dict:
        """The physics dict frozen to config_used.yaml and hashed.  dt and
        max_steps are stored RESOLVED so the frozen config is complete; the
        loader honors them and round-trips identically."""
        out = {
            "stage_id": self.stage_id,
            "scenario": self.scenario,
            "electrical": {
                "cathode_offset": self.cathode_offset,
                "phi_body_init": self.phi_body_init,
                "t_supply": self.t_supply,
            },
            "beam": {
                "i_beam": self.i_beam, "t_on": self.t_on,
                "rms_velocity": self.rms_velocity,
                "flux_correction": self.flux_correction,
            },
            "geometry": {
                "r_probe": self.r_probe, "wall_thickness": self.wall_thickness,
                "lid_thickness": self.lid_thickness,
                "floor_thickness": self.floor_thickness,
                "z_bot": self.z_bot, "z_top": self.z_top,
                "r_slit": self.r_slit, "r_cathode": self.r_cathode,
                "emit_radius": self.emit_radius,
            },
            "plasma": {
                "n0": self.n0, "Te_K": self.Te_K, "Ti_K": self.Ti_K,
                "ion_mass_me": self.ion_mass_me,
            },
            "reservoir": {
                "enabled": self.reservoir_enabled,
                "frac": self.reservoir_frac, "every": self.reservoir_every,
            },
            "domain": {
                "rmax": self.rmax_requested, "aspect": self.aspect,
                "zmargin_lo": self.zmargin_lo, "zmargin_hi": self.zmargin_hi,
                "edge_phi_max": self.edge_phi_max,
            },
            "numerics": {
                "dx": self.dx, "dt": self.dt, "ppc": self.ppc,
                "ppc_beam": self.ppc_beam,
            },
            "run": {
                "t_end": self.t_end, "max_steps": self.max_steps,
                "diag_period_frac": self.diag_period_frac,
                "phi_ceiling": self.phi_ceiling,
                "choke_sustain": self.choke_sustain,
            },
            "compute": {"gpu_arena_bytes": self.gpu_arena_bytes},
            "law_anchor": dict(self.law_anchor),
            "drag_target_N": self.drag_target_N,
            "predicted": dict(self.predicted),
            "provenance": dict(self.provenance),
        }
        if self.reported:
            out["reported"] = dict(self.reported)
        if self.note:
            out["note"] = self.note
        return out

    def study_config(self) -> Optional[dict]:
        """The full two-scenario study (shared physics + every scenario), hashed
        into ``study_sha256`` so a cohort cannot mix configuration generations.

        None when this Config came from a frozen single-scenario file.  Every
        per-scenario quantity is stripped out of the shared part -- including the
        DERIVED ones (dt from the CFL, max_steps from dt), which differ between
        scenarios purely because their electron temperatures do.
        """
        if not self._scenarios:
            return None
        shared = self.effective_config()
        for key in ("scenario", "plasma", "drag_target_N", "predicted",
                    "provenance", "reported", "note"):
            shared.pop(key, None)
        shared["electrical"].pop("cathode_offset", None)
        shared["beam"].pop("i_beam", None)
        shared["numerics"].pop("dt", None)
        shared["run"].pop("max_steps", None)
        shared["scenarios"] = [_canonical_scenario(s) for s in self._scenarios]
        return shared

    def validate_smoke(self) -> None:
        """Every invariant EXCEPT the settle-time requirement.

        A smoke run is deliberately too short for the float to settle -- that is
        precisely why it is declared calibration rather than evidence.  Nothing
        else is relaxed.
        """
        self.validate(require_settled=False)

    def validate(self, require_settled: bool = True) -> None:
        """The contactor's physics/numerics invariants, as explicit errors."""
        if self.cathode_offset >= 0.0:
            raise ConfigError(
                "electrical.cathode_offset must be negative (the cathode is the "
                f"most-negative node); got {self.cathode_offset:+g} V")
        if self.t_on < self.t_supply:
            raise ConfigError(
                f"beam.t_on ({self.t_on:g}) must be >= electrical.t_supply "
                f"({self.t_supply:g}): the supply must be live before the gun fires")
        if self.z_top <= self.z_bot:
            raise ConfigError("geometry.z_top must be above z_bot (inverted can)")
        if self.i_beam <= 0:
            raise ConfigError("beam.i_beam must be positive")
        if self.flux_correction <= 0:
            raise ConfigError("beam.flux_correction must be positive")
        if self.n0 <= 0 or self.Te_K <= 0 or self.Ti_K <= 0:
            raise ConfigError("plasma density/temperatures must be positive")
        if self.dx >= self.lamD:
            raise ConfigError(
                f"numerics.dx ({self.dx:g}) must resolve lambda_D ({self.lamD:g} m)")
        if not (0.0 < self.reservoir_frac < 1.0):
            raise ConfigError("reservoir.frac must be in (0, 1)")
        if self.reservoir_every < 1:
            raise ConfigError("reservoir.every must be >= 1")
        if self.ppc < 1 or self.ppc_beam < 1:
            raise ConfigError("ppc / ppc_beam must be >= 1")
        if self.t_end <= self.t_on:
            raise ConfigError("run.t_end must exceed beam.t_on (gun never fires)")
        if self.phi_ceiling is not None and self.phi_ceiling <= 0:
            raise ConfigError("run.phi_ceiling must be positive or null")
        # grid/timestep invariants (contactor _validate_grid)
        if self.cfl >= 0.5:
            raise ConfigError(f"dt too large: CFL={self.cfl:.2f} (must be < 0.5)")
        if self.wpe * self.dt >= 0.2:
            raise ConfigError(
                f"plasma frequency not resolved: wpe*dt={self.wpe*self.dt:.3f}")
        if self.dx > self.r_slit / 5.0:
            raise ConfigError(
                f"lid hole not resolved: dx={self.dx:g} > r_slit/5={self.r_slit/5:g}")
        geom = self.geometry()          # runs the geometric invariants
        if geom.d_gap < 7.0 * self.dx:
            raise ConfigError(
                f"accelerating gap {geom.d_gap*1e3:.2f} mm is < 7 cells: "
                f"under-resolved gaps give spurious beam loss (Q5 guard)")
        # the can must sit inside the (snapped) domain
        if self.r_probe >= self.rmax - 2 * self.dx:
            raise ConfigError("can radius reaches the radial boundary")
        if not (self.zmin < self.z_bot and self.z_top < self.zmax):
            raise ConfigError("can is not inside the axial domain")
        if self.R_res >= self.rmax - 2 * self.dx:
            raise ConfigError("reservoir shell has no room inside rmax")
        # ---- this stage's own invariants ---------------------------------
        if self.scenario is None:
            raise ConfigError("every run of this stage belongs to a scenario")
        # Only meaningful on the STUDY form, where a human sets the cap. On a
        # frozen config the cap IS the resolved (diag-floored) step count, so it
        # is legitimately a few steps below ceil(t_end/dt).
        if self._scenarios and math.ceil(self.t_end / self.dt) > self.max_steps_cap:
            raise ConfigError(
                f"run.max_steps cap ({self.max_steps_cap}) truncates scenario "
                f"{self.scenario!r}: t_end={self.t_end*1e9:.0f} ns needs "
                f"{math.ceil(self.t_end / self.dt)} steps at dt={self.dt:.3e} s. "
                f"A silently shortened run would measure a transient.")
        if require_settled and self.t_end < 3.0 * self.predicted_settle_time_s():
            raise ConfigError(
                f"run.t_end ({self.t_end*1e9:.0f} ns) is under 3 settle times "
                f"(tau={self.predicted_settle_time_s()*1e9:.0f} ns) for scenario "
                f"{self.scenario!r}: the float would still be climbing at the end "
                f"and no gate on it would mean anything")


def _canonical_scenario(sc: Mapping[str, Any]) -> dict:
    """One scenario reduced to the values that define it, for the study hash.

    Comments, notes and reported-only diagnostics are excluded: they must be
    editable without invalidating a cohort, while anything the deck consumes or
    the gates test must not be.
    """
    return {
        "name": str(sc["name"]),
        "plasma": {k: float(sc["plasma"][k]) for k in _PLASMA_KEYS},
        "cathode_offset": float(sc["cathode_offset"]),
        "i_beam": float(sc["i_beam"]),
        "drag_target_N": float(sc["drag_target_N"]),
        "predicted": {
            "phi_body_V": float(sc["predicted"]["phi_body_V"]),
            "f_beam_nN": float(sc["predicted"]["f_beam_nN"]),
            "exhaust_ke_eV": float(sc["predicted"]["exhaust_ke_eV"]),
            "binding": str(sc["predicted"]["binding"]),
        },
        "provenance": {k: sc["provenance"][k] for k in _PROVENANCE_REQUIRED},
    }


def scenario_names(path: Path | str) -> list[str]:
    """The scenario names declared in the study config, in order."""
    raw = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    return [str(s["name"]) for s in (raw.get("scenarios") or [])]


def _build(raw: Mapping[str, Any], sc: Mapping[str, Any],
           scenarios: tuple[dict, ...]) -> Config:
    ele, bea, geo = raw["electrical"], raw["beam"], raw["geometry"]
    res, dom = raw["reservoir"], raw["domain"]
    num, run, com = raw["numerics"], raw["run"], raw["compute"]
    pla = sc["plasma"]
    stage_id = str(raw.get("stage_id", ""))
    if stage_id != STAGE_ID:
        raise ConfigError(f"stage_id {stage_id!r} != expected {STAGE_ID!r}")
    dt_raw = num.get("dt")
    phi_ceiling_raw = run.get("phi_ceiling")
    cfg = Config(
        stage_id=stage_id,
        cathode_offset=_f(sc, "cathode_offset"),
        phi_body_init=_f(ele, "phi_body_init"),
        t_supply=_f(ele, "t_supply"),
        i_beam=_f(sc, "i_beam"), t_on=_f(bea, "t_on"),
        rms_velocity=_f(bea, "rms_velocity"),
        flux_correction=_f(bea, "flux_correction"),
        r_probe=_f(geo, "r_probe"),
        wall_thickness=_f(geo, "wall_thickness"),
        lid_thickness=_f(geo, "lid_thickness"),
        floor_thickness=_f(geo, "floor_thickness"),
        z_bot=_f(geo, "z_bot"), z_top=_f(geo, "z_top"),
        r_slit=_f(geo, "r_slit"), r_cathode=_f(geo, "r_cathode"),
        emit_radius=_f(geo, "emit_radius"),
        n0=_f(pla, "n0"), Te_K=_f(pla, "Te_K"), Ti_K=_f(pla, "Ti_K"),
        ion_mass_me=_f(pla, "ion_mass_me"),
        reservoir_enabled=bool(res["enabled"]),
        reservoir_frac=_f(res, "frac"), reservoir_every=_i(res, "every"),
        rmax_requested=_f(dom, "rmax"), aspect=_f(dom, "aspect"),
        zmargin_lo=_f(dom, "zmargin_lo"), zmargin_hi=_f(dom, "zmargin_hi"),
        edge_phi_max=_f(dom, "edge_phi_max"),
        dx=_f(num, "dx"),
        dt_explicit=(None if dt_raw is None else float(dt_raw)),
        ppc=_i(num, "ppc"), ppc_beam=_i(num, "ppc_beam"),
        t_end=_f(run, "t_end"), max_steps_cap=_i(run, "max_steps"),
        diag_period_frac=_i(run, "diag_period_frac"),
        phi_ceiling=(None if phi_ceiling_raw is None
                     else float(phi_ceiling_raw)),
        choke_sustain=_f(run, "choke_sustain"),
        gpu_arena_bytes=_i(com, "gpu_arena_bytes"),
        scenario=str(sc["name"]),
        drag_target_N=_f(sc, "drag_target_N"),
        law_anchor=_check_law_anchor(raw),
        predicted=dict(sc["predicted"]),
        provenance=dict(sc["provenance"]),
        reported=dict(sc.get("reported") or {}),
        note=(str(sc["note"]) if sc.get("note") else None),
        _scenarios=scenarios,
    )
    cfg.validate()
    return cfg


def load_config(path: Path | str, scenario: str | None = None) -> Config:
    """Load the two-scenario study (needs ``scenario``) or a frozen run config.

    The study form has a ``scenarios`` list and REQUIRES a selection -- there is
    no default scenario, because a run that silently picked one would be
    unattributable.  A frozen ``config_used.yaml`` carries its resolved scenario
    inline and round-trips to an identical Config.
    """
    raw = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    if not isinstance(raw, Mapping):
        raise ConfigError(f"config {path} is not a mapping")

    if "scenarios" in raw:                       # the study
        _reject_unknown(raw, extra_top={"scenarios"})
        table = raw["scenarios"]
        if not isinstance(table, list) or not table:
            raise ConfigError("'scenarios' must be a non-empty list")
        for sc in table:
            if not isinstance(sc, Mapping):
                raise ConfigError("each scenario must be a mapping")
            _check_scenario(sc)
        names = [str(s["name"]) for s in table]
        if len(set(names)) != len(names):
            raise ConfigError(f"duplicate scenario names: {names}")
        if scenario is None:
            raise ConfigError(f"a scenario must be selected; choices: {names}")
        if scenario not in names:
            raise ConfigError(f"unknown scenario {scenario!r}; choices: {names}")
        sc = next(s for s in table if str(s["name"]) == scenario)
        return _build(raw, sc, tuple(table))

    # a frozen, single-scenario run config
    _reject_unknown(raw, extra_top={"scenario", "plasma", "drag_target_N",
                                    "predicted", "provenance", "reported", "note"},
                    extra_section={"electrical": ("cathode_offset",),
                                   "beam": ("i_beam",)})
    frozen = raw.get("scenario")
    if not frozen:
        raise ConfigError("frozen config carries no 'scenario'")
    if scenario is not None and frozen != scenario:
        raise ConfigError(f"requested scenario {scenario!r} != frozen {frozen!r}")
    for key in ("cathode_offset",):
        if key in raw["electrical"]:
            continue
        raise ConfigError(f"frozen config missing electrical.{key}")
    if "i_beam" not in raw["beam"]:
        raise ConfigError("frozen config missing beam.i_beam")
    sc = {
        "name": frozen,
        "plasma": raw["plasma"],
        "cathode_offset": raw["electrical"]["cathode_offset"],
        "i_beam": raw["beam"]["i_beam"],
        "drag_target_N": raw.get("drag_target_N", 0.0),
        "predicted": raw.get("predicted"),
        "provenance": raw.get("provenance"),
        "reported": raw.get("reported"),
        "note": raw.get("note"),
    }
    _check_scenario(sc)
    return _build(raw, sc, ())


def analytic_capacitance(r_probe: float) -> float:
    """Isolated-sphere scale 4*pi*eps0*r_p used as the C-calibration sanity band."""
    return 4.0 * math.pi * EPS0 * r_probe
