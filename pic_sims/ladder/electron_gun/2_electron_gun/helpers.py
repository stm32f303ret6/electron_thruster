#!/usr/bin/env python3
"""Stage-local physics and configuration for emitter.holed_anode.

Handles the multi-scenario source study: the live config.yaml lists all
scenarios, while a run's frozen config_used.yaml carries a single resolved
scenario.  ``load_config`` reads either form.  No pywarpx/PICMI, matplotlib, or
openPMD here, and no run/analysis lifecycle -- that is ladder_contract.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Optional

import yaml
from scipy import constants as scc

STAGE_ID = "emitter.holed_anode"
SPECIES_NAME = "electrons"

_SHARED_SCHEMA: dict[str, tuple[str, ...]] = {
    "geometry": ("r_max", "z_min", "z_max", "n_r", "n_z"),
    "electrodes": ("v_cathode", "v_collector", "v_anode"),
    "anode": ("z_front", "thickness"),
    "emission": ("radius", "u_th"),
    "numerics": ("time_step", "max_steps", "beam_ppc", "random_seed"),
    "diagnostics": ("field_period", "reduced_period", "scrape_period",
                    "ke_max_ev"),
    "compute": ("gpu_arena_bytes",),
}
_SCENARIO_KEYS = ("name", "current", "hole_radius")


class ConfigError(ValueError):
    """A malformed or physically invalid stage configuration."""


def _f(section: Mapping[str, Any], key: str) -> float:
    value = float(section[key])
    if not math.isfinite(value):
        raise ConfigError(f"non-finite value for '{key}': {section[key]!r}")
    return value


def _i(section: Mapping[str, Any], key: str) -> int:
    return int(section[key])


def _check_shared(raw: Mapping[str, Any], extra_top: set[str]) -> None:
    allowed_top = set(_SHARED_SCHEMA) | {"stage_id"} | extra_top
    unknown = set(raw) - allowed_top
    if unknown:
        raise ConfigError(f"unknown top-level config keys: {sorted(unknown)}")
    for section, keys in _SHARED_SCHEMA.items():
        if section not in raw:
            raise ConfigError(f"missing config section '{section}'")
        block = raw[section]
        if not isinstance(block, Mapping):
            raise ConfigError(f"config section '{section}' must be a mapping")


@dataclass(frozen=True)
class Config:
    """Typed view of ONE resolved scenario plus derived quantities."""
    stage_id: str
    r_max: float
    z_min: float
    z_max: float
    n_r: int
    n_z: int
    v_cathode: float
    v_collector: float
    v_anode: float
    anode_z_front: float
    anode_thickness: float
    emit_radius: float
    u_th: float
    time_step: float
    max_steps: int
    beam_ppc: int
    random_seed: int
    field_period: int
    reduced_period: int
    scrape_period: int
    ke_max_ev: float
    gpu_arena_bytes: int
    scenario: Optional[str]
    beam_current: float
    hole_radius: float
    _scenarios: tuple[dict, ...] = ()  # full study table, when known

    # ----- derived geometry / kinematics -----
    @property
    def d_r(self) -> float:
        return self.r_max / self.n_r

    @property
    def d_z(self) -> float:
        return (self.z_max - self.z_min) / self.n_z

    @property
    def flux(self) -> float:
        return self.beam_current / (
            math.pi * self.emit_radius**2 * scc.elementary_charge)

    @property
    def rms_velocity(self) -> float:
        return self.u_th * scc.speed_of_light

    @property
    def emit_z(self) -> float:
        return self.z_min + self.d_z

    @property
    def t_end(self) -> float:
        return self.max_steps * self.time_step

    @property
    def kt_launch_eV(self) -> float:
        return scc.m_e * self.rms_velocity**2 / scc.e

    @property
    def scenario_names(self) -> tuple[str, ...]:
        return tuple(str(s["name"]) for s in self._scenarios)

    # ----- references (display only; NOT gated -- see README C8 note) -----
    def child_langmuir_uA(self) -> float:
        """Planar Child-Langmuir current [uA] for the accel gap over the spot.

        A rough SCALE only: the geometry is non-planar, so this is printed for
        orientation, never used as a gate (plan C8)."""
        d = self.anode_z_front - self.z_min
        v = abs(self.v_anode - self.v_cathode)
        j_cl = (4.0 * scc.epsilon_0 / 9.0) * math.sqrt(
            2.0 * scc.e / scc.m_e) * v**1.5 / d**2
        return j_cl * math.pi * self.emit_radius**2 * 1e6

    def emitted_number(self) -> float:
        return (self.beam_current / scc.e) * self.t_end

    # ----- frozen / study serializations -----
    def effective_config(self) -> dict:
        """The single-scenario physics frozen to config_used.yaml and hashed."""
        return {
            "stage_id": self.stage_id,
            "scenario": self.scenario,
            "geometry": {
                "r_max": self.r_max, "z_min": self.z_min, "z_max": self.z_max,
                "n_r": self.n_r, "n_z": self.n_z,
            },
            "electrodes": {
                "v_cathode": self.v_cathode, "v_collector": self.v_collector,
                "v_anode": self.v_anode,
            },
            "anode": {
                "z_front": self.anode_z_front, "thickness": self.anode_thickness,
                "hole_radius": self.hole_radius,
            },
            "emission": {
                "radius": self.emit_radius, "u_th": self.u_th,
                "current": self.beam_current,
            },
            "numerics": {
                "time_step": self.time_step, "max_steps": self.max_steps,
                "beam_ppc": self.beam_ppc, "random_seed": self.random_seed,
            },
            "diagnostics": {
                "field_period": self.field_period,
                "reduced_period": self.reduced_period,
                "scrape_period": self.scrape_period,
                "ke_max_ev": self.ke_max_ev,
            },
            "compute": {"gpu_arena_bytes": self.gpu_arena_bytes},
        }

    def study_config(self) -> Optional[dict]:
        """The full source-study physics (shared + all scenarios), for the
        study SHA-256.  None if this Config was loaded from a frozen scenario."""
        if not self._scenarios:
            return None
        shared = self.effective_config()
        shared.pop("scenario", None)
        shared["anode"].pop("hole_radius", None)
        shared["emission"].pop("current", None)
        shared["scenarios"] = [
            {"name": str(s["name"]), "current": float(s["current"]),
             "hole_radius": float(s["hole_radius"])} for s in self._scenarios]
        return shared

    def validate(self) -> None:
        if self.n_r <= 0 or self.n_z <= 0:
            raise ConfigError("grid cell counts must be positive")
        if self.z_max <= self.z_min:
            raise ConfigError("z_max must exceed z_min")
        if self.emit_radius <= 0 or self.emit_radius >= self.r_max:
            raise ConfigError("emission radius must be inside the domain")
        if self.hole_radius <= 0 or self.hole_radius >= self.r_max:
            raise ConfigError("hole radius must be inside the domain")
        if self.beam_current <= 0:
            raise ConfigError("beam current must be positive")
        if self.max_steps <= 0 or self.time_step <= 0:
            raise ConfigError("max_steps and time_step must be positive")
        if self.max_steps % self.scrape_period != 0:
            raise ConfigError("max_steps must be divisible by scrape_period")
        if self.max_steps % self.field_period != 0:
            raise ConfigError("max_steps must be divisible by field_period")
        # anode plate must sit strictly inside the domain, downstream of source
        back = self.anode_z_front + self.anode_thickness
        if not (self.emit_z < self.anode_z_front < back < self.z_max):
            raise ConfigError("anode plate is not inside the drift region")
        v_fall = math.sqrt(2.0 * scc.e * abs(self.v_cathode) / scc.m_e)
        vmax = v_fall + 4.0 * self.rms_velocity
        cfl = self.time_step * vmax / min(self.d_r, self.d_z)
        if cfl >= 1.0:
            raise ConfigError(f"CFL too large: {cfl:.2f}")


def _build(raw: Mapping[str, Any], scenario: Optional[str],
           beam_current: float, hole_radius: float,
           scenarios: tuple[dict, ...]) -> Config:
    geo, ele, ano = raw["geometry"], raw["electrodes"], raw["anode"]
    emi, num = raw["emission"], raw["numerics"]
    dia, com = raw["diagnostics"], raw["compute"]
    cfg = Config(
        stage_id=str(raw.get("stage_id", STAGE_ID)),
        r_max=_f(geo, "r_max"), z_min=_f(geo, "z_min"), z_max=_f(geo, "z_max"),
        n_r=_i(geo, "n_r"), n_z=_i(geo, "n_z"),
        v_cathode=_f(ele, "v_cathode"), v_collector=_f(ele, "v_collector"),
        v_anode=_f(ele, "v_anode"),
        anode_z_front=_f(ano, "z_front"), anode_thickness=_f(ano, "thickness"),
        emit_radius=_f(emi, "radius"), u_th=_f(emi, "u_th"),
        time_step=_f(num, "time_step"), max_steps=_i(num, "max_steps"),
        beam_ppc=_i(num, "beam_ppc"), random_seed=_i(num, "random_seed"),
        field_period=_i(dia, "field_period"),
        reduced_period=_i(dia, "reduced_period"),
        scrape_period=_i(dia, "scrape_period"), ke_max_ev=_f(dia, "ke_max_ev"),
        gpu_arena_bytes=_i(com, "gpu_arena_bytes"),
        scenario=scenario, beam_current=beam_current, hole_radius=hole_radius,
        _scenarios=scenarios)
    if cfg.stage_id != STAGE_ID:
        raise ConfigError(f"stage_id {cfg.stage_id!r} != expected {STAGE_ID!r}")
    cfg.validate()
    return cfg


def scenario_names(path: Path | str) -> list[str]:
    """The scenario names declared in a source-study config, in order."""
    raw = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    return [str(s["name"]) for s in (raw.get("scenarios") or [])]


def load_config(path: Path | str, scenario: str | None = None) -> Config:
    """Load a source study (needs ``scenario``) or a frozen scenario config.

    A source study has a ``scenarios`` list and requires ``scenario`` to select
    one; a frozen ``config_used.yaml`` carries the resolved scenario inline."""
    raw = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    if not isinstance(raw, Mapping):
        raise ConfigError(f"config {path} is not a mapping")

    if "scenarios" in raw:                       # source study
        _check_shared(raw, extra_top={"scenarios"})
        table = raw["scenarios"]
        if not isinstance(table, list) or not table:
            raise ConfigError("'scenarios' must be a non-empty list")
        for s in table:
            unknown = set(s) - set(_SCENARIO_KEYS)
            if unknown:
                raise ConfigError(f"unknown scenario keys: {sorted(unknown)}")
        names = [str(s["name"]) for s in table]
        if len(set(names)) != len(names):
            raise ConfigError(f"duplicate scenario names: {names}")
        if scenario is None:
            raise ConfigError(
                f"a scenario must be selected; choices: {names}")
        if scenario not in names:
            raise ConfigError(f"unknown scenario {scenario!r}; choices: {names}")
        sc = next(s for s in table if str(s["name"]) == scenario)
        return _build(raw, scenario, _f(sc, "current"), _f(sc, "hole_radius"),
                      tuple(table))

    # frozen effective scenario config
    _check_shared(raw, extra_top={"scenario"})
    if "current" not in raw.get("emission", {}):
        raise ConfigError("frozen config missing emission.current")
    if "hole_radius" not in raw.get("anode", {}):
        raise ConfigError("frozen config missing anode.hole_radius")
    frozen_scn = raw.get("scenario")
    if scenario is not None and frozen_scn != scenario:
        raise ConfigError(
            f"requested scenario {scenario!r} != frozen {frozen_scn!r}")
    return _build(raw, frozen_scn, _f(raw["emission"], "current"),
                  _f(raw["anode"], "hole_radius"), ())
