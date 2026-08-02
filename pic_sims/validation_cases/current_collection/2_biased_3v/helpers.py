#!/usr/bin/env python3
"""Stage-local physics and configuration for a current_collection stage.

A conducting sphere (embedded boundary) at fixed bias in the electron_contactor
capstone plasma.  This file holds the typed config, the derived plasma/probe
quantities, and the closed-form references (thermal-flux law, OML ceiling,
species ratio).  It is duplicated verbatim in each collector stage folder --
that duplication is deliberate, so a reviewer sees the whole model per folder.

No pywarpx/PICMI, matplotlib, or openPMD here, and no run/analysis lifecycle
(that is ladder_contract).

Analytic references:
  I_th   = n0 * e * <v>/4 * 4*pi*a^2       exact at 0 V for ANY convex probe
  I_OML  = I_th * (1 + e*V/kTe)            small-sphere ceiling, a/lambda_De << 1
  I_e/I_i = sqrt((mi/me)*(Te/Ti))          species ratio, area/density-free
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

import yaml
from scipy import constants as scc

ELECTRONS, IONS = "electrons", "ions"

# The three collector stages share this code; each declares its own stage_id.
STAGE_IDS = ("collector.thermal", "collector.biased_3v", "collector.biased_10v")

_SCHEMA: dict[str, tuple[str, ...]] = {
    "probe": ("radius", "bias"),
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
    """Typed view of one current_collection config plus derived quantities."""
    stage_id: str
    probe_radius: float
    bias: float
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
    scenario: Any = None  # collector stages are single-run (uniform API)

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
    def chi(self) -> float:
        return self.bias / self.kTe_eV  # e*V/kTe

    @property
    def I_oml_e(self) -> float:
        return self.I_th_e * (1.0 + max(self.chi, 0.0))

    @property
    def ion_boltzmann(self) -> float:
        """Repelled-ion Boltzmann factor for a positive bias."""
        return math.exp(-max(self.bias, 0.0) / self.kTi_eV)

    @property
    def a_over_debye(self) -> float:
        return self.probe_radius / self.debye

    # ----- serialization -----
    def effective_config(self) -> dict:
        return {
            "stage_id": self.stage_id,
            "probe": {"radius": self.probe_radius, "bias": self.bias},
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
        if self.max_steps % self.scrape_period != 0:
            raise ConfigError("max_steps must be divisible by scrape_period")
        if self.max_steps % self.field_period != 0:
            raise ConfigError("max_steps must be divisible by field_period")
        # Grid must resolve the Debye length (else the sheath is unphysical).
        if max(self.d_r, self.d_z) >= self.debye:
            raise ConfigError("grid must resolve lambda_De")
        # CFL for the fastest electron (bias infall + 4*vth tail).
        v_fall = math.sqrt(2.0 * scc.e * max(self.bias, 0.0) / scc.m_e)
        vmax = v_fall + 4.0 * self.vth_e
        cfl = self.time_step * vmax / min(self.d_r, self.d_z)
        if cfl >= 1.0:
            raise ConfigError(f"CFL too large: {cfl:.2f}")


def load_config(path: Path | str, scenario: str | None = None) -> Config:
    """Parse, coerce, and validate a config.yaml (or a frozen config_used.yaml)."""
    if scenario is not None:
        raise ConfigError("current_collection stages have no scenarios")
    raw = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    if not isinstance(raw, Mapping):
        raise ConfigError(f"config {path} is not a mapping")
    _reject_unknown(raw)
    pro, pla, geo = raw["probe"], raw["plasma"], raw["geometry"]
    num, dia, com = raw["numerics"], raw["diagnostics"], raw["compute"]
    stage_id = str(raw.get("stage_id", ""))
    if stage_id not in STAGE_IDS:
        raise ConfigError(f"stage_id {stage_id!r} not one of {STAGE_IDS}")
    cfg = Config(
        stage_id=stage_id,
        probe_radius=_f(pro, "radius"), bias=_f(pro, "bias"),
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
