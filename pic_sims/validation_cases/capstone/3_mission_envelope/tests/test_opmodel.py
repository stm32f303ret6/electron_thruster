"""The stage-local law formulas, pinned against closed forms.

This file is what makes the duplication of design_sims/opmodel.py safe: both
copies are checked against the same closed forms, so they cannot drift apart
silently.  (The run-time check that they have not is
``S__prediction_consistency`` in the policy.)
"""

import math

import pytest
from scipy import constants as scc

import opmodel

E, ME, KB, EPS0 = scc.e, scc.m_e, scc.k, scc.epsilon_0

# The committed anchor: capstone.floating_body's float200 reference.
ANCHOR = dict(n_e=1.627e12, Te_K=1318.8, v_drive=200.0, i_beam_A=0.342e-3,
              phi_V=16.976759467084637, f_nN=13.651711504702194,
              ke_eV=147.51960470219436, escape_pct=98.43638401253918,
              area_m2=3.29867228626928e-4)

# The frozen constants, as they appear in config.yaml's law_anchor block.
LAWS = dict(k=3.28652, ke_ledger=0.806016, f_esc=0.984364, beta=0.46158,
            area_m2=0.000329867, capacitance_F=5.56325e-13)


def test_kTe_eV_is_the_volts_one_kTe_is_worth():
    assert opmodel.kTe_eV(11604.518) == pytest.approx(1.0, rel=1e-4)
    assert opmodel.kTe_eV(1318.8) == pytest.approx(0.11365, rel=1e-3)


def test_chi_is_phi_over_kTe():
    assert opmodel.chi(50.0, 1000.0) == pytest.approx(
        50.0 / (KB * 1000.0 / E), rel=1e-12)


def test_thermal_current_matches_the_kinetic_formula():
    n, te, a = 1e12, 1500.0, 3.3e-4
    want = n * E * a * math.sqrt(KB * te / (2.0 * math.pi * ME))
    assert opmodel.thermal_current_A(n, te, a) == pytest.approx(want, rel=1e-12)


def test_thermal_current_scales_as_n_times_sqrt_Te():
    base = opmodel.thermal_current_A(1e12, 1000.0, 3.3e-4)
    assert opmodel.thermal_current_A(2e12, 1000.0, 3.3e-4) == pytest.approx(2 * base)
    assert opmodel.thermal_current_A(1e12, 4000.0, 3.3e-4) == pytest.approx(2 * base)


def test_collection_law_and_its_inverse_round_trip():
    for phi in (1.0, 26.35, 50.0, 200.0):
        i_ret = opmodel.return_current_A(phi, 1e12, 1500.0, LAWS["beta"],
                                         LAWS["area_m2"])
        back = opmodel.phi_for_escape_current_V(i_ret, 1e12, 1500.0,
                                                LAWS["beta"], LAWS["area_m2"])
        assert back == pytest.approx(phi, rel=1e-10)


def test_at_plasma_potential_the_body_collects_beta_times_the_thermal_current():
    """chi = 0 is the calibration point of the (1+chi) form."""
    i_the = opmodel.thermal_current_A(1e12, 1500.0, LAWS["area_m2"])
    got = opmodel.return_current_A(0.0, 1e12, 1500.0, LAWS["beta"], LAWS["area_m2"])
    assert got == pytest.approx(LAWS["beta"] * i_the, rel=1e-12)


def test_hot_electrons_lower_the_ceiling_at_fixed_potential():
    """At chi >> 1 the ceiling goes as n/sqrt(Te), not n*sqrt(Te). The sign that
    is easy to get backwards, so both opmodels pin it."""
    def ceiling(te):
        return opmodel.return_current_A(50.0, 1e12, te, LAWS["beta"],
                                        LAWS["area_m2"])
    assert ceiling(4000.0) / ceiling(1000.0) == pytest.approx(0.5, rel=0.01)


def test_thrust_is_zero_once_the_float_eats_the_whole_gap():
    assert opmodel.thrust_nN(1.0, 200.0, 200.0, LAWS["k"], LAWS["ke_ledger"]) == 0.0
    assert opmodel.thrust_nN(1.0, 200.0, 250.0, LAWS["k"], LAWS["ke_ledger"]) == 0.0


def test_child_langmuir_scales_as_v_to_the_three_halves():
    a = opmodel.child_langmuir_A(100.0, 4.7e-3, 0.5e-3)
    b = opmodel.child_langmuir_A(400.0, 4.7e-3, 0.5e-3)
    assert b / a == pytest.approx(8.0, rel=1e-12)


def test_settle_time_is_C_phi_over_I():
    assert opmodel.settle_time_s(50.0, 1e-4, 5.56325e-13) == pytest.approx(
        5.56325e-13 * 50.0 / 1e-4, rel=1e-12)
    assert math.isinf(opmodel.settle_time_s(50.0, 0.0, 5.56325e-13))


# ----------------------------------------------------------------------
# the anchor: these formulas must reproduce the constants they were fitted from
# ----------------------------------------------------------------------

def test_measured_constants_reproduce_the_frozen_anchor():
    got = opmodel.measured_constants(
        f_beam_nN=ANCHOR["f_nN"], phi_body_V=ANCHOR["phi_V"],
        escape_fraction_pct=ANCHOR["escape_pct"],
        exhaust_ke_eV=ANCHOR["ke_eV"], i_beam_A=ANCHOR["i_beam_A"],
        v_drive=ANCHOR["v_drive"], n_e=ANCHOR["n_e"], Te_K=ANCHOR["Te_K"],
        area_m2=ANCHOR["area_m2"])
    assert got["k_meas"] == pytest.approx(LAWS["k"], rel=1e-5)
    assert got["ke_ledger_meas"] == pytest.approx(LAWS["ke_ledger"], rel=1e-5)
    assert got["f_esc_meas"] == pytest.approx(LAWS["f_esc"], rel=1e-5)
    assert got["beta_meas"] == pytest.approx(LAWS["beta"], rel=1e-4)
    assert got["chi_meas"] == pytest.approx(149.4, rel=1e-3)


def test_predict_reproduces_the_anchor_float():
    """Feed the model the anchor run's own inputs; it must return its output."""
    got = opmodel.predict(
        n_e=ANCHOR["n_e"], Te_K=ANCHOR["Te_K"], v_drive=ANCHOR["v_drive"],
        i_beam_A=ANCHOR["i_beam_A"], k=LAWS["k"], ke_ledger=LAWS["ke_ledger"],
        f_esc=LAWS["f_esc"], beta=LAWS["beta"], area_m2=LAWS["area_m2"])
    assert got["phi_body_V"] == pytest.approx(ANCHOR["phi_V"], rel=2e-3)
    assert got["f_beam_nN"] == pytest.approx(ANCHOR["f_nN"], rel=2e-3)
    assert got["exhaust_ke_eV"] == pytest.approx(ANCHOR["ke_eV"], rel=2e-3)


def test_predict_and_measured_constants_are_mutual_inverses():
    """Predict a point, then invert it: the constants must come back."""
    pred = opmodel.predict(n_e=5e11, Te_K=2000.0, v_drive=250.0, i_beam_A=2e-4,
                           k=LAWS["k"], ke_ledger=LAWS["ke_ledger"],
                           f_esc=LAWS["f_esc"], beta=LAWS["beta"],
                           area_m2=LAWS["area_m2"])
    back = opmodel.measured_constants(
        f_beam_nN=pred["f_beam_nN"], phi_body_V=pred["phi_body_V"],
        escape_fraction_pct=LAWS["f_esc"] * 100.0,
        exhaust_ke_eV=pred["exhaust_ke_eV"], i_beam_A=2e-4, v_drive=250.0,
        n_e=5e11, Te_K=2000.0, area_m2=LAWS["area_m2"])
    assert back["k_meas"] == pytest.approx(LAWS["k"], rel=1e-10)
    assert back["ke_ledger_meas"] == pytest.approx(LAWS["ke_ledger"], rel=1e-10)
    assert back["beta_meas"] == pytest.approx(LAWS["beta"], rel=1e-10)


# The two scenarios, at their PREDICTED floats. The gate's whole leverage comes
# from how far apart in chi these are.
_SCN = ((2.138e12, 1528.54, 26.3503361014), (1.972e11, 1504.87, 49.9999486881))
_GATE = 0.2231          # acceptance.yaml collection_law_form_holds_across_chi


def _beta_spread_for_exponent(exponent: float) -> float:
    """Invert two synthetic measurements -- generated from ``(1+chi)**exponent``
    -- using the (1+chi) form, and return the resulting |ln(beta_A/beta_B)|."""
    betas = []
    for n_e, Te_K, phi in _SCN:
        i_the = opmodel.thermal_current_A(n_e, Te_K, LAWS["area_m2"])
        i_ret = LAWS["beta"] * i_the * (1.0 + opmodel.chi(phi, Te_K)) ** exponent
        got = opmodel.measured_constants(
            f_beam_nN=1.0, phi_body_V=phi,
            escape_fraction_pct=LAWS["f_esc"] * 100.0, exhaust_ke_eV=200.0,
            i_beam_A=i_ret / LAWS["f_esc"], v_drive=300.0, n_e=n_e, Te_K=Te_K,
            area_m2=LAWS["area_m2"])
        betas.append(got["beta_meas"])
    return abs(math.log(betas[0] / betas[1]))


def test_the_right_law_form_gives_no_spread_at_all():
    assert _beta_spread_for_exponent(1.0) == pytest.approx(0.0, abs=1e-12)


def test_the_gate_catches_a_sheath_limited_collection_law():
    """The failure mode this gate hunts.

    The archived femtosat f1b record found the OML-style form off by ~5x at
    r/lambda_D ~ 9 -- collection had gone sheath-limited, where the enhancement
    is much weaker than linear.  A sqrt-like exponent must be visible.
    """
    assert _beta_spread_for_exponent(0.5) > _GATE
    assert _beta_spread_for_exponent(1.6) > _GATE


def test_the_gates_leverage_is_exactly_what_the_readme_claims():
    """HONEST LIMIT, pinned so the README and the policy cannot drift from it.

    Inverting a ``(1+chi)**p`` law with the ``(1+chi)`` form gives
    ``beta_meas ~ (1+chi)**(p-1)``, so the observable spread is exactly
    ``|p-1| * ln((1+chi_B)/(1+chi_A))``.  With this mission's chi = 200 and 386
    that log-lever is 0.654, so the gate detects

        |p - 1| > 0.2231 / 0.654 = 0.341

    and NOT a subtle one: a mild curvature (p = 0.8) passes.  That is a real
    limit of what two operating points 1.9x apart in (1+chi) can prove, and it
    is why the tolerance was derived FROM this lever rather than inherited.
    """
    chi_a = opmodel.chi(_SCN[0][2], _SCN[0][1])
    chi_b = opmodel.chi(_SCN[1][2], _SCN[1][1])
    lever = math.log((1.0 + chi_b) / (1.0 + chi_a))
    assert lever == pytest.approx(0.654, abs=0.01)

    min_detectable = _GATE / lever
    assert min_detectable == pytest.approx(0.341, abs=0.005)

    assert _beta_spread_for_exponent(0.8) < _GATE      # a mild error passes
    assert _beta_spread_for_exponent(1.0 - min_detectable * 1.05) > _GATE
    # the spread is exactly linear in the exponent error -- no fitting involved
    for p in (0.5, 0.8, 1.6):
        assert _beta_spread_for_exponent(p) == pytest.approx(
            abs(p - 1.0) * lever, rel=1e-9)


def test_the_tolerance_preserves_the_planned_discriminating_power():
    """The tolerance was scaled from the plan's, not loosened or invented.

    The plan specified ln(1.5) against a hypothetical chi pair of 224/727
    (lever 1.174), i.e. it intended to catch |p-1| > 0.345.  The real mission
    rows give roughly half that leverage, so the tolerance is scaled to keep the
    same intent.
    """
    planned_lever = math.log((1.0 + 727.0) / (1.0 + 224.0))
    planned_power = math.log(1.5) / planned_lever
    chi_a = opmodel.chi(_SCN[0][2], _SCN[0][1])
    chi_b = opmodel.chi(_SCN[1][2], _SCN[1][1])
    actual_lever = math.log((1.0 + chi_b) / (1.0 + chi_a))
    assert _GATE / actual_lever == pytest.approx(planned_power, abs=0.01)
