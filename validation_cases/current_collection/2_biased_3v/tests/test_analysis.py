"""Analysis math + OML policy wiring on synthetic fixtures (no WarpX)."""

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
    scraped = {
        ELECTRONS: (np.array([sp, 2 * sp]), np.array([2.0, 2.0]), np.array([0., 0.])),
        IONS: (np.array([2 * sp]), np.array([1.0]), np.array([0.])),
    }
    steps, hist = analyze.current_history(cfg, scraped)
    assert list(steps) == [sp, 2 * sp]
    assert hist[IONS][0] == 0.0
    assert hist[ELECTRONS][0] == pytest.approx(2.0 * scc.e / (sp * dt))


def _metrics(**over):
    base = dict(electron_current_over_oml=0.93, far_density_e_over_n0=1.0,
                quasineutrality=0.0, edge_phi_max_V=0.0)
    base.update(over)
    return {k: lc.Metric.measure(k, v, "-") for k, v in base.items()}


def test_expected_oml_fraction_passes():
    # ~93% of the ceiling (the contactor cross-reference) is in [0.85, 1.05].
    verdict = lc.evaluate_gates(_metrics(), lc.load_policy(POLICY))
    assert verdict.status == lc.V_PASS


def test_above_ceiling_fails():
    # I_e > OML beyond noise signals an injection bug.
    verdict = lc.evaluate_gates(_metrics(electron_current_over_oml=1.20),
                                lc.load_policy(POLICY))
    assert verdict.status == lc.V_FAIL


def test_clipped_sheath_fails_containment():
    verdict = lc.evaluate_gates(_metrics(edge_phi_max_V=1.0),
                                lc.load_policy(POLICY))
    assert verdict.status == lc.V_FAIL


def test_missing_oml_metric_errors():
    m = _metrics()
    del m["electron_current_over_oml"]
    verdict = lc.evaluate_gates(m, lc.load_policy(POLICY))
    assert verdict.status == lc.V_ERROR and verdict.exit_code == 2
