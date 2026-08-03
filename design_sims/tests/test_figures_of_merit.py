"""The figures of merit the thesis claim quotes.

These exist so a number in the README can never drift from `laws.yaml` or from
the committed measurements: every headline figure is pinned to a closed form
AND to the numerical path, and the two must agree.
"""

import json
import math
from pathlib import Path

import pytest
from scipy import constants as scc

import figures_of_merit as fom
import opmodel as om
from calibration import load_laws

LAWS = load_laws()
REPO_ROOT = Path(__file__).resolve().parents[2]
POINTS = fom.measured_points()


# ----------------------------------------------------------------------
# the closed forms == the numerical path
# ----------------------------------------------------------------------

@pytest.mark.parametrize("v,phi", [(200.0, 17.0), (300.0, 30.0), (300.0, 50.0),
                                   (100.0, 5.0)])
def test_eta_closed_form_matches_the_numerical_path(v, phi):
    """eta = f_esc*ke_ledger*(V-phi)/V, built from P_jet/P for a modelled point."""
    p = fom.modelled_point(v, phi, 0.5, LAWS, "x")
    want = fom.eta_closed_form(v, phi, LAWS.f_esc, LAWS.ke_ledger)
    assert p.eta == pytest.approx(want, rel=1e-12)


@pytest.mark.parametrize("v,phi", [(200.0, 17.0), (300.0, 30.0), (100.0, 5.0)])
def test_f_per_p_closed_form_matches_the_numerical_path(v, phi):
    p = fom.modelled_point(v, phi, 0.5, LAWS, "x")
    want = fom.f_per_p_closed_form(v, phi, LAWS.k, LAWS.ke_ledger)
    assert p.f_per_p_uN_per_W == pytest.approx(want, rel=1e-12)


def test_f_per_p_is_independent_of_current():
    """F and P are both linear in I, so their ratio is not a throttle knob.

    This is why the device owns a THRUST regime rather than a power regime:
    you cannot throttle your way to a better thrust-per-watt.
    """
    a = fom.modelled_point(300.0, 30.0, 0.1, LAWS, "a")
    b = fom.modelled_point(300.0, 30.0, 0.9, LAWS, "b")
    assert a.f_per_p_uN_per_W == pytest.approx(b.f_per_p_uN_per_W, rel=1e-12)
    assert a.eta == pytest.approx(b.eta, rel=1e-12)


def test_f_per_p_falls_as_one_over_sqrt_v():
    """The reason this device cannot scale up: a faster beam buys thrust more
    expensively, so F/P degrades as the drive voltage rises."""
    lo = fom.f_per_p_closed_form(100.0, 0.0, LAWS.k, LAWS.ke_ledger)
    hi = fom.f_per_p_closed_form(400.0, 0.0, LAWS.k, LAWS.ke_ledger)
    assert lo / hi == pytest.approx(2.0, rel=1e-12)


def test_eta_does_not_depend_on_the_collection_law():
    """The load-bearing separation after rung 9.

    eta and F/P contain f_esc, ke_ledger, k and (V - phi) -- and NO beta, no
    density, no temperature. Rung 9 falsified the collection law; these figures
    are untouched by that, because the runs measured phi directly rather than
    predicting it.
    """
    import inspect
    for fn in (fom.eta_closed_form, fom.f_per_p_closed_form):
        params = set(inspect.signature(fn).parameters)
        assert not params & {"beta", "n_e", "Te_K", "area_m2"}


# ----------------------------------------------------------------------
# the committed points
# ----------------------------------------------------------------------

def test_every_quoted_point_is_measured_not_modelled():
    assert len(POINTS) == 3
    for p in POINTS:
        assert p.source.startswith("measured"), p.label


def test_the_headline_bands_are_what_the_readme_claims():
    """eta ~ 0.7 (ion-thruster class) and F/P ~ 0.2 uN/W (~200x below ion).

    Both must be quoted together; a drift in either changes the claim.
    """
    etas = [p.eta for p in POINTS]
    fps = [p.f_per_p_uN_per_W for p in POINTS]
    assert 0.70 <= min(etas) and max(etas) <= 0.75
    assert 0.15 <= min(fps) and max(fps) <= 0.21
    # the claim's own framing: energy-efficient, thrust-per-watt poor
    assert min(etas) > 0.5
    assert max(fps) < 1.0


def test_f_per_p_is_two_to_three_orders_below_gridded_ion():
    """The 'why it only owns the nN slot' half of the claim, as a number."""
    fps = [p.f_per_p_uN_per_W for p in POINTS]
    assert 150 <= 30.0 / max(fps) <= 400        # vs the 30 uN/W end
    assert 200 <= 60.0 / max(fps) <= 500        # vs the 60 uN/W end


def test_measured_eta_agrees_with_the_closed_form_within_ke_ledger_drift():
    """The measured path uses the run's own exhaust KE; the closed form uses
    laws.yaml's ke_ledger. Rung 9 measured ke_ledger 0.6 % below the anchor, so
    the two agree to about that -- and no better, honestly."""
    for p in POINTS:
        want = fom.eta_closed_form(p.v_drive, p.phi_V, p.f_esc, LAWS.ke_ledger)
        assert p.eta == pytest.approx(want, rel=0.01), p.label


def test_momentum_and_energy_exhaust_speeds_agree():
    """F/mdot vs sqrt(2*e*KE/m_e): equal for a monoenergetic beam.

    The measured v_eff sits slightly BELOW the energy value because the beam has
    angular and thermal spread -- momentum is a vector, energy is not.
    """
    for p in POINTS:
        ratio = p.v_eff_km_s / p.v_from_energy_km_s
        assert 0.95 <= ratio <= 1.0, f"{p.label}: {ratio:.4f}"


def test_jet_power_never_exceeds_electrical_power():
    for p in POINTS:
        assert p.p_jet_mW < p.p_supply_mW
        assert 0.0 < p.eta < 1.0


def test_the_power_band_is_milliwatts():
    """'a power level the spacecraft's own skin can harvest' -- as a number."""
    for p in POINTS:
        assert 10.0 <= p.p_supply_mW <= 250.0


def test_points_are_read_from_committed_evidence():
    for rel in (fom.RUNG8, fom.RUNG9):
        path = REPO_ROOT / rel
        assert path.is_file(), rel
        doc = json.loads(path.read_text(encoding="utf-8"))
        assert doc["metrics"]


def test_a_missing_artifact_is_a_hard_error(monkeypatch):
    monkeypatch.setattr(fom, "RUNG8", "pic_sims/nope/metrics.json")
    with pytest.raises(SystemExit, match="missing committed evidence"):
        fom.measured_points()


def test_report_renders_in_both_forms():
    for md in (False, True):
        text = fom.render(POINTS, md)
        assert "eta" in text and "F/P" in text
        assert "zero" in fom.render(POINTS, md)
        land = fom.render_landscape(POINTS, md)
        assert "CONTEXT not measurement" in land
        assert "electrospray" in land
