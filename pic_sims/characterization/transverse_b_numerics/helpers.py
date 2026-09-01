#!/usr/bin/env python3
"""Stage-local configuration for characterization.transverse_b_numerics.

The validation mini-ladder the transverse-B measurement rides on (the design
note in future_work/M2_TRANSVERSE_B.md asked for it): single test electrons
on the SAME cubic grid and time step as the measurement deck
(../magnetized_transverse), pushed through the same Boris/ES machinery,
compared with closed-form gyration and E x B drift.  No plasma, no body.

Multi-scenario source study: one test particle per scenario.  No pywarpx,
matplotlib, or openPMD here, and no run/analysis lifecycle (ladder_contract).
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Optional

import yaml
from scipy import constants as scc

STAGE_ID = "characterization.transverse_b_numerics"
SPECIES = "test_electrons"

E = scc.e
ME = scc.m_e
CC = scc.c

_SCHEMA: dict[str, tuple[str, ...]] = {
    "grid": ("dx", "nx", "ny", "nz", "zmin"),
    "numerics": ("dt",),
    "compute": ("gpu_arena_bytes",),
}
_SCENARIO_KEYS = ("name", "Bx_T", "Ez_V_per_m", "ke_eV", "x0", "y0", "z0", "t_run")


class ConfigError(ValueError):
    """A malformed or physically invalid stage configuration."""


def _reject_unknown(raw: Mapping[str, Any]) -> None:
    allowed_top = set(_SCHEMA) | {"stage_id", "scenarios", "scenario", "case"}
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


@dataclass(frozen=True)
class Config:
    stage_id: str
    scenario: Optional[str]
    # grid (must equal the measurement deck's; the tests assert it)
    dx: float
    nx: int
    ny: int
    nz: int
    zmin: float
    dt: float
    gpu_arena_bytes: int
    # the case: one test electron in uniform fields
    Bx_T: float
    Ez_V_per_m: float
    ke_eV: float
    x0: float
    y0: float
    z0: float
    t_run: float
    _scenarios: tuple[dict, ...] = ()

    @property
    def xmax(self) -> float:
        return 0.5 * self.nx * self.dx

    @property
    def ymax(self) -> float:
        return 0.5 * self.ny * self.dx

    @property
    def zmax(self) -> float:
        return self.zmin + self.nz * self.dx

    @property
    def Lz(self) -> float:
        return self.nz * self.dx

    @property
    def omega_c(self) -> float:
        return E * abs(self.Bx_T) / ME

    @property
    def T_c(self) -> float:
        return 2.0 * math.pi / self.omega_c

    @property
    def v0(self) -> float:
        """Launch speed along +z for ke_eV (relativistically exact)."""
        g = 1.0 + E * self.ke_eV / (ME * CC**2)
        return CC * math.sqrt(1.0 - 1.0 / g**2)

    @property
    def gamma0(self) -> float:
        return 1.0 + E * self.ke_eV / (ME * CC**2)

    @property
    def r_gyro(self) -> float:
        """Exact gyroradius of the launch momentum (perpendicular to B)."""
        return self.gamma0 * ME * self.v0 / (E * abs(self.Bx_T))

    @property
    def v_exb(self) -> float:
        """E x B drift for E = Ez z-hat, B = Bx x-hat: v_y = Ez / Bx."""
        return self.Ez_V_per_m / self.Bx_T

    @property
    def phi_hi_z(self) -> float:
        """Dirichlet potential on the +z face giving a uniform Ez (lo face at 0)."""
        return -self.Ez_V_per_m * self.Lz

    @property
    def max_steps(self) -> int:
        return int(math.ceil(self.t_run / self.dt))

    def scenario_names(self) -> tuple[str, ...]:
        return tuple(str(s["name"]) for s in self._scenarios)

    def _shared(self) -> dict:
        return {
            "stage_id": self.stage_id,
            "grid": {"dx": self.dx, "nx": self.nx, "ny": self.ny, "nz": self.nz,
                     "zmin": self.zmin},
            "numerics": {"dt": self.dt},
            "compute": {"gpu_arena_bytes": self.gpu_arena_bytes},
        }

    def effective_config(self) -> dict:
        out = self._shared()
        out["scenario"] = self.scenario
        out["case"] = {"Bx_T": self.Bx_T, "Ez_V_per_m": self.Ez_V_per_m,
                       "ke_eV": self.ke_eV, "x0": self.x0, "y0": self.y0,
                       "z0": self.z0, "t_run": self.t_run}
        return out

    def study_config(self) -> Optional[dict]:
        if not self._scenarios:
            return None
        out = self._shared()
        out["scenarios"] = [{k: (str(s[k]) if k == "name" else float(s[k]))
                             for k in _SCENARIO_KEYS} for s in self._scenarios]
        return out

    def validate(self) -> None:
        if self.dx <= 0 or min(self.nx, self.ny, self.nz) < 8:
            raise ConfigError("grid must have >= 8 cells per side")
        if self.dt <= 0:
            raise ConfigError("numerics.dt must be positive")
        if not (0.0 < abs(self.Bx_T) <= 1.0e-2):
            raise ConfigError("case.Bx_T must be a nonzero field within +-10 mT")
        if self.omega_c * self.dt >= 0.2:
            raise ConfigError("omega_c*dt >= 0.2: gyromotion under-resolved")
        if self.ke_eV < 0:
            raise ConfigError("case.ke_eV must be >= 0")
        if self.t_run <= 0:
            raise ConfigError("case.t_run must be positive")
        if not (abs(self.x0) < self.xmax and abs(self.y0) < self.ymax
                and self.zmin < self.z0 < self.zmax):
            raise ConfigError("launch point outside the box")
        if self.ke_eV > 0 and self.v0 * self.dt > 0.5 * self.dx:
            raise ConfigError("test particle crosses more than half a cell per step")


def scenario_names(path: Path | str) -> list[str]:
    raw = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    return [str(s["name"]) for s in (raw.get("scenarios") or [])]


def load_config(path: Path | str, scenario: str | None = None) -> Config:
    raw = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    if not isinstance(raw, Mapping):
        raise ConfigError(f"config {path} is not a mapping")
    _reject_unknown(raw)
    stage_id = str(raw.get("stage_id", ""))
    if stage_id != STAGE_ID:
        raise ConfigError(f"stage_id {stage_id!r} != expected {STAGE_ID!r}")

    if "scenarios" in raw:
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
        case = matches[0]
        scenarios = tuple(dict(s) for s in table)
    else:
        if "scenario" not in raw or "case" not in raw:
            raise ConfigError("frozen config needs 'scenario' and 'case'")
        if scenario is not None and str(raw["scenario"]) != scenario:
            raise ConfigError(
                f"frozen config is scenario {raw['scenario']!r}, not {scenario!r}")
        scenario = str(raw["scenario"])
        case = raw["case"]
        if not isinstance(case, Mapping) or set(case) != set(_SCENARIO_KEYS) - {"name"}:
            raise ConfigError("'case' must hold exactly the scenario physics keys")
        scenarios = ()

    grid, num, com = raw["grid"], raw["numerics"], raw["compute"]
    cfg = Config(
        stage_id=stage_id, scenario=scenario,
        dx=_f(grid, "dx"), nx=int(grid["nx"]), ny=int(grid["ny"]),
        nz=int(grid["nz"]), zmin=_f(grid, "zmin"),
        dt=_f(num, "dt"), gpu_arena_bytes=int(com["gpu_arena_bytes"]),
        Bx_T=_f(case, "Bx_T"), Ez_V_per_m=_f(case, "Ez_V_per_m"),
        ke_eV=_f(case, "ke_eV"), x0=_f(case, "x0"), y0=_f(case, "y0"),
        z0=_f(case, "z0"), t_run=_f(case, "t_run"),
        _scenarios=scenarios,
    )
    cfg.validate()
    return cfg
