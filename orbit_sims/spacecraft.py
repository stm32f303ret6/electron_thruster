#!/usr/bin/env python3
r"""spacecraft.py — the cylinder, its pose, and the reference area that follows.

Only ONE area matters here: the silhouette the drag equation uses, and it is set
by the ROTATION state. (The predecessor also tracked cell area and collecting
area, both of which belonged to the solar/propulsion ledgers this port drops.)

  rotation = tumbling   reference area = the Cauchy mean A_ext/4, the
                        orientation-averaged silhouette of a convex body.
                        Uncontrolled: the honest default when attitude is not
                        actively held.
           = axial      the cylinder axis is held along the velocity vector, so
                        drag hits the END CAPS. The lateral wall lies parallel
                        to the flow and pays only grazing free-molecular
                        friction, ~30x less per unit area.
           = lateral    the cylinder is held BROADSIDE, so drag hits the SIDE
                        WALL. Symmetric to axial: the ram silhouette is the
                        rectangle 2*r*h, and the caps now lie parallel to the
                        flow and pay the same grazing friction the wall pays in
                        the axial case.

Both held poses fold their two drag coefficients into ONE effective area,
because TudatPy's constant-coefficient aero interface takes a single scalar
S_ref with a single Cd:

    rho v^2/2 * (Cd*A_ram + Cd_side*A_parallel)
  = rho v^2/2 * Cd * [A_ram + (Cd_side/Cd)*A_parallel]

Dropping the grazing term from `lateral` while keeping it in `axial` would make
the two poses an apples-to-oranges comparison (~10 % on the squat r = h
chipsat), which is exactly the kind of silent asymmetry this repo exists to
avoid.

COUNTERINTUITIVE, WORTH KNOWING: the ram areas are pi*r^2 (axial) and 2*r*h
(lateral), so the axial pose has the larger silhouette whenever h < (pi/2)*r.
The chipsat is r = h = 5 mm, so pi*r^2 = 7.85e-5 m^2 beats 2*r*h = 5.0e-5 m^2:
BROADSIDE IS THE LOW-DRAG POSE for this squat body, not the high-drag one.
Slender bodies (h > 1.571*r) reverse it.

Depends on: constants only.
"""

import math
from dataclasses import dataclass

from constants import KB, MU_EARTH, R_EARTH, cauchy_mean_area, orbital_speed

AMU = 1.66053906892e-27

VALID_ROTATIONS = ("axial", "lateral", "tumbling")


@dataclass(frozen=True)
class Spacecraft:
    mass_kg: float
    cd: float
    cr: float
    rotation: str
    radius_m: float
    height_m: float
    external_area_m2: float
    reference_area_m2: float       # what the drag equation uses, given the rotation
    cauchy_area_m2: float          # the tumbling reference, always reported
    lateral_area_m2: float         # side wall, 2*pi*r*h
    cap_area_m2: float             # BOTH end caps, 2*pi*r^2
    ram_area_m2: float             # the silhouette that meets the flow head-on
    cd_side: float                 # grazing friction coefficient (0 when tumbling)
    meta: dict

    @property
    def ballistic_coefficient(self):
        """m / (Cd * S_ref) [kg/m^2]. Higher = decays slower."""
        return self.mass_kg / (self.cd * self.reference_area_m2)

    def describe(self):
        s = (f"cylinder r={self.radius_m*1e3:g} mm h={self.height_m*1e3:g} mm, "
             f"{self.mass_kg:g} kg, rotation={self.rotation}: "
             f"S_ref = {self.reference_area_m2:.4e} m^2, "
             f"BC = {self.ballistic_coefficient:.1f} kg/m^2")
        if self.rotation != "tumbling":
            parallel = (self.lateral_area_m2 if self.rotation == "axial"
                        else self.cap_area_m2)
            s += (f" (ram {self.ram_area_m2*1e4:.2f} cm^2 + parallel "
                  f"{parallel*1e4:.2f} cm^2 at Cd_side = {self.cd_side:.4f})")
        return s


def most_probable_speed(T_K, mass_amu):
    """Most probable thermal speed of the ambient neutrals [m/s]: sqrt(2kT/m)."""
    return math.sqrt(2.0 * KB * T_K / (mass_amu * AMU))


def grazing_cd(sigma_t, T_K, mass_amu, altitude_km):
    """Free-molecular drag coefficient of a surface PARALLEL to the flow.

        Cd_side = sigma_t * (v_mp / v_orbit) / sqrt(pi)

    A surface edge-on to a hyperthermal flow sees molecules only through their
    thermal spread, so the coefficient collapses from ~2.2 broadside to ~0.07.
    `sigma_t` is the tangential momentum accommodation coefficient.

    sigma_t is NOT a free parameter to fit. Flight-derived values sit in 0.5-0.9
    (and fall with altitude); it is also partly a surface-finish design choice,
    which is why it is a config key rather than a constant.
    """
    v_mp = most_probable_speed(T_K, mass_amu)
    return sigma_t * (v_mp / orbital_speed(altitude_km * 1e3)) / math.sqrt(math.pi)


def from_dims(*, radius_m, height_m, mass_kg, cd, cr, rotation, altitude_km,
              sigma_t=0.9, exospheric_T_K=1000.0, mean_mass_amu=16.0):
    """Build a Spacecraft from primitives."""
    if rotation not in VALID_ROTATIONS:
        raise ValueError(f"rotation must be one of {VALID_ROTATIONS}, got {rotation!r}")
    if radius_m <= 0.0 or height_m <= 0.0:
        raise ValueError("cylinder radius and height must both be positive")
    if mass_kg <= 0.0:
        raise ValueError("mass must be positive")

    lateral = 2.0 * math.pi * radius_m * height_m
    caps = 2.0 * math.pi * radius_m * radius_m
    external = lateral + caps
    cauchy = cauchy_mean_area(external)

    if rotation == "tumbling":
        s_ref, cd_side, ram = cauchy, 0.0, cauchy
    else:
        cd_side = grazing_cd(sigma_t, exospheric_T_K, mean_mass_amu, altitude_km)
        if rotation == "axial":
            ram = math.pi * radius_m ** 2          # one cap meets the flow
            parallel = lateral
        else:                                       # lateral / broadside
            ram = 2.0 * radius_m * height_m         # the side-on rectangle
            parallel = caps
        s_ref = ram + (cd_side / cd) * parallel

    meta = {"shape": "cylinder", "cylinder_radius_m": radius_m,
            "cylinder_height_m": height_m, "rotation": rotation}
    if rotation != "tumbling":
        meta.update(sigma_t=sigma_t, cd_side=cd_side,
                    exospheric_T_K=exospheric_T_K, mean_mass_amu=mean_mass_amu)

    return Spacecraft(
        mass_kg=mass_kg, cd=cd, cr=cr, rotation=rotation,
        radius_m=radius_m, height_m=height_m,
        external_area_m2=external, reference_area_m2=s_ref, cauchy_area_m2=cauchy,
        lateral_area_m2=lateral, cap_area_m2=caps, ram_area_m2=ram,
        cd_side=cd_side, meta=meta)


def projected_solar_area_m2(craft, sin_alpha):
    """Sunlit projected area [m^2] for an array-like of sin(sun-to-axis angle).

    For a HELD pose the cylinder's silhouette against the Sun is

        A(alpha) = pi*r^2*|cos alpha| + 2*r*h*sin alpha

    (the caps project as a disc, the wall as a rectangle).  Averaged over solid
    angle this integrates to A_ext/4 exactly -- <|cos|> = 1/2, <sin> = pi/4 --
    so the held and tumbling models agree in the mean, as they must.

    `tumbling` uses the Cauchy mean directly (no defined axis).  `lateral` also
    uses it: its axis is perpendicular to the velocity vector but its ROLL is
    unconstrained, so there is no honest per-row sun angle to compute -- an
    orientation average is the truthful answer rather than an invented one.
    """
    import numpy as np
    if craft.rotation == "axial":
        sa = np.clip(np.asarray(sin_alpha, dtype=float), 0.0, 1.0)
        ca = np.sqrt(np.clip(1.0 - sa * sa, 0.0, 1.0))
        return (math.pi * craft.radius_m ** 2 * ca
                + 2.0 * craft.radius_m * craft.height_m * sa)
    return np.full(np.shape(sin_alpha), craft.cauchy_area_m2, dtype=float)


def available_power_W(craft, irradiance_W_m2, sin_alpha, cfg):
    """Electrical power the body-mounted cells deliver [W], per exported row.

    `irradiance_W_m2` is Tudat's SHADOW-CORRECTED received irradiance, so
    eclipse is already folded in and an eclipsed row returns 0.
    """
    import numpy as np
    s = cfg.solar
    if not s.enabled:
        return np.zeros(np.shape(sin_alpha), dtype=float)
    area = projected_solar_area_m2(craft, sin_alpha)
    return (np.asarray(irradiance_W_m2, dtype=float) * area
            * s.packing_factor * s.cell_efficiency * s.pointing_loss)


def build(cfg):
    """Config adapter over `from_dims`."""
    s = cfg.spacecraft
    return from_dims(
        radius_m=s.cylinder_radius_m, height_m=s.cylinder_height_m,
        mass_kg=s.mass_kg, cd=s.cd, cr=s.cr, rotation=s.rotation,
        altitude_km=cfg.orbit.initial_altitude_km, sigma_t=s.sigma_t,
        exospheric_T_K=s.exospheric_T_K, mean_mass_amu=s.mean_mass_amu)


def orbital_period_s(cfg, mu=MU_EARTH):
    r = R_EARTH + cfg.orbit.initial_altitude_km * 1e3
    return 2.0 * math.pi * math.sqrt(r ** 3 / mu)
