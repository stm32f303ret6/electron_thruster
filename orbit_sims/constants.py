#!/usr/bin/env python3
"""SI constants and the two geometric helpers the orbit sim needs.

Trimmed port of the pre-refactor shared constants module: everything the
PIC side used (Debye lengths, thermal currents, electron speeds) is gone,
because this half of the repo stops at the CSV.

Depends on scipy only, so it imports in either conda environment.
"""

import math

from scipy import constants as scc

KB = scc.k                 # Boltzmann constant [J/K]

MU_EARTH = 3.986004418e14  # Earth GM [m^3/s^2]
R_EARTH = 6378137.0        # WGS-84 equatorial radius [m]


def cauchy_mean_area(total_surface_area_m2):
    """Orientation-averaged projected area of a convex body = A_surface / 4.

    Cauchy's formula. This is the correct reference area for a TUMBLING body:
    averaged over all orientations, a convex body of surface area A projects A/4.
    """
    return total_surface_area_m2 / 4.0


def orbital_speed(altitude_m):
    """Circular orbital speed at a given altitude above the WGS-84 equator [m/s]."""
    return math.sqrt(MU_EARTH / (R_EARTH + altitude_m))
