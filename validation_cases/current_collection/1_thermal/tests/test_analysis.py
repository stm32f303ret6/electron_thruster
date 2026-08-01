"""Analysis math + policy wiring on synthetic fixtures (no WarpX/openPMD)."""

from pathlib import Path

import numpy as np
import pytest
from scipy import constants as scc

import analyze
import ladder_contract as lc
from helpers import ELECTRONS, IONS, load_config

STAGE_DIR = Path(__file__).resolve().parents[1]
CONFIG = STAGE_DIR / "config.yaml"
POLICY = STAGE_DIR / "acceptance.yaml"


def test_current_history_zero_bins():
    cfg = load_config(CONFIG)
    sp, dt = cfg.scrape_period, cfg.time_step
    # electrons hit at both dumps; ions only at the 2nd.
    scraped = {
        ELECTRONS: (np.array([sp, 2 * sp]), np.array([2.0, 2.0]), np.array([0., 0.])),
        IONS: (np.array([2 * sp]), np.array([1.0]), np.array([0.])),
    }
    steps, hist = analyze.current_history(cfg, scraped)
    assert list(steps) == [sp, 2 * sp]
    assert hist[IONS][0] == 0.0  # ion zero bin present, not dropped
    assert hist[ELECTRONS][0] == pytest.approx(2.0 * scc.e / (sp * dt))


def test_steady_stats_window():
    cfg = load_config(CONFIG)  # steady_window_frac = 0.4
    I = np.arange(10, dtype=float)
    mean, err, n, i0 = analyze.steady_stats(cfg, I)
    assert i0 == 6 and n == 4
    assert mean == pytest.approx(np.mean([6, 7, 8, 9]))


def test_sheath_radius_interpolates():
    r = np.array([0.0, 1.0, 2.0, 3.0])
    phi = np.array([1.0, 1.0, 0.0, 0.0])  # crosses 0.5 between r=1 and r=2
    assert analyze.sheath_radius(r, phi, 0.5) == pytest.approx(1.5)


def test_sheath_radius_none_when_below_threshold():
    r = np.array([0.0, 1.0, 2.0])
    phi = np.array([0.1, 0.1, 0.1])
    assert np.isnan(analyze.sheath_radius(r, phi, 0.5))


def _metrics(**over):
    base = dict(electron_current_over_th=1.0, ion_current_over_th=1.0,
                species_ratio_over_theory=1.0, far_density_e_over_n0=1.0,
                quasineutrality=0.0, edge_phi_max_V=0.0)
    base.update(over)
    return {k: lc.Metric.measure(k, v, "-") for k, v in base.items()}


def test_ideal_metrics_pass_thermal_policy():
    verdict = lc.evaluate_gates(_metrics(), lc.load_policy(POLICY))
    assert verdict.status == lc.V_PASS


def test_edge_sheath_fails_containment():
    verdict = lc.evaluate_gates(_metrics(edge_phi_max_V=0.5),
                                lc.load_policy(POLICY))
    assert verdict.status == lc.V_FAIL


def test_missing_ratio_metric_errors():
    m = _metrics()
    del m["species_ratio_over_theory"]  # required gate -> ERROR, exit 2
    verdict = lc.evaluate_gates(m, lc.load_policy(POLICY))
    assert verdict.status == lc.V_ERROR and verdict.exit_code == 2
