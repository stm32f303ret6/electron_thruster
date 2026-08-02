#!/usr/bin/env python3
"""Stage-local physics and configuration for collector.floating.

A conducting sphere (embedded boundary) whose potential FLOATS via the
chipsat capstone's charge pump, in the electron_contactor capstone plasma.
This file holds the typed config, the derived plasma/probe quantities, and
the closed-form floating-potential references.  It is adapted from the
biased collector stages' shared-by-copy helpers; the deliberate physics
duplication is the ladder's convention.

No pywarpx/PICMI, matplotlib, or openPMD here, and no run/analysis lifecycle
(that is ladder_contract).

Analytic references (a/lambda_De = 0.38, deep OML regime):
  I_th   = n0 * e * <v>/4 * 4*pi*a^2      exact at 0 V for ANY convex probe
  R      = I_th_e/I_th_i = sqrt((mi/me)*(Te/Ti))
  floating potential = the bias where electron and ion collection balance:
    thermal-ion model (ions collect at I_th_i regardless of phi):
        exp(phi/kTe) * R = 1          ->  phi_f = -kTe/e * ln(R)
    OML-ion model (attracted ions collect at the OML sphere ceiling):
        exp(phi/kTe) * R = 1 - phi/kTi    (solved numerically)
  The truth for a sub-Debye sphere lies between the two models; phi_f is
  INDEPENDENT of the capacitance C (C only sets the charging timescale).
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

import yaml
from scipy import constants as scc

ELECTRONS, IONS = "electrons", "ions"

STAGE_ID = "collector.floating"

_SCHEMA: dict[str, tuple[str, ...]] = {
    "probe": ("radius",),
    "electrical": ("phi_init", "log_every"),
    "plasma": ("n0", "Te_K", "Ti_K", "ion_mass_me"),
    "geometry": ("r_max", "z_half", "n_r", "n_z"),
    "numerics": ("time_step", "max_steps", "ppc", "random_seed"),
    "diagnostics": ("field_period", "scrape_period", "reduced_period",
                    "steady_window_frac"),
    "compute": ("gpu_arena_bytes",),
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


@dataclass(frozen=True)
class Config:
    """Typed view of the floating-sphere config plus derived quantities."""
    stage_id: str
    probe_radius: float
    phi_init: float
    log_every: int
    n0: float
    Te_K: float
    Ti_K: float
    ion_mass_me: float
    r_max: float
    z_half: float
    n_r: int
    n_z: int
    time_step: float
    max_steps: int
    ppc: int
    random_seed: int
    field_period: int
    scrape_period: int
    reduced_period: int
    steady_window_frac: float
    gpu_arena_bytes: int
    scenario: Any = None  # single-run stage (uniform API)

    # ----- grid -----
    @property
    def d_r(self) -> float:
        return self.r_max / self.n_r

    @property
    def d_z(self) -> float:
        return 2.0 * self.z_half / self.n_z

    # ----- plasma / probe (all SI unless noted) -----
    @property
    def m_ion(self) -> float:
        return self.ion_mass_me * scc.m_e

    @property
    def kTe_J(self) -> float:
        return scc.k * self.Te_K

    @property
    def kTi_J(self) -> float:
        return scc.k * self.Ti_K

    @property
    def kTe_eV(self) -> float:
        return self.kTe_J / scc.e

    @property
    def kTi_eV(self) -> float:
        return self.kTi_J / scc.e

    @property
    def vth_e(self) -> float:
        return math.sqrt(self.kTe_J / scc.m_e)

    @property
    def vth_i(self) -> float:
        return math.sqrt(self.kTi_J / self.m_ion)

    @property
    def vbar_e(self) -> float:
        return math.sqrt(8.0 * self.kTe_J / (math.pi * scc.m_e))

    @property
    def vbar_i(self) -> float:
        return math.sqrt(8.0 * self.kTi_J / (math.pi * self.m_ion))

    @property
    def flux_e(self) -> float:
        return self.n0 * self.vbar_e / 4.0  # one-sided Maxwellian flux

    @property
    def flux_i(self) -> float:
        return self.n0 * self.vbar_i / 4.0

    @property
    def debye(self) -> float:
        return math.sqrt(scc.epsilon_0 * self.kTe_J / (self.n0 * scc.e**2))

    @property
    def wpe(self) -> float:
        return math.sqrt(self.n0 * scc.e**2 / (scc.m_e * scc.epsilon_0))

    @property
    def area(self) -> float:
        return 4.0 * math.pi * self.probe_radius**2

    @property
    def I_th_e(self) -> float:
        return scc.e * self.flux_e * self.area

    @property
    def I_th_i(self) -> float:
        return scc.e * self.flux_i * self.area

    @property
    def species_ratio_theory(self) -> float:
        return math.sqrt(self.ion_mass_me * self.Te_K / self.Ti_K)

    @property
    def a_over_debye(self) -> float:
        return self.probe_radius / self.debye

    # ----- floating-potential references -----
    @property
    def phi_float_thermal_ion(self) -> float:
        """Floating potential if ions collect at the bare thermal flux:
        exp(phi/kTe) * R = 1  ->  phi = -kTe/e * ln(R)."""
        return -self.kTe_eV * math.log(self.species_ratio_theory)

    @property
    def phi_float_oml_ion(self) -> float:
        """Floating potential if attracted ions collect at the OML sphere
        ceiling: exp(phi/kTe) * R = 1 - phi/kTi, solved by bisection.
        Less negative than the thermal-ion answer (enhanced ion current
        needs less electron retardation to balance)."""
        R = self.species_ratio_theory

        def net(phi: float) -> float:
            return math.exp(phi / self.kTe_eV) * R - (1.0 - phi / self.kTi_eV)

        lo, hi = self.phi_float_thermal_ion, 0.0   # net(lo) < 0 < net(hi)
        for _ in range(200):
            mid = 0.5 * (lo + hi)
            if net(mid) < 0.0:
                lo = mid
            else:
                hi = mid
        return 0.5 * (lo + hi)

    @property
    def analytic_capacitance(self) -> float:
        """Isolated-sphere scale 4*pi*eps0*a.  The grounded box at ~16 a
        raises the true C by ~a/r_wall ~ 6-7%; the C gate band covers it."""
        return 4.0 * math.pi * scc.epsilon_0 * self.probe_radius

    # ----- serialization -----
    def effective_config(self) -> dict:
        return {
            "stage_id": self.stage_id,
            "probe": {"radius": self.probe_radius},
            "electrical": {"phi_init": self.phi_init,
                           "log_every": self.log_every},
            "plasma": {"n0": self.n0, "Te_K": self.Te_K, "Ti_K": self.Ti_K,
                       "ion_mass_me": self.ion_mass_me},
            "geometry": {"r_max": self.r_max, "z_half": self.z_half,
                         "n_r": self.n_r, "n_z": self.n_z},
            "numerics": {"time_step": self.time_step, "max_steps": self.max_steps,
                         "ppc": self.ppc, "random_seed": self.random_seed},
            "diagnostics": {"field_period": self.field_period,
                            "scrape_period": self.scrape_period,
                            "reduced_period": self.reduced_period,
                            "steady_window_frac": self.steady_window_frac},
            "compute": {"gpu_arena_bytes": self.gpu_arena_bytes},
        }

    def validate(self) -> None:
        if self.n_r <= 0 or self.n_z <= 0:
            raise ConfigError("grid cell counts must be positive")
        if self.r_max <= 0 or self.z_half <= 0:
            raise ConfigError("domain extents must be positive")
        if self.probe_radius <= 0 or self.probe_radius >= min(self.r_max,
                                                              self.z_half):
            raise ConfigError("probe radius must be inside the domain")
        if self.n0 <= 0 or self.Te_K <= 0 or self.Ti_K <= 0:
            raise ConfigError("plasma density/temperatures must be positive")
        if self.max_steps <= 0 or self.time_step <= 0:
            raise ConfigError("max_steps and time_step must be positive")
        if not (0.0 < self.steady_window_frac <= 1.0):
            raise ConfigError("steady_window_frac must be in (0, 1]")
        if self.log_every < 1:
            raise ConfigError("electrical.log_every must be >= 1")
        if self.max_steps % self.log_every != 0:
            raise ConfigError("max_steps must be divisible by log_every")
        if self.max_steps % self.scrape_period != 0:
            raise ConfigError("max_steps must be divisible by scrape_period")
        if self.max_steps % self.field_period != 0:
            raise ConfigError("max_steps must be divisible by field_period")
        # Grid must resolve the Debye length (else the sheath is unphysical).
        if max(self.d_r, self.d_z) >= self.debye:
            raise ConfigError("grid must resolve lambda_De")
        # CFL for the fastest electron (thermal tail; the floating sphere
        # repels electrons, so there is no infall acceleration to add).
        vmax = 4.0 * self.vth_e
        cfl = self.time_step * vmax / min(self.d_r, self.d_z)
        if cfl >= 1.0:
            raise ConfigError(f"CFL too large: {cfl:.2f}")


def load_config(path: Path | str, scenario: str | None = None) -> Config:
    """Parse, coerce, and validate a config.yaml (or a frozen config_used.yaml)."""
    if scenario is not None:
        raise ConfigError("collector.floating has no scenarios")
    raw = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    if not isinstance(raw, Mapping):
        raise ConfigError(f"config {path} is not a mapping")
    _reject_unknown(raw)
    pro, ele, pla = raw["probe"], raw["electrical"], raw["plasma"]
    geo, num = raw["geometry"], raw["numerics"]
    dia, com = raw["diagnostics"], raw["compute"]
    stage_id = str(raw.get("stage_id", ""))
    if stage_id != STAGE_ID:
        raise ConfigError(f"stage_id {stage_id!r} != expected {STAGE_ID!r}")
    cfg = Config(
        stage_id=stage_id,
        probe_radius=_f(pro, "radius"),
        phi_init=_f(ele, "phi_init"), log_every=_i(ele, "log_every"),
        n0=_f(pla, "n0"), Te_K=_f(pla, "Te_K"), Ti_K=_f(pla, "Ti_K"),
        ion_mass_me=_f(pla, "ion_mass_me"),
        r_max=_f(geo, "r_max"), z_half=_f(geo, "z_half"),
        n_r=_i(geo, "n_r"), n_z=_i(geo, "n_z"),
        time_step=_f(num, "time_step"), max_steps=_i(num, "max_steps"),
        ppc=_i(num, "ppc"), random_seed=_i(num, "random_seed"),
        field_period=_i(dia, "field_period"),
        scrape_period=_i(dia, "scrape_period"),
        reduced_period=_i(dia, "reduced_period"),
        steady_window_frac=_f(dia, "steady_window_frac"),
        gpu_arena_bytes=_i(com, "gpu_arena_bytes"),
    )
    cfg.validate()
    return cfg
