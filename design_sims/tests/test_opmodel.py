"""The laws and the solver, checked against closed forms and the committed anchor.

The point of these tests is that every number the design side emits is either an
exact algebraic consequence of a PIC measurement or a closed form -- so a
regression here is a real change of belief, not a tolerance drift.
"""

import math

import pytest

import opmodel as om
from calibration import load_laws

LAWS = load_laws()
CONS = om.Constraints()

# The committed reference operating point (capstone.floating_body float200).
ANCHOR = dict(n_e=1.627e12, Te_K=1318.8, v_drive=200.0, i_beam_A=0.342e-3,
              phi_V=16.976759467084637, f_nN=13.651711504702194,
              ke_eV=147.51960470219436, escape_pct=98.43638401253918)


# ======================================================================
# closed forms
# ======================================================================

def test_ideal_k_matches_the_analytic_thrust_per_amp():
    """k_ideal must equal the no-loss slope m_e*v/e re-expressed in nN/(mA*sqrt(eV))."""
    for v in (100.0, 200.0, 300.0, 800.0):
        direct = om.thrust_nN_ideal(1.0, v)
        via_k = LAWS.k_ideal * 1.0 * math.sqrt(v)
        # laws.yaml stores 6 significant figures, so this is a 1e-6 comparison
        assert direct == pytest.approx(via_k, rel=1e-5)
    assert LAWS.k_ideal == pytest.approx(3.3721, abs=1e-3)


def test_thrust_and_its_inverse_round_trip():
    for i_mA in (0.05, 0.342, 1.0):
        f = om.thrust_nN(i_mA, 200.0, 17.0, LAWS.k, LAWS.ke_ledger)
        back = om.current_for_thrust_mA(f, 200.0, 17.0, LAWS.k, LAWS.ke_ledger)
        assert back == pytest.approx(i_mA, rel=1e-12)


def test_phi_and_current_round_trip_through_the_collection_law():
    for phi in (1.0, 17.0, 50.0, 120.0):
        i_beam = om.beam_current_at_phi_A(phi, 1e12, 1500.0, LAWS.beta,
                                          LAWS.area_m2, LAWS.f_esc)
        back = om.phi_for_escape_current_V(LAWS.f_esc * i_beam, 1e12, 1500.0,
                                           LAWS.beta, LAWS.area_m2)
        assert back == pytest.approx(phi, rel=1e-10)


def test_thermal_current_scales_as_n_times_sqrt_Te():
    base = om.thermal_current_A(1e12, 1000.0, LAWS.area_m2)
    assert om.thermal_current_A(2e12, 1000.0, LAWS.area_m2) == pytest.approx(2 * base)
    assert om.thermal_current_A(1e12, 4000.0, LAWS.area_m2) == pytest.approx(2 * base)


def test_collection_ceiling_is_monotone_in_n_and_phi():
    """The two levers that move it in the obvious direction."""
    def ceiling(n, te, phi):
        return om.beam_current_at_phi_A(phi, n, te, LAWS.beta, LAWS.area_m2,
                                        LAWS.f_esc)

    assert ceiling(2e12, 1500.0, 50.0) == pytest.approx(
        2.0 * ceiling(1e12, 1500.0, 50.0))                             # density
    assert ceiling(1e12, 1500.0, 80.0) > ceiling(1e12, 1500.0, 50.0)   # potential


def test_hot_electrons_LOWER_the_ceiling_at_fixed_potential():
    """The sign that is easy to get backwards, so it is pinned here.

    I_the grows as sqrt(Te), but the (1 + e*phi/kTe) pull weakens as 1/Te, and at
    the chi ~ 150-400 this design runs at the second term dominates. Net: at
    fixed phi the ceiling goes as n_e/sqrt(Te). Hot dayside electrons are HARDER
    to collect per unit density, not easier.
    """
    def ceiling(te):
        return om.beam_current_at_phi_A(50.0, 1e12, te, LAWS.beta, LAWS.area_m2,
                                        LAWS.f_esc)
    assert ceiling(4000.0) < ceiling(1000.0)
    assert ceiling(4000.0) / ceiling(1000.0) == pytest.approx(0.5, rel=0.01)


def test_the_zero_potential_ceiling_still_grows_with_Te():
    """The other limit, for contrast: a body AT plasma potential collects the
    bare thermal flux, which does go as n*sqrt(Te)."""
    hot = om.thermal_current_A(1e12, 4000.0, LAWS.area_m2)
    cold = om.thermal_current_A(1e12, 1000.0, LAWS.area_m2)
    assert hot / cold == pytest.approx(2.0, rel=1e-12)


def test_child_langmuir_scales_as_v_to_the_three_halves():
    a = om.child_langmuir_A(100.0, CONS.d_gap, CONS.emit_radius)
    b = om.child_langmuir_A(400.0, CONS.d_gap, CONS.emit_radius)
    assert b / a == pytest.approx(8.0, rel=1e-12)


def test_thrust_peak_matches_a_brute_force_maximum():
    """The closed-form interior maximum is what makes feasibility exact."""
    n_e, Te, v = 5e11, 1200.0, 250.0
    i_star, f_star = om.thrust_peak(v, n_e, Te, LAWS)
    a, b = om._coefficients(n_e, Te, LAWS)
    best = max(
        om.thrust_nN(i * 1e3, v, a * i - b, LAWS.k, LAWS.ke_ledger)
        for i in [k * i_star * 2.0 / 5000 for k in range(1, 5000)])
    assert f_star == pytest.approx(best, rel=1e-4)
    assert f_star >= best


def test_settle_time_grows_as_density_falls():
    """tau ~ 1/n_e is why the night rows need the guard."""
    def tau(n):
        i = om.beam_current_at_phi_A(50.0, n, 1500.0, LAWS.beta, LAWS.area_m2,
                                     LAWS.f_esc)
        return om.settle_time_s(50.0, i, LAWS.capacitance_F)
    assert tau(1e11) == pytest.approx(10.0 * tau(1e12), rel=1e-9)


def test_analytic_capacitance_is_the_isolated_sphere():
    assert om.analytic_capacitance_F(5e-3) == pytest.approx(0.556e-12, rel=1e-3)


# ======================================================================
# the anchor reproduces itself
# ======================================================================

def test_anchor_constants_reproduce_the_committed_laws():
    """Invert the laws at the reference point; get laws.yaml back."""
    got = om.anchor_constants(
        f_beam_nN=ANCHOR["f_nN"], phi_body_V=ANCHOR["phi_V"],
        escape_fraction_pct=ANCHOR["escape_pct"], exhaust_ke_eV=ANCHOR["ke_eV"],
        i_beam_A=ANCHOR["i_beam_A"], v_drive_V=ANCHOR["v_drive"],
        n_e=ANCHOR["n_e"], Te_K=ANCHOR["Te_K"], area_m2=LAWS.area_m2)
    assert got["k"] == pytest.approx(LAWS.k, rel=1e-5)
    assert got["ke_ledger"] == pytest.approx(LAWS.ke_ledger, rel=1e-5)
    assert got["f_esc"] == pytest.approx(LAWS.f_esc, rel=1e-5)
    assert got["beta"] == pytest.approx(LAWS.beta, rel=1e-5)
    # the derived intermediates the plan quotes
    assert got["i_the_A"] == pytest.approx(4.85e-6, rel=2e-3)
    assert got["chi"] == pytest.approx(149.4, rel=2e-3)


def test_solver_reproduces_the_anchor_operating_point():
    """Ask for exactly the thrust the reference produced; get its (I, phi) back."""
    p = om.solve_at_voltage(ANCHOR["n_e"], ANCHOR["Te_K"], ANCHOR["f_nN"] * 1e-9,
                            ANCHOR["v_drive"], LAWS, CONS)
    assert p.feasible
    assert p.i_beam_mA == pytest.approx(0.342, rel=2e-4)
    assert p.phi_V == pytest.approx(ANCHOR["phi_V"], rel=2e-3)
    assert p.f_nN == pytest.approx(ANCHOR["f_nN"], rel=1e-6)
    assert p.exhaust_ke_eV == pytest.approx(ANCHOR["ke_eV"], rel=2e-3)


def test_reference_run_sits_where_gamma_cl_max_says_it_may():
    """gamma_CL_max = 1.5 is justified by the reference drawing 1.46."""
    i_cl = om.child_langmuir_A(200.0, CONS.d_gap, CONS.emit_radius)
    assert ANCHOR["i_beam_A"] / i_cl == pytest.approx(1.457, rel=1e-3)
    assert ANCHOR["i_beam_A"] / i_cl < CONS.gamma_cl_max


# ======================================================================
# the solver's decision logic
# ======================================================================

def test_feasible_rows_pick_the_cheapest_voltage():
    """P ~ sqrt(V) at fixed thrust, so the cheapest feasible point is the lowest
    voltage that still clears every ceiling."""
    p = om.solve_operating_point(3e12, 1500.0, 5e-9, LAWS, CONS)
    assert p.feasible
    cheaper = [om.solve_at_voltage(3e12, 1500.0, 5e-9, v, LAWS, CONS)
               for v in (CONS.v_min, p.v_drive_V - 1.0)]
    assert all((not q.feasible) or q.p_supply_mW >= p.p_supply_mW - 1e-9
               for q in cheaper)


def test_infeasible_rows_report_a_deficit_and_a_binding_constraint():
    p = om.solve_operating_point(1e11, 900.0, 200e-9, LAWS, CONS)
    assert not p.feasible
    assert p.deficit_nN > 0
    assert p.binding in ("phi_max", "gamma_cl", "thrust_peak")
    assert p.v_drive_V == pytest.approx(CONS.v_max)   # every ceiling grows with V


def test_the_float_limit_binds_when_the_plasma_is_thin():
    p = om.solve_operating_point(2e11, 800.0, 100e-9, LAWS, CONS)
    assert p.binding == "phi_max"
    assert p.phi_V == pytest.approx(CONS.phi_max, rel=1e-6)


def test_the_emission_ceiling_binds_when_the_plasma_is_dense():
    p = om.solve_operating_point(3e12, 2500.0, 500e-9, LAWS, CONS)
    assert p.binding == "gamma_cl"
    assert p.i_over_i_cl == pytest.approx(CONS.gamma_cl_max, rel=1e-6)


def test_the_solution_never_violates_a_constraint():
    for n_e in (5e10, 5e11, 5e12):
        for Te in (800.0, 1500.0, 3000.0):
            for drag in (5e-9, 30e-9, 90e-9):
                p = om.solve_operating_point(n_e, Te, drag, LAWS, CONS)
                assert p.phi_V <= CONS.phi_max + 1e-6
                assert p.i_over_i_cl <= CONS.gamma_cl_max + 1e-9
                assert CONS.v_min - 1e-9 <= p.v_drive_V <= CONS.v_max + 1e-9
                assert p.exhaust_ke_eV > 0


def test_margin_scales_the_demand():
    strict = om.Constraints(margin=2.0)
    a = om.solve_at_voltage(3e12, 1500.0, 5e-9, 200.0, LAWS, CONS)
    b = om.solve_at_voltage(3e12, 1500.0, 5e-9, 200.0, LAWS, strict)
    assert b.f_required_nN == pytest.approx(2.0 * a.f_required_nN)
    assert b.i_beam_mA > a.i_beam_mA


def test_bad_plasma_rows_raise_rather_than_returning_nonsense():
    with pytest.raises(ValueError):
        om.solve_operating_point(0.0, 1500.0, 10e-9, LAWS, CONS)
    with pytest.raises(ValueError):
        om.solve_operating_point(1e12, -5.0, 10e-9, LAWS, CONS)


def test_constraints_reject_a_phi_max_above_v_min():
    """A float that can reach the supply voltage stalls the beam entirely."""
    with pytest.raises(ValueError, match="phi_max must stay below v_min"):
        om.Constraints(v_min=40.0, phi_max=50.0).validate()


# ======================================================================
# the mission rollup
# ======================================================================

class _Row:
    def __init__(self, n_e, Te_K, drag_N):
        self.n_e, self.Te_K, self.drag_N = n_e, Te_K, drag_N


def test_orbit_summary_closes_when_supply_beats_average_demand():
    rows = [_Row(3e12, 2000.0, 5e-9) for _ in range(10)]
    s = om.orbit_summary(rows, LAWS, CONS)
    assert s.closes_on_average
    assert s.duty_cycle_required < 1.0
    assert s.continuous_feasible_frac == 1.0


def test_orbit_summary_reports_failure_rather_than_rounding_it_away():
    rows = [_Row(1e11, 900.0, 200e-9) for _ in range(10)]
    s = om.orbit_summary(rows, LAWS, CONS)
    assert not s.closes_on_average
    assert s.duty_cycle_required > 1.0
    assert s.continuous_feasible_frac == 0.0


def test_orbit_summary_percentile_uses_nearest_rank():
    rows = [_Row(1e12, 1500.0, (i + 1) * 1e-9) for i in range(100)]
    s = om.orbit_summary(rows, LAWS, CONS)
    assert s.drag_p95_nN == pytest.approx(95.0)
    assert s.drag_max_nN == pytest.approx(100.0)
    assert s.n_rows == 100
