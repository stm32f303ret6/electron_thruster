#!/usr/bin/env python3
r"""config.py — the station-keeping scenario schema.

A scenario is a YAML file, merged STRICTLY over DEFAULTS (an unknown key is a
hard error, not a silent no-op), and the merged copy is written next to the
results as `config_used.yaml`. Reproducing a result means reading that file, not
reconstructing a command line.

DEFAULTS below IS the schema: nothing outside it can be set.

Renames vs the predecessor (`steps/step0_orbit/core/config.py`):
    orbit.altitude_km            -> orbit.initial_altitude_km
    spacecraft.cylinder_r_m/h_m  -> spacecraft.cylinder_radius_m/height_m
    spacecraft.attitude          -> spacecraft.rotation  (and 'endon' -> 'axial',
                                    plus the new 'lateral' broadside pose)
Dropped blocks: propulsion, solar, expect — this half of the repo stops at the
CSV, and the design/propulsion ledger lives in design_sims/.

Depends on: yamlcfg, spacecraft.
"""

from types import SimpleNamespace

import yamlcfg
from spacecraft import VALID_ROTATIONS

DEFAULTS = {
    "mission": {
        # 2024 is a fully observed past year, so NRLMSISE-00 uses real historical
        # F10.7/Ap, and it sits near solar-cycle-25 maximum -- a realistically
        # high drag environment rather than a quiet-sun best case.
        "start_utc": "2024-01-01T12:00:00",
        "duration_days": 365.0,
        "arc_days": 30.0,             # propagate in monthly arcs (bounded memory)
        "output_step_s": 300.0,       # CSV cadence
        "integration_step_s": 60.0,   # fixed RKF7(8) step
    },
    "orbit": {
        "initial_altitude_km": 400.0,
        "inclination_deg": 0.5,       # near-equatorial
        "eccentricity": 0.0,
        "raan_deg": 0.0,
        "argp_deg": 0.0,
        "true_anomaly_deg": 0.0,
        # Terminate the propagation below this. 120 km is also the floor of the
        # IRI electron/ion TEMPERATURE validity range, so it guards the CSV's
        # Te/Ti columns as well as the dynamics.
        "decay_floor_km": 120.0,
    },
    "spacecraft": {
        "mass_kg": 0.1,
        "cylinder_radius_m": 0.005,
        "cylinder_height_m": 0.005,
        "cd": 2.2,                    # free-molecular drag coefficient, broadside
        "cr": 1.2,                    # radiation-pressure coefficient
        # --- rotation ------------------------------------------------------
        # "axial":    axis along the velocity vector; drag hits the END CAPS.
        # "lateral":  broadside; drag hits the SIDE WALL.
        # "tumbling": uncontrolled; reference area = Cauchy mean A_ext/4.
        # See spacecraft.py for why the two held poses both carry a grazing
        # friction term, and why broadside is the LOW-drag pose at r = h.
        "rotation": "axial",
        "sigma_t": 0.9,               # tangential momentum accommodation, held poses
                                      # only. Flight-derived range is 0.5-0.9 and it
                                      # FALLS with altitude; 1.0 is outside the
                                      # literature.
        "exospheric_T_K": 1000.0,     # for the most-probable thermal speed in Cd_side
        "mean_mass_amu": 16.0,        # atomic oxygen dominates at 400-700 km
    },
    "gravity": {
        "sh_degree": 8,               # EGM96 spherical harmonics
        "sh_order": 8,
    },
    # --- solar ledger -------------------------------------------------------
    # Only the AVAILABLE power is computed here.  What the thruster REQUIRES is
    # a function of its figures of merit, which live in design_sims/ -- and this
    # tree reads nothing from there.  design_sims closes the loop.
    "solar": {
        "enabled": True,
        "cell_efficiency": 0.30,      # triple-junction PV, end-of-life-ish
        "packing_factor": 0.70,       # fraction of the wetted surface carrying cells
        "pointing_loss": 0.90,        # cosine/temperature/wiring derate, lumped
    },
}


class Config:
    """Merged config as attribute groups (cfg.orbit.initial_altitude_km)."""

    def __init__(self, merged, source_path=None):
        self.raw = merged
        self.source_path = str(source_path) if source_path else None
        for group, vals in merged.items():
            setattr(self, group, SimpleNamespace(**vals))
        self._validate()

    def _validate(self):
        s = self.spacecraft
        if s.rotation not in VALID_ROTATIONS:
            raise SystemExit(
                f"spacecraft.rotation must be one of {VALID_ROTATIONS}, got {s.rotation!r}")
        if s.cylinder_radius_m <= 0.0 or s.cylinder_height_m <= 0.0:
            raise SystemExit(
                "spacecraft.cylinder_radius_m and cylinder_height_m must both be positive")
        if s.mass_kg <= 0.0:
            raise SystemExit("spacecraft.mass_kg must be positive")
        if not (0.0 < s.sigma_t <= 1.0):
            raise SystemExit("spacecraft.sigma_t must be in (0, 1]")
        if s.rotation != "tumbling" and s.sigma_t > 0.9:
            print(f"[warn] sigma_t = {s.sigma_t} is above the flight-derived range "
                  f"(0.5-0.9). Grazing drag will be overstated.", flush=True)
        if self.mission.output_step_s % self.mission.integration_step_s != 0:
            raise SystemExit(
                "mission.output_step_s must be an integer multiple of "
                "integration_step_s (the CSV grid is a decimation of the fine grid)")
        if self.mission.duration_days <= 0.0:
            raise SystemExit("mission.duration_days must be positive")
        if self.mission.arc_days <= 0.0:
            raise SystemExit("mission.arc_days must be positive")
        sol = self.solar
        if not (0.0 < sol.cell_efficiency <= 1.0):
            raise SystemExit("solar.cell_efficiency must be in (0, 1]")
        if not (0.0 < sol.packing_factor <= 1.0):
            raise SystemExit("solar.packing_factor must be in (0, 1]")
        if not (0.0 < sol.pointing_loss <= 1.0):
            raise SystemExit("solar.pointing_loss must be in (0, 1]")
        if self.orbit.decay_floor_km < 120.0:
            print(f"[warn] orbit.decay_floor_km = {self.orbit.decay_floor_km} is below "
                  f"120 km, where IRI electron/ion temperatures stop being valid. "
                  f"Rows written below it would carry meaningless Te/Ti.", flush=True)

    def dump(self, path):
        yamlcfg.dump(self.raw, path)


def load(path):
    """Load a scenario YAML merged over DEFAULTS (strictly: a typo aborts)."""
    return Config(yamlcfg.load_merged(path, DEFAULTS), source_path=path)
