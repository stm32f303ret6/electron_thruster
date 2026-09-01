#!/usr/bin/env python3
"""Stage-local physics and configuration for characterization.magnetized_transverse.

The chipsat body of the 200 V anchor (capstone.floating_body) in a Cartesian
3D electrostatic deck with a uniform external magnetic field PERPENDICULAR to
the thrust axis (B = Bx x-hat, thrust along +z): the flight geometry that the
RZ decks cannot represent.  Typed config (the anchor's plasma row and body
carried over; the gun replaced by a prescribed exhaust source on the lid,
see README.md), the derived numerics, and the solid-body Geometry as WarpX
EB expressions.

Multi-scenario source study (the holed-anode convention): the live
config.yaml lists the scenarios (one field strength each); a run's frozen
config_used.yaml carries one resolved scenario.  ``load_config`` reads both.

No pywarpx/PICMI, matplotlib, or openPMD here, and no run/analysis lifecycle
(that is ladder_contract).
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Optional

import yaml
from scipy import constants as scc

STAGE_ID = "characterization.magnetized_transverse"

BEAM, AMB_E, AMB_I = "beam_electrons", "ambient_electrons", "ambient_ions"

E = scc.e
ME = scc.m_e
EPS0 = scc.epsilon_0
KB = scc.k
CC = scc.c

_SCHEMA: dict[str, tuple[str, ...]] = {
    "electrical": ("phi_body_init",),
    "beam": ("i_beam", "t_on", "ke_inject_eV", "emit_radius", "rms_velocity"),
    "geometry": ("r_probe", "z_bot", "z_top"),
    "plasma": ("n0", "Te_K", "Ti_K", "ion_mass_me"),
    "reservoir": ("enabled", "frac", "every"),
    "domain": ("half_x", "half_y", "zmargin_lo", "zmargin_hi", "edge_phi_max"),
    "numerics": ("dx", "dt", "ppc", "ppc_beam"),
    "run": ("t_end", "max_steps", "diag_period_frac", "phi_ceiling",
            "choke_sustain"),
    "compute": ("gpu_arena_bytes",),
}
# Optional keys: absent -> a documented default that reproduces the committed
# baseline byte-for-byte, so frozen config_used.yaml files stay loadable and
# their case hashes stay valid.
_OPTIONAL: dict[str, tuple[str, ...]] = {
    "compute": ("max_grid_size",),   # AMReX box size; None -> the deck's 128
}

# The per-scenario axis.  A source study carries it inside ``scenarios``; a
# frozen config carries it resolved under ``field`` next to ``scenario``.
_SCENARIO_KEYS = ("name", "Bx_T")


class ConfigError(ValueError):
    """A malformed or physically invalid stage configuration."""


def _reject_unknown(raw: Mapping[str, Any]) -> None:
    allowed_top = set(_SCHEMA) | {"stage_id", "scenarios", "scenario", "field"}
    unknown = set(raw) - allowed_top
    if unknown:
        raise ConfigError(f"unknown top-level config keys: {sorted(unknown)}")
    for section, keys in _SCHEMA.items():
        if section not in raw:
            raise ConfigError(f"missing config section '{section}'")
        block = raw[section]
        if not isinstance(block, Mapping):
            raise ConfigError(f"config section '{section}' must be a mapping")
        unknown = set(block) - set(keys) - set(_OPTIONAL.get(section, ()))
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
# geometry: the solid chipsat body (single electrical node)
# ======================================================================

class Geometry:
    """The anchor's can as ONE solid conductor (Ø 2 r_probe, z_bot..z_top).

    The RZ anchor resolves the gun inside the can at dx = 0.15 mm (walls,
    cathode disk, lid hole).  At the millimetre cells this deck needs for a
    3D box the gun is sub-cell, so the body is solid and the escaped beam is a
    prescribed flux source on the lid (README.md: "the instrument").  One
    node, one potential: phi_body.
    """

    def __init__(self, *, dx: float, r_probe: float, z_bot: float,
                 z_top: float, emit_radius: float):
        self.dx = dx
        self.r_p = r_probe
        self.z_bot = z_bot
        self.z_top = z_top
        self.we = emit_radius
        # Emit 2 cells ABOVE the lid: launching on the EB face itself puts
        # macroparticles in the covered cut-cell, where WarpX scrapes them at once.
        self.z_emit = z_top + 2.0 * dx
        self._validate()

    def _validate(self) -> None:
        dx = self.dx

        def req(cond: bool, msg: str) -> None:
            if not cond:
                raise ConfigError(f"geometry: {msg}")

        req(self.z_top > self.z_bot, "z_top must be above z_bot (inverted body)")
        req(self.r_p >= 2.0 * dx, "body radius not resolved (< 2 cells)")
        req((self.z_top - self.z_bot) >= 2.0 * dx, "body height not resolved (< 2 cells)")
        req(self.we < self.r_p, "emission spot must sit on the lid (emit_radius < r_probe)")
        req(self.we >= dx, "emission spot not resolved (emit_radius < 1 cell)")

    # ---- solid region (implicit function; positive inside the metal) ----
    def implicit_function(self) -> str:
        return (f"min(z-({self.z_bot:.10g}), min(({self.z_top:.10g})-z, "
                f"({self.r_p:.10g})-sqrt(x*x+y*y)))")

    def potential_string(self, phi_body: float) -> str:
        """Single-node EB Dirichlet potential (a constant expression)."""
        return f"{phi_body:.10g}"

    def inside(self, x, y, z, tol: float = 0.0):
        """Boolean mask: inside the solid (padded by tol), for tests/classifiers."""
        return ((z > self.z_bot - tol) & (z < self.z_top + tol)
                & ((x * x + y * y) < (self.r_p + tol) ** 2))

    def describe(self) -> str:
        return (f"solid can r<{self.r_p*1e3:.1f} mm, z in [{self.z_bot*1e3:.1f},"
                f"{self.z_top*1e3:.1f}] mm; exhaust source r<{self.we*1e3:.2f} mm "
                f"at z={self.z_emit*1e3:.2f} mm (lid + 2 cells)")


# ======================================================================
# config
# ======================================================================

@dataclass(frozen=True)
class Config:
    """Typed config plus every derived numeric the deck needs."""
    stage_id: str
    scenario: Optional[str]
    # electrical
    phi_body_init: float
    # beam (the escaped exhaust, prescribed at the lid)
    i_beam: float
    t_on: float
    ke_inject_eV: float
    emit_radius: float
    rms_velocity: float
    # geometry
    r_probe: float
    z_bot: float
    z_top: float
    # plasma
    n0: float
    Te_K: float
    Ti_K: float
    ion_mass_me: float
    # the axis: transverse external field (None -> the unmagnetized control)
    Bx_T: Optional[float]
    # reservoir
    reservoir_enabled: bool
    reservoir_frac: float
    reservoir_every: int
    # domain
    half_x: float
    half_y: float
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
    # optional: AMReX max box size (None -> the deck's 128).  The wide-domain
    # follow-up sets 64 so the 59M-particle load sorts in 8 boxes, not one.
    max_grid_size: Optional[int] = None
    _scenarios: tuple[dict, ...] = ()  # full study table, when known

    # ---- plasma derivations (identical to the anchor's) ----
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

    # ---- magnetic derivations ----
    @property
    def omega_ce(self) -> float:
        return 0.0 if self.Bx_T is None else E * abs(self.Bx_T) / ME

    @property
    def r_gyro_beam(self) -> Optional[float]:
        """Exhaust-electron gyroradius at the injection energy."""
        return None if self.Bx_T is None else ME * self.v_inject / (E * abs(self.Bx_T))

    @property
    def r_gyro_thermal_e(self) -> Optional[float]:
        return None if self.Bx_T is None else ME * self.vth_e / (E * abs(self.Bx_T))

    # ---- geometry ----
    def geometry(self) -> Geometry:
        return Geometry(dx=self.dx, r_probe=self.r_probe, z_bot=self.z_bot,
                        z_top=self.z_top, emit_radius=self.emit_radius)

    # ---- beam derivations ----
    @property
    def v_inject(self) -> float:
        """Injection speed for ke_inject_eV (non-relativistic; gamma-1 ~ 3e-4)."""
        return math.sqrt(2.0 * E * self.ke_inject_eV / ME)

    @property
    def flux0(self) -> float:
        """Electron flux over the emission disk that carries i_beam."""
        return self.i_beam / (math.pi * self.emit_radius**2 * E)

    @property
    def vmax(self) -> float:
        return self.v_inject + 4.0 * self.vth_e

    @property
    def dt(self) -> float:
        return self.dt_explicit if self.dt_explicit else 0.3 * self.dx / self.vmax

    @property
    def cfl(self) -> float:
        return self.dt * self.vmax / self.dx

    # ---- grid (snap up to multiples of 8 cells; the box is centred on x=y=0) ----
    @staticmethod
    def _snap8(n_cells: float) -> int:
        return int(math.ceil(n_cells / 8.0)) * 8

    @property
    def nx(self) -> int:
        return self._snap8(2.0 * self.half_x / self.dx)

    @property
    def ny(self) -> int:
        return self._snap8(2.0 * self.half_y / self.dx)

    @property
    def xmax(self) -> float:
        return 0.5 * self.nx * self.dx

    @property
    def ymax(self) -> float:
        return 0.5 * self.ny * self.dx

    @property
    def zmin(self) -> float:
        return self.z_bot - self.zmargin_lo

    @property
    def nz(self) -> int:
        return self._snap8((self.z_top + self.zmargin_hi - self.zmin) / self.dx)

    @property
    def zmax(self) -> float:
        return self.zmin + self.nz * self.dx

    @property
    def n_cells(self) -> int:
        return self.nx * self.ny * self.nz

    # ---- reservoir recycle shell: outside the inner box (frac of each half-extent) ----
    @property
    def inner_box(self) -> tuple[float, float, float, float]:
        """(x_half, y_half, z_lo, z_hi) of the region the reservoir never fills."""
        zc = 0.5 * (self.zmin + self.zmax)
        zh = 0.5 * (self.zmax - self.zmin)
        f = self.reservoir_frac
        return (f * self.xmax, f * self.ymax, zc - f * zh, zc + f * zh)

    # ---- step count (floored to a diag_period multiple, as the anchor does) ----
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

    # ---- serialization ----
    def scenario_names(self) -> tuple[str, ...]:
        return tuple(str(s["name"]) for s in self._scenarios)

    def _shared(self) -> dict:
        return {
            "stage_id": self.stage_id,
            "electrical": {"phi_body_init": self.phi_body_init},
            "beam": {
                "i_beam": self.i_beam, "t_on": self.t_on,
                "ke_inject_eV": self.ke_inject_eV,
                "emit_radius": self.emit_radius,
                "rms_velocity": self.rms_velocity,
            },
            "geometry": {"r_probe": self.r_probe, "z_bot": self.z_bot,
                         "z_top": self.z_top},
            "plasma": {"n0": self.n0, "Te_K": self.Te_K, "Ti_K": self.Ti_K,
                       "ion_mass_me": self.ion_mass_me},
            "reservoir": {"enabled": self.reservoir_enabled,
                          "frac": self.reservoir_frac,
                          "every": self.reservoir_every},
            "domain": {"half_x": self.half_x, "half_y": self.half_y,
                       "zmargin_lo": self.zmargin_lo,
                       "zmargin_hi": self.zmargin_hi,
                       "edge_phi_max": self.edge_phi_max},
            "numerics": {"dx": self.dx, "dt": self.dt, "ppc": self.ppc,
                         "ppc_beam": self.ppc_beam},
            "run": {"t_end": self.t_end, "max_steps": self.max_steps,
                    "diag_period_frac": self.diag_period_frac,
                    "phi_ceiling": self.phi_ceiling,
                    "choke_sustain": self.choke_sustain},
            "compute": {
                "gpu_arena_bytes": self.gpu_arena_bytes,
                # omitted when unset, so baseline case hashes are unchanged
                **({} if self.max_grid_size is None
                   else {"max_grid_size": self.max_grid_size}),
            },
        }

    def effective_config(self) -> dict:
        """The single-scenario physics frozen to config_used.yaml and hashed.
        dt and max_steps are stored RESOLVED so the frozen config is complete;
        the loader honors them and round-trips identically."""
        out = self._shared()
        out["scenario"] = self.scenario
        out["field"] = {"Bx_T": self.Bx_T}
        return out

    def study_config(self) -> Optional[dict]:
        """The full source-study physics (shared + all scenarios), for the
        study SHA-256.  None if this Config was loaded from a frozen scenario."""
        if not self._scenarios:
            return None
        out = self._shared()
        out["scenarios"] = [
            {"name": str(s["name"]),
             "Bx_T": (None if s.get("Bx_T") is None else float(s["Bx_T"]))}
            for s in self._scenarios]
        return out

    def validate(self) -> None:
        """The physics/numerics invariants, as explicit errors."""
        if self.i_beam <= 0:
            raise ConfigError("beam.i_beam must be positive")
        if self.ke_inject_eV <= 0:
            raise ConfigError("beam.ke_inject_eV must be positive")
        if self.rms_velocity < 0:
            raise ConfigError("beam.rms_velocity must be >= 0")
        if self.n0 <= 0 or self.Te_K <= 0 or self.Ti_K <= 0:
            raise ConfigError("plasma density/temperatures must be positive")
        if self.Bx_T is not None:
            if not (0.0 < abs(self.Bx_T) <= 1.0e-2):
                raise ConfigError(
                    f"field.Bx_T ({self.Bx_T:g} T) must be a nonzero field within "
                    "+-10 mT (LEO is ~3e-5 T); the control scenario uses null")
            omega_ce_dt = self.omega_ce * self.dt
            if omega_ce_dt >= 0.2:
                raise ConfigError(
                    f"omega_ce*dt = {omega_ce_dt:.3g} >= 0.2: the Boris push "
                    "under-resolves the gyromotion at this Bx/dt")
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
        if self.max_grid_size is not None and not (8 <= self.max_grid_size <= 1024):
            raise ConfigError("compute.max_grid_size must be in [8, 1024] or null")
        if self.cfl >= 0.5:
            raise ConfigError(f"dt too large: CFL={self.cfl:.2f} (must be < 0.5)")
        if self.wpe * self.dt >= 0.2:
            raise ConfigError(
                f"plasma frequency not resolved: wpe*dt={self.wpe*self.dt:.3f}")
        geom = self.geometry()          # runs the geometric invariants
        dx = self.dx
        if self.r_probe >= min(self.xmax, self.ymax) - 4 * dx:
            raise ConfigError("body reaches the transverse boundaries")
        if not (self.zmin + 2 * dx < self.z_bot and geom.z_emit < self.zmax - 4 * dx):
            raise ConfigError("body/source is not inside the axial domain")
        xh, yh, zlo, zhi = self.inner_box
        if not (self.r_probe < xh - 2 * dx and self.r_probe < yh - 2 * dx
                and zlo + 2 * dx < self.z_bot and geom.z_emit < zhi - 2 * dx):
            raise ConfigError(
                "reservoir shell reaches the body: raise reservoir.frac or the box")


def scenario_names(path: Path | str) -> list[str]:
    """The scenario names declared in a source-study config, in order."""
    raw = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    return [str(s["name"]) for s in (raw.get("scenarios") or [])]


def load_config(path: Path | str, scenario: str | None = None) -> Config:
    """Load a source study (needs ``scenario``) or a frozen scenario config.

    A source study has a ``scenarios`` list and requires ``scenario`` to select
    one; a frozen ``config_used.yaml`` carries the resolved scenario inline
    (``scenario`` + ``field``)."""
    raw = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    if not isinstance(raw, Mapping):
        raise ConfigError(f"config {path} is not a mapping")
    _reject_unknown(raw)
    stage_id = str(raw.get("stage_id", ""))
    if stage_id != STAGE_ID:
        raise ConfigError(f"stage_id {stage_id!r} != expected {STAGE_ID!r}")

    if "scenarios" in raw:                       # source study
        table = raw["scenarios"] or []
        if not isinstance(table, list) or not table:
            raise ConfigError("'scenarios' must be a non-empty list")
        for s in table:
            if not isinstance(s, Mapping) or set(s) != set(_SCENARIO_KEYS):
                raise ConfigError(
                    f"each scenario needs exactly the keys {_SCENARIO_KEYS}: {s!r}")
        names = [str(s["name"]) for s in table]
        if len(set(names)) != len(names):
            raise ConfigError(f"duplicate scenario names: {names}")
        if scenario is None:
            raise ConfigError(
                f"this config is a source study; pick a scenario from {names}")
        matches = [s for s in table if str(s["name"]) == scenario]
        if not matches:
            raise ConfigError(f"unknown scenario {scenario!r}; known: {names}")
        bx_raw = matches[0].get("Bx_T")
        scenarios = tuple(dict(s) for s in table)
    else:                                        # frozen single scenario
        if "scenario" not in raw or "field" not in raw:
            raise ConfigError("frozen config needs 'scenario' and 'field'")
        if scenario is not None and str(raw["scenario"]) != scenario:
            raise ConfigError(
                f"frozen config is scenario {raw['scenario']!r}, not {scenario!r}")
        scenario = str(raw["scenario"])
        fld = raw["field"]
        if not isinstance(fld, Mapping) or set(fld) != {"Bx_T"}:
            raise ConfigError("'field' must hold exactly Bx_T")
        bx_raw = fld.get("Bx_T")
        scenarios = ()

    ele, bea, geo = raw["electrical"], raw["beam"], raw["geometry"]
    pla, res, dom = raw["plasma"], raw["reservoir"], raw["domain"]
    num, run, com = raw["numerics"], raw["run"], raw["compute"]
    dt_raw = num.get("dt")
    phi_ceiling_raw = run.get("phi_ceiling")
    cfg = Config(
        stage_id=stage_id, scenario=scenario,
        phi_body_init=_f(ele, "phi_body_init"),
        i_beam=_f(bea, "i_beam"), t_on=_f(bea, "t_on"),
        ke_inject_eV=_f(bea, "ke_inject_eV"),
        emit_radius=_f(bea, "emit_radius"),
        rms_velocity=_f(bea, "rms_velocity"),
        r_probe=_f(geo, "r_probe"), z_bot=_f(geo, "z_bot"), z_top=_f(geo, "z_top"),
        n0=_f(pla, "n0"), Te_K=_f(pla, "Te_K"), Ti_K=_f(pla, "Ti_K"),
        ion_mass_me=_f(pla, "ion_mass_me"),
        Bx_T=(None if bx_raw is None else float(bx_raw)),
        reservoir_enabled=bool(res["enabled"]),
        reservoir_frac=_f(res, "frac"), reservoir_every=_i(res, "every"),
        half_x=_f(dom, "half_x"), half_y=_f(dom, "half_y"),
        zmargin_lo=_f(dom, "zmargin_lo"), zmargin_hi=_f(dom, "zmargin_hi"),
        edge_phi_max=_f(dom, "edge_phi_max"),
        dx=_f(num, "dx"),
        dt_explicit=(None if dt_raw is None else float(dt_raw)),
        ppc=_i(num, "ppc"), ppc_beam=_i(num, "ppc_beam"),
        t_end=_f(run, "t_end"), max_steps_cap=_i(run, "max_steps"),
        diag_period_frac=_i(run, "diag_period_frac"),
        phi_ceiling=(None if phi_ceiling_raw is None else float(phi_ceiling_raw)),
        choke_sustain=_f(run, "choke_sustain"),
        gpu_arena_bytes=_i(com, "gpu_arena_bytes"),
        max_grid_size=(None if com.get("max_grid_size") is None
                       else int(com["max_grid_size"])),
        _scenarios=scenarios,
    )
    if cfg.Bx_T is not None and not math.isfinite(cfg.Bx_T):
        raise ConfigError("field.Bx_T must be finite or null")
    cfg.validate()
    return cfg


def analytic_capacitance(r_probe: float) -> float:
    """Isolated-sphere scale 4*pi*eps0*r_p used as the C-calibration sanity band."""
    return 4.0 * math.pi * EPS0 * r_probe
