#!/usr/bin/env python3
r"""propagate.py — the TudatPy propagation and the per-arc CSV export loop.

An idealised thruster fires continuously to exactly cancel instantaneous drag,
so altitude is HELD and the per-row drag force IS the thrust a real system would
have to supply. That equivalence is the whole point of the CSV: `drag_N` is the
demand signal the design side sizes against.

The exported drag comes from the INDEPENDENTLY saved aerodynamic acceleration
norm, not from the cancelling acceleration, so the number does not depend on the
cancel direction being perfect.

Propagation runs in monthly arcs chained state-to-state so memory stays bounded
over a year; each arc is integrated on a 60 s fixed RKF7(8) grid, decimated to
the 300 s CSV grid, and enriched with IRI-2020 (n_e, Te, Ti) at every exported
pose. 300 s resolves the diurnal ionospheric swing with ~19 samples per orbit,
which is what makes day-vs-night design points readable straight off the CSV.

Depends on: tudatpy, numpy, environment.
"""

import csv
import datetime as _dt
import math
import time as _wall

import numpy as np

try:
    from tudatpy.dynamics import propagation_setup
    from tudatpy.dynamics import simulator as tud_sim
except ImportError:  # pragma: no cover - legacy fallback
    from tudatpy.numerical_simulation import propagation_setup
    import tudatpy.numerical_simulation as tud_sim

from tudatpy.astro import element_conversion
from tudatpy.astro import time_representation as tr
from tudatpy.util import result2array

import environment as env_mod

OMEGA_E = 7.2921159e-5           # Earth rotation rate [rad/s], for the airspeed direction
EARTH_J2 = 1.08262668e-3         # zonal J2 (EGM96), for the circular-velocity setup

CSV_COLUMNS = [
    "timestamp_utc",             # ISO-8601 UTC
    "altitude_km",               # ellipsoidal, WGS-84
    "latitude_deg",              # geodetic
    "longitude_deg",             # east, wrapped to [-180, 180)
    "electron_density_m3",       # IRI-2020
    "electron_temperature_K",    # IRI-2020
    "ion_temperature_K",         # IRI-2020
    "drag_N",                    # = thruster demand, because drag is cancelled
]


def build_accelerations(cfg, bodies, craft):
    acc = propagation_setup.acceleration
    s_ref, cd = craft.reference_area_m2, craft.cd

    def drag_cancel(time):
        """Continuous thrust that exactly opposes the instantaneous drag.

        Reads the live environment through the closed-over `bodies`, and returns
        an acceleration of magnitude |a_drag| along the wind-free airspeed
        direction, so drag is cancelled and altitude is held.
        """
        veh = bodies.get("Vehicle")
        fc = veh.flight_conditions
        r_rel = veh.position - bodies.get("Earth").position
        v_air = veh.velocity - np.cross([0.0, 0.0, OMEGA_E], r_rel)
        speed = np.linalg.norm(v_air)
        if speed == 0.0:
            return np.zeros(3)
        drag_mag = 0.5 * fc.density * fc.airspeed**2 * cd * s_ref / veh.mass
        return drag_mag * v_air / speed

    accs = {
        "Earth": [acc.spherical_harmonic_gravity(cfg.gravity.sh_degree,
                                                 cfg.gravity.sh_order),
                  acc.aerodynamic()],
        "Sun": [acc.point_mass_gravity(), acc.radiation_pressure()],
        "Moon": [acc.point_mass_gravity()],
        "Vehicle": [acc.custom_acceleration(drag_cancel)],
    }
    return propagation_setup.create_acceleration_models(
        bodies, {"Vehicle": accs}, ["Vehicle"], ["Earth"])


def initial_state(cfg, mu):
    """Cartesian initial state for a near-circular, near-equatorial orbit.

    A two-body circular speed sqrt(mu/a) inserted into the real (J2) field is
    ~0.07 % too slow at the equator, which excites an osculating eccentricity
    e ~ 1.5*J2*(Re/a)^2 and a spurious ~10 km once-per-orbit altitude breathing
    that would contaminate the drag statistics. Start at the ascending node and
    boost the tangential speed by the J2 equatorial factor so the osculating
    orbit is genuinely near-circular; the residual few-km variation from higher
    zonals and the 0.5 deg inclination is physically real.
    """
    o = cfg.orbit
    r = env_mod.WGS84_A + o.initial_altitude_km * 1.0e3
    cart = element_conversion.keplerian_to_cartesian_elementwise(
        semi_major_axis=r,
        eccentricity=o.eccentricity,
        inclination=math.radians(o.inclination_deg),
        argument_of_periapsis=math.radians(o.argp_deg),
        longitude_of_ascending_node=math.radians(o.raan_deg),
        true_anomaly=math.radians(o.true_anomaly_deg),
        gravitational_parameter=mu,
    ).ravel()
    cart[3:6] *= math.sqrt(1.0 + 1.5 * EARTH_J2 * (env_mod.WGS84_A / r) ** 2)
    return cart


def dependent_variables():
    dv = propagation_setup.dependent_variable
    acc = propagation_setup.acceleration
    return [
        dv.geodetic_latitude("Vehicle", "Earth"),                  # rad
        dv.longitude("Vehicle", "Earth"),                          # rad, ECEF east
        dv.altitude("Vehicle", "Earth"),                           # m, ellipsoidal
        dv.single_acceleration_norm(acc.aerodynamic_type,
                                    "Vehicle", "Earth"),           # m/s^2, |a_drag|
    ]


def propagate_arc(cfg, bodies, acceleration_models, state0, t_start, t_end, dep_vars):
    integrator_settings = propagation_setup.integrator.runge_kutta_fixed_step(
        cfg.mission.integration_step_s,
        propagation_setup.integrator.CoefficientSets.rkf_78)
    termination = propagation_setup.propagator.hybrid_termination(
        [propagation_setup.propagator.time_termination(tr.Time(float(t_end))),
         propagation_setup.propagator.dependent_variable_termination(
             propagation_setup.dependent_variable.altitude("Vehicle", "Earth"),
             cfg.orbit.decay_floor_km * 1e3, use_as_lower_limit=True)],
        fulfill_single_condition=True)
    prop_settings = propagation_setup.propagator.translational(
        ["Earth"], acceleration_models, ["Vehicle"], state0,
        tr.Time(float(t_start)), integrator_settings, termination,
        output_variables=dep_vars)
    sim = tud_sim.create_dynamics_simulator(bodies, prop_settings)
    return (result2array(sim.propagation_results.state_history),
            result2array(sim.propagation_results.dependent_variable_history))


def _wrap180(lon_deg):
    return (lon_deg + 180.0) % 360.0 - 180.0


def _append_csv(path, row_dts, block, write_header):
    mode = "w" if write_header else "a"
    with open(path, mode, newline="") as fh:
        w = csv.writer(fh)
        if write_header:
            w.writerow(CSV_COLUMNS)
        for dt, row in zip(row_dts, block):
            w.writerow([
                dt.replace(tzinfo=_dt.timezone.utc).isoformat(),
                f"{row[0]:.4f}",                       # altitude_km
                f"{row[1]:.6f}", f"{row[2]:.6f}",      # lat, lon
                f"{row[3]:.6e}",                       # electron_density_m3
                f"{row[4]:.2f}", f"{row[5]:.2f}",      # Te, Ti
                f"{row[6]:.6e}",                       # drag_N
            ])


class RunningStats:
    """Streaming min/max/mean across arcs, so a year never sits in memory."""

    FIELDS = ("alt", "drag", "ne", "te", "ti")

    def __init__(self):
        self.n = 0
        self._sum = {f: 0.0 for f in self.FIELDS}
        self._min = {f: np.inf for f in self.FIELDS}
        self._max = {f: -np.inf for f in self.FIELDS}
        self.alt_first = None
        self.alt_last = None

    def update(self, alt, drag, ne, te, ti):
        self.n += len(alt)
        for f, arr in zip(self.FIELDS, (alt, drag, ne, te, ti)):
            self._sum[f] += float(arr.sum())
            self._min[f] = min(self._min[f], float(arr.min()))
            self._max[f] = max(self._max[f], float(arr.max()))
        if self.alt_first is None:
            self.alt_first = float(alt[0])
        self.alt_last = float(alt[-1])

    def triple(self, field):
        """(min, mean, max) of a tracked field."""
        return (self._min[field], self._sum[field] / max(self.n, 1), self._max[field])

    @property
    def alt_drift(self):
        return (self.alt_last or 0.0) - (self.alt_first or 0.0)


def run(cfg, craft, bodies, acceleration_models, mu, start_epoch, csv_path):
    """Propagate the whole mission, writing the CSV arc by arc.

    Returns (n_rows, stats, wall_time_s).
    """
    m = cfg.mission
    dep_vars = dependent_variables()
    state0 = initial_state(cfg, mu)

    total_seconds = m.duration_days * 86400.0
    arc_seconds = m.arc_days * 86400.0
    step_ratio = int(round(m.output_step_s / m.integration_step_s))

    n_rows = 0
    last_epoch_written = -np.inf
    stats = RunningStats()
    wrote_header = False
    t0_wall = _wall.time()

    n_arcs = int(math.ceil(total_seconds / arc_seconds))
    arc_start = start_epoch
    for arc_i in range(n_arcs):
        arc_end = min(start_epoch + total_seconds, arc_start + arc_seconds)
        # snap the arc end onto the CSV grid so arcs join without a ragged seam
        arc_end = start_epoch + round((arc_end - start_epoch) / m.output_step_s) * m.output_step_s

        t_arc = _wall.time()
        states, deps = propagate_arc(cfg, bodies, acceleration_models, state0,
                                     arc_start, arc_end, dep_vars)
        state0 = states[-1, 1:7]              # chain the next arc from this final state
        arc_final_epoch = states[-1, 0]

        idx = np.arange(0, len(deps), step_ratio)
        idx = idx[deps[idx, 0] > last_epoch_written + 1e-6]   # drop the shared seam row
        if idx.size == 0:
            arc_start = arc_final_epoch
            continue

        epochs = deps[idx, 0]
        lat_deg = np.degrees(deps[idx, 1])
        lon_deg = _wrap180(np.degrees(deps[idx, 2]))
        alt_km = deps[idx, 3] / 1.0e3
        drag_acc = deps[idx, 4]
        drag_N = craft.mass_kg * drag_acc

        row_dts = [tr.date_time_from_epoch(float(e)).to_python_datetime() for e in epochs]
        ne, te, ti = env_mod.evaluate_iri(row_dts, lat_deg, lon_deg, alt_km)

        block = np.column_stack([alt_km, lat_deg, lon_deg, ne, te, ti, drag_N])
        _append_csv(csv_path, row_dts, block, write_header=not wrote_header)
        wrote_header = True
        n_rows += len(idx)
        last_epoch_written = float(epochs[-1])
        stats.update(alt_km, drag_N, ne, te, ti)

        elapsed_days = (epochs - start_epoch) / 86400.0
        print(f"  arc {arc_i+1}/{n_arcs}: t={elapsed_days[0]:.1f}->{elapsed_days[-1]:.1f} d"
              f" | {len(idx)} rows | alt {alt_km.min():.1f}-{alt_km.max():.1f} km"
              f" | drag {drag_N.min()*1e9:.1f}-{drag_N.max()*1e9:.1f} nN"
              f" | n_e {ne.min():.2e}-{ne.max():.2e} m^-3"
              f" | Te {te.min():.0f}-{te.max():.0f} K"
              f" | {(_wall.time()-t_arc):.1f}s", flush=True)

        if arc_final_epoch < arc_end - m.integration_step_s:
            print("  ! propagation terminated early (altitude floor reached)", flush=True)
            break
        arc_start = arc_final_epoch

    return n_rows, stats, _wall.time() - t0_wall
