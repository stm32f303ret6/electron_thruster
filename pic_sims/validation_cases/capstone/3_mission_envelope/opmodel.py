#!/usr/bin/env python3
"""The design-model FORMULAS this stage validates -- and nothing else.

This is a deliberate, audited duplicate of the formulas in
``design_sims/opmodel.py``.  It exists so the stage is SELF-CONTAINED: it holds
the shapes of the laws but not a single one of their constants, which arrive
only through the stage's own frozen ``config.yaml`` (``law_anchor:``).

Why not import design_sims?  Because then the evidence would move whenever the
model moved.  A stage that read the live ``laws.yaml`` would re-validate itself
against whatever the design side currently believes, and a refit would silently
turn a FAIL into a PASS.  Freezing the constants into the run config and
duplicating only the formulas makes the coupling one-way and checkable: the
analysis recomputes the frozen ``predicted:`` block from the frozen constants,
and ``S__prediction_consistency`` FAILS if the two opmodels have drifted apart.

Every function here is pure and takes its constants explicitly.  No I/O, no
config, no numpy -- so ``tests/test_opmodel.py`` can pin it against closed forms
without any of the stage's machinery.
"""

from __future__ import annotations

import math

from scipy import constants as scc

E = scc.e
ME = scc.m_e
EPS0 = scc.epsilon_0
KB = scc.k


def kTe_eV(Te_K: float) -> float:
    """Electron temperature in eV."""
    return KB * Te_K / E


def chi(phi_V: float, Te_K: float) -> float:
    """Normalised body potential ``e*phi/kTe``."""
    return phi_V / kTe_eV(Te_K)


def thermal_current_A(n_e: float, Te_K: float, area_m2: float) -> float:
    """One-sided random thermal electron current ``n*e*A*sqrt(kTe/(2*pi*m_e))`` [A]."""
    return n_e * E * area_m2 * math.sqrt(KB * Te_K / (2.0 * math.pi * ME))


def return_current_A(phi_V: float, n_e: float, Te_K: float, beta: float,
                     area_m2: float) -> float:
    """Collection law: ``I_return = beta * I_the * (1 + e*phi/kTe)`` [A]."""
    return beta * thermal_current_A(n_e, Te_K, area_m2) * (1.0 + chi(phi_V, Te_K))


def phi_for_escape_current_V(i_escape_A: float, n_e: float, Te_K: float,
                             beta: float, area_m2: float) -> float:
    """Collection law inverted: the predicted floating potential [V].

    Steady state is a current balance -- what leaves as beam comes back as
    collected ambient electrons -- so this is where the body must sit.
    """
    i_the = thermal_current_A(n_e, Te_K, area_m2)
    if i_the <= 0.0:
        return float("inf")
    return kTe_eV(Te_K) * (i_escape_A / (beta * i_the) - 1.0)


def exhaust_ke_eV(v_drive: float, phi_V: float, ke_ledger: float) -> float:
    """Mean kinetic energy of the escaping beam [eV]."""
    return ke_ledger * (abs(v_drive) - phi_V)


def thrust_nN(i_mA: float, v_drive: float, phi_V: float, k: float,
              ke_ledger: float) -> float:
    """Thrust law: ``F[nN] = k * I[mA] * sqrt(KE[eV])``."""
    ke = exhaust_ke_eV(v_drive, phi_V, ke_ledger)
    return k * i_mA * math.sqrt(ke) if ke > 0.0 else 0.0


def settle_time_s(phi_V: float, i_beam_A: float, capacitance_F: float) -> float:
    """``tau ~ C*phi/I`` [s] -- how long the float takes to reach ``phi_V``."""
    if i_beam_A <= 0.0:
        return float("inf")
    return capacitance_F * phi_V / i_beam_A


def child_langmuir_A(v_drive: float, d_gap: float, emit_radius: float) -> float:
    """Planar Child-Langmuir current over the emission spot [A]. A SCALE, not a
    bound: the geometry is non-planar and the reference run draws 1.46x this."""
    j = (4.0 / 9.0) * EPS0 * math.sqrt(2.0 * E / ME) * abs(v_drive) ** 1.5 / d_gap ** 2
    return j * math.pi * emit_radius ** 2


# ----------------------------------------------------------------------
# forward prediction and its inverse -- the two directions the stage needs
# ----------------------------------------------------------------------

def predict(*, n_e: float, Te_K: float, v_drive: float, i_beam_A: float,
            k: float, ke_ledger: float, f_esc: float, beta: float,
            area_m2: float) -> dict:
    """What the design model says this operating point will do.

    The analysis recomputes the frozen ``predicted:`` block with exactly this
    function and exactly the frozen constants, so any disagreement is a real
    formula drift rather than a rounding allowance.
    """
    phi = phi_for_escape_current_V(f_esc * i_beam_A, n_e, Te_K, beta, area_m2)
    return {
        "phi_body_V": phi,
        "f_beam_nN": thrust_nN(i_beam_A * 1e3, v_drive, phi, k, ke_ledger),
        "exhaust_ke_eV": exhaust_ke_eV(v_drive, phi, ke_ledger),
    }


def measured_constants(*, f_beam_nN: float, phi_body_V: float,
                       escape_fraction_pct: float, exhaust_ke_eV: float,
                       i_beam_A: float, v_drive: float, n_e: float, Te_K: float,
                       area_m2: float) -> dict:
    """Invert the laws at a MEASURED point: the per-scenario refit outputs.

    Reported, never gated on their own -- but ``beta_meas`` from two scenarios at
    different chi is what the cross-scenario ``beta_log_spread`` gate tests, and
    that IS the law-form test proper.
    """
    ke_span = abs(v_drive) - phi_body_V
    i_mA = i_beam_A * 1e3
    f_esc = escape_fraction_pct / 100.0
    i_the = thermal_current_A(n_e, Te_K, area_m2)
    out = {
        "k_meas": (f_beam_nN / (i_mA * math.sqrt(exhaust_ke_eV))
                   if exhaust_ke_eV > 0.0 and i_mA > 0.0 else float("nan")),
        "ke_ledger_meas": (exhaust_ke_eV / ke_span if ke_span > 0.0 else float("nan")),
        "f_esc_meas": f_esc,
        "chi_meas": chi(phi_body_V, Te_K),
        "i_the_A": i_the,
    }
    denom = i_the * (1.0 + out["chi_meas"])
    out["beta_meas"] = (f_esc * i_beam_A / denom) if denom > 0.0 else float("nan")
    return out
