#!/usr/bin/env python3
r"""environment.py — the physical environment: bodies, atmosphere, ionosphere.

Two model families, both driven by real observed inputs rather than climatology:

  NRLMSISE-00  neutral density, driven by the observed historical F10.7/Ap in
               Tudat's bundled CelesTrak space-weather file. This is what sets
               the drag, so it is the model the whole result rests on.
  IRI-2020     electron density AND electron/ion temperature along the actual
               propagated ground track. This is what the PIC side needs: it
               turns "400 km" into the three numbers (n_e, Te, Ti) a particle
               simulation can be run at.

IRI is DIAGNOSTIC: it is evaluated per exported pose but does not enter the
dynamics. It failing silently is not acceptable, so it raises with the offending
timestamp and position rather than writing a NaN. `np.isfinite` is load-bearing
there: iricore maps IRI's internal sentinel values to NaN, not to an exception.

Note the jf preset: `"default"` (NOT the predecessor's `"default_edens"`, which
zeroes jf[1] and returns electron density only). Te/Ti are valid from roughly
120 km to 2500 km; the config's decay floor already guards the lower end.

Depends on: tudatpy, iricore, numpy, constants.
"""

import datetime as _dt
import os

import numpy as np

try:
    from tudatpy.dynamics import environment_setup
    TUDAT_NAMESPACE = "tudatpy.dynamics (v1.0)"
except ImportError:  # pragma: no cover - legacy fallback
    from tudatpy.numerical_simulation import environment_setup
    TUDAT_NAMESPACE = "tudatpy.numerical_simulation (legacy 0.x)"

import iricore

from constants import R_EARTH

WGS84_A = R_EARTH
WGS84_F = 1.0 / 298.257223563

IRI_VERSION = 20
IRI_JF_PRESET = "default"            # full switch set: electron density AND Te/Ti

_IRI_JF = iricore.get_jf(IRI_JF_PRESET)


# ---------------------------------------------------------------------------
# bodies
# ---------------------------------------------------------------------------
def build_bodies(cfg, craft):
    """Earth/Sun/Moon plus the vehicle, with its rotation-derived reference area.

    `craft.reference_area_m2` is the ONE place the rotation state enters the
    dynamics. TudatPy's constant-coefficient aero interface takes a single
    scalar, so a held pose is expressed as an effective area that already folds
    in the grazing-friction term (see spacecraft.from_dims).
    """
    body_settings = environment_setup.get_default_body_settings(
        ["Earth", "Sun", "Moon"], "Earth", "J2000")

    body_settings.get("Earth").atmosphere_settings = \
        environment_setup.atmosphere.nrlmsise00()
    # explicit WGS-84 oblate shape -> geodetic latitude and ellipsoidal altitude
    body_settings.get("Earth").shape_settings = \
        environment_setup.shape.oblate_spherical(WGS84_A, WGS84_F)

    body_settings.add_empty_settings("Vehicle")
    body_settings.get("Vehicle").aerodynamic_coefficient_settings = \
        environment_setup.aerodynamic_coefficients.constant(
            craft.reference_area_m2, [craft.cd, 0.0, 0.0])
    body_settings.get("Vehicle").radiation_pressure_target_settings = \
        environment_setup.radiation_pressure.cannonball_radiation_target(
            craft.reference_area_m2, craft.cr, {"Sun": ["Earth"]})

    bodies = environment_setup.create_system_of_bodies(body_settings)
    bodies.get("Vehicle").mass = craft.mass_kg
    return bodies


# ---------------------------------------------------------------------------
# ionosphere
# ---------------------------------------------------------------------------
def evaluate_iri(dts, lats_deg, lons_deg, alts_km):
    """IRI-2020 (n_e [m^-3], Te [K], Ti [K]) at each (time, lat, lon, alt) row.

    Evaluated at the row's actual altitude (single-altitude call, no vertical
    profile interpolation). A model failure or a non-finite / non-positive
    result raises immediately with the offending pose rather than writing a
    silent NaN.
    """
    n = len(dts)
    ne = np.empty(n, dtype=float)
    te = np.empty(n, dtype=float)
    ti = np.empty(n, dtype=float)
    for i in range(n):
        lat = float(lats_deg[i])
        lon = float(lons_deg[i]) % 360.0          # IRI wants geographic lon in [0,360)
        alt = float(alts_km[i])
        try:
            out = iricore.iri(dts[i], [alt, alt, 1.0], lat, lon,
                              version=IRI_VERSION, jf=_IRI_JF)
            vals = (float(np.asarray(out.edens).ravel()[0]),
                    float(np.asarray(out.etemp).ravel()[0]),
                    float(np.asarray(out.itemp).ravel()[0]))
        except Exception as exc:  # noqa: BLE001 - re-raise with context
            raise RuntimeError(
                f"IRI-2020 evaluation failed at t={dts[i].isoformat()} "
                f"lat={lat:.4f} lon={lon:.4f} alt={alt:.3f} km: {exc}") from exc
        for name, val in zip(("Ne", "Te", "Ti"), vals):
            if not np.isfinite(val) or val <= 0.0:
                raise RuntimeError(
                    f"IRI-2020 returned non-physical {name}={val} at "
                    f"t={dts[i].isoformat()} lat={lat:.4f} lon={lon:.4f} "
                    f"alt={alt:.3f} km")
        ne[i], te[i], ti[i] = vals
    return ne, te, ti


def _iri_index_dir():
    return os.path.join(os.path.dirname(iricore.__file__), "data", "index")


def assert_models_available():
    """Fail before propagating if the model version is not the expected one."""
    assert IRI_VERSION == 20, "IRI version must be 20 (IRI-2020)"
    return f"IRI-2020 (jf preset '{IRI_JF_PRESET}': electron density + Te/Ti)"


def assert_iri_coverage(start_dt, end_dt):
    """Fail early unless the apf107 index covers the whole mission span.

    A year-long propagation that discovers on day 300 that its solar-index file
    stops in month 9 has wasted the whole run.
    """
    with open(os.path.join(_iri_index_dir(), "apf107.dat")) as fh:
        first = last = None
        for line in fh:
            if line.strip():
                first = first or line
                last = line

    def _rec_date(rec):
        yy, mm, dd = int(rec[0:3]), int(rec[3:6]), int(rec[6:9])
        yy += 1900 if yy >= 58 else 2000
        return _dt.datetime(yy, mm, dd)

    cov_start, cov_end = _rec_date(first), _rec_date(last)
    if not (cov_start <= start_dt and end_dt <= cov_end + _dt.timedelta(days=1)):
        raise RuntimeError(
            f"IRI apf107 index covers {cov_start.date()}..{cov_end.date()} but the "
            f"mission needs {start_dt.date()}..{end_dt.date()}. Run "
            f"`python -c \"import iricore; iricore.update()\"` (needs internet).")
    return f"IRI index coverage OK: {cov_start.date()}..{cov_end.date()}"
