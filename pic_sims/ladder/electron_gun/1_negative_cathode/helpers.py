#!/usr/bin/env python3
"""Stage-local physics and configuration for emitter.negative_cathode.

Small and unit-testable: typed config loading/validation, geometric and
numerical invariants, and the closed-form references the analysis compares
against.  This module must NOT import pywarpx/PICMI, matplotlib, or an openPMD
reader, must not touch the run/analysis lifecycle (that is ladder_contract), and
must not import another stage.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

import yaml
from scipy import constants as scc

STAGE_ID = "emitter.negative_cathode"
SPECIES_NAME = "electrons"

# Allowed config schema: rejecting unknown keys catches typos and silent config
# drift (an ignored misspelled key would otherwise run the wrong physics).
_SCHEMA: dict[str, tuple[str, ...]] = {
    "geometry": ("r_max", "z_min", "z_max", "n_r", "n_z"),
    "electrodes": ("v_cathode", "v_collector"),
    "emission": ("radius", "current", "u_th"),
    "numerics": ("time_step", "max_steps", "beam_ppc", "random_seed"),
    "diagnostics": ("field_period", "reduced_period", "scrape_period",
                    "ke_max_ev"),
    "compute": ("gpu_arena_bytes",),
}


class ConfigError(ValueError):
    """A malformed or physically invalid stage configuration."""


def _reject_unknown(raw: Mapping[str, Any]) -> None:
    allowed_top = set(_SCHEMA) | {"stage_id"}
    unknown_top = set(raw) - allowed_top
    if unknown_top:
        raise ConfigError(f"unknown top-level config keys: {sorted(unknown_top)}")
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
    """Coerce a numeric leaf to a finite float (PyYAML 1.1 may load it as str)."""
    value = float(section[key])
    if not math.isfinite(value):
        raise ConfigError(f"non-finite value for '{key}': {section[key]!r}")
    return value


def _i(section: Mapping[str, Any], key: str) -> int:
    return int(section[key])


@dataclass(frozen=True)
class Config:
    """Typed view of one negative_cathode config plus derived quantities."""
    stage_id: str
    r_max: float
    z_min: float
    z_max: float
    n_r: int
    n_z: int
    v_cathode: float
    v_collector: float
    emit_radius: float
    beam_current: float
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
    scenario: Any = None  # single-run stage: always None (uniform stage API)

    # ----- derived geometry / kinematics -----
    @property
    def d_r(self) -> float:
        return self.r_max / self.n_r

    @property
    def d_z(self) -> float:
        return (self.z_max - self.z_min) / self.n_z

    @property
    def flux(self) -> float:
        """Prescribed z-normal number flux [1/(m^2 s)] over the emission spot."""
        return self.beam_current / (
            math.pi * self.emit_radius**2 * scc.elementary_charge)

    @property
    def rms_velocity(self) -> float:
        return self.u_th * scc.speed_of_light

    @property
    def emit_z(self) -> float:
        """Source plane one cell inside the cathode (a regular cell, not the face)."""
        return self.z_min + self.d_z

    @property
    def t_end(self) -> float:
        return self.max_steps * self.time_step

    @property
    def kt_launch_eV(self) -> float:
        """Per-axis launch temperature of the flux Maxwellian [eV]."""
        return scc.m_e * self.rms_velocity**2 / scc.e

    # ----- closed-form references used by analyze.py -----
    def laplace_ramp(self, z):
        """Vacuum on-axis potential: the linear cathode->collector ramp [V]."""
        dV = self.v_collector - self.v_cathode
        L = self.z_max - self.z_min
        return self.v_cathode + dV * (z - self.z_min) / L

    def expected_collector_ke_eV(self) -> float:
        """Arrival KE by energy conservation from the emission plane [eV].

        Electrons born ~at rest at emit_z fall through
        phi(collector) - phi_ramp(emit_z) and carry the flux-Maxwellian launch
        energy 2*kT (one normal + two transverse half-degrees)."""
        return ((self.v_collector - self.laplace_ramp(self.emit_z))
                + 2.0 * self.kt_launch_eV)

    def emitted_number(self) -> float:
        """Total emitted electron weight over the run: (I/e) * t_end."""
        return (self.beam_current / scc.e) * self.t_end

    def effective_config(self) -> dict:
        """The physics/numerics dict frozen to config_used.yaml and hashed.

        Same nested shape as config.yaml, with type-stable coerced numbers, so
        load_config round-trips a frozen config identically to the live one."""
        return {
            "stage_id": self.stage_id,
            "geometry": {
                "r_max": self.r_max, "z_min": self.z_min, "z_max": self.z_max,
                "n_r": self.n_r, "n_z": self.n_z,
            },
            "electrodes": {
                "v_cathode": self.v_cathode, "v_collector": self.v_collector,
            },
            "emission": {
                "radius": self.emit_radius, "current": self.beam_current,
                "u_th": self.u_th,
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

    def validate(self) -> None:
        """Dimensional/geometric/numerical invariants; raise on any violation."""
        if self.n_r <= 0 or self.n_z <= 0:
            raise ConfigError("grid cell counts must be positive")
        if self.z_max <= self.z_min:
            raise ConfigError("z_max must exceed z_min")
        if self.r_max <= 0:
            raise ConfigError("r_max must be positive")
        if self.emit_radius <= 0 or self.emit_radius >= self.r_max:
            raise ConfigError("emission radius must be inside the domain")
        if self.beam_current <= 0:
            raise ConfigError("beam current must be positive")
        if self.max_steps <= 0 or self.time_step <= 0:
            raise ConfigError("max_steps and time_step must be positive")
        # A complete scrape/field grid needs max_steps divisible by the cadence,
        # so the final dump lands exactly on max_steps (sections 8.2, 10).
        if self.max_steps % self.scrape_period != 0:
            raise ConfigError(
                "max_steps must be divisible by scrape_period "
                f"({self.max_steps} % {self.scrape_period} != 0)")
        if self.max_steps % self.field_period != 0:
            raise ConfigError(
                "max_steps must be divisible by field_period")
        # CFL for the fastest electron (fell through the full 100 V gap).
        v_fall = math.sqrt(2.0 * scc.e * abs(self.v_cathode) / scc.m_e)
        vmax = v_fall + 4.0 * self.rms_velocity
        cfl = self.time_step * vmax / min(self.d_r, self.d_z)
        if cfl >= 1.0:
            raise ConfigError(f"CFL too large: {cfl:.2f}")
        # Source plane must sit strictly inside the domain (a regular cell).
        if not (self.z_min < self.emit_z < self.z_max):
            raise ConfigError("emission plane is not inside the domain")


def load_config(path: Path | str, scenario: str | None = None) -> Config:
    """Parse, coerce, and validate a config.yaml (or a frozen config_used.yaml).

    ``scenario`` is accepted for a uniform stage API but must be None here --
    negative_cathode is a single-run stage.
    """
    if scenario is not None:
        raise ConfigError("negative_cathode has no scenarios")
    raw = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    if not isinstance(raw, Mapping):
        raise ConfigError(f"config {path} is not a mapping")
    _reject_unknown(raw)
    geo, ele = raw["geometry"], raw["electrodes"]
    emi, num = raw["emission"], raw["numerics"]
    dia, com = raw["diagnostics"], raw["compute"]
    cfg = Config(
        stage_id=str(raw.get("stage_id", STAGE_ID)),
        r_max=_f(geo, "r_max"), z_min=_f(geo, "z_min"), z_max=_f(geo, "z_max"),
        n_r=_i(geo, "n_r"), n_z=_i(geo, "n_z"),
        v_cathode=_f(ele, "v_cathode"), v_collector=_f(ele, "v_collector"),
        emit_radius=_f(emi, "radius"), beam_current=_f(emi, "current"),
        u_th=_f(emi, "u_th"),
        time_step=_f(num, "time_step"), max_steps=_i(num, "max_steps"),
        beam_ppc=_i(num, "beam_ppc"), random_seed=_i(num, "random_seed"),
        field_period=_i(dia, "field_period"),
        reduced_period=_i(dia, "reduced_period"),
        scrape_period=_i(dia, "scrape_period"), ke_max_ev=_f(dia, "ke_max_ev"),
        gpu_arena_bytes=_i(com, "gpu_arena_bytes"),
    )
    if cfg.stage_id != STAGE_ID:
        raise ConfigError(
            f"stage_id {cfg.stage_id!r} != expected {STAGE_ID!r}")
    cfg.validate()
    return cfg
