"""Analysis math + OML/containment policy wiring on synthetic fixtures."""

import dataclasses
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
    cfg = dataclasses.replace(cfg, max_steps=3 * sp)
    # the 3rd dump has no hits from either species and must still appear as
    # a recorded zero bin, not disappear from the grid (plan section 10).
    scraped = {
        ELECTRONS: (np.array([sp, 2 * sp]), np.array([2.0, 2.0]), np.array([0., 0.])),
        IONS: (np.array([2 * sp]), np.array([1.0]), np.array([0.])),
    }
    steps, hist = analyze.current_history(cfg, scraped)
    assert list(steps) == [sp, 2 * sp, 3 * sp]
    assert hist[IONS][0] == 0.0
    assert hist[ELECTRONS][0] == pytest.approx(2.0 * scc.e / (sp * dt))
    assert hist[ELECTRONS][2] == 0.0 and hist[IONS][2] == 0.0  # wholly silent dump kept, not dropped


def _metrics(**over):
    base = dict(electron_current_over_oml=0.85, far_density_e_over_n0=1.0,
                quasineutrality=0.0, edge_phi_max_V=0.1)
    base.update(over)
    return {k: lc.Metric.measure(k, v, "-") for k, v in base.items()}


def test_deeper_barrier_floor_0p80_passes():
    # +10 V floor is relaxed to 0.80 (deeper barrier than +3 V).
    verdict = lc.evaluate_gates(_metrics(electron_current_over_oml=0.82),
                                lc.load_policy(POLICY))
    assert verdict.status == lc.V_PASS


def test_clipped_sheath_is_the_gate_to_watch():
    # The +10 V sheath reaching the boundary must fail containment.
    verdict = lc.evaluate_gates(_metrics(edge_phi_max_V=0.9),
                                lc.load_policy(POLICY))
    assert verdict.status == lc.V_FAIL


def test_far_density_looser_tolerance_here():
    # far-density tol is 0.06 for this larger domain; 0.05 deviation still passes.
    verdict = lc.evaluate_gates(_metrics(far_density_e_over_n0=1.05),
                                lc.load_policy(POLICY))
    assert verdict.status == lc.V_PASS
