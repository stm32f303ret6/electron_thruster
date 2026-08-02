"""Analysis math on small synthetic fixtures (no WarpX, no openPMD).

Only the pure numeric kernels are exercised here; the openPMD reads and figure
writing are covered by an end-to-end run, not by unit tests."""

import dataclasses

import numpy as np
import pytest
from scipy import constants as scc

import analyze
from helpers import load_config
from pathlib import Path

CONFIG = Path(__file__).resolve().parents[1] / "config.yaml"


def test_ke_eV_nonrelativistic():
    # A 100 eV electron: p = sqrt(2 m E).  ke_eV must invert it.
    E = 100.0
    p = np.sqrt(2 * scc.m_e * E * scc.e)
    ke = analyze.ke_eV(np.array([0.0]), np.array([0.0]), np.array([p]))
    assert ke[0] == pytest.approx(100.0, rel=1e-4)


def test_steady_mean_last_40pct():
    I = np.arange(10, dtype=float)  # 0..9
    mean, i0 = analyze.steady_mean(I)
    assert i0 == 6                      # int(0.6*10)
    assert mean == pytest.approx(np.mean([6, 7, 8, 9]))


def test_steady_mean_empty():
    mean, i0 = analyze.steady_mean(np.array([]))
    assert np.isnan(mean)


def test_current_history_includes_zero_bins():
    """A dump step where a boundary caught nothing must appear as 0, not vanish
    (collector hits at both steps keep both dump steps in the grid); a dump
    step with no hits from any boundary must also survive as an all-zero row
    (plan section 10 rule 1 -- the grid comes from config, not from hits)."""
    cfg = load_config(CONFIG)
    cfg = dataclasses.replace(cfg, max_steps=3 * cfg.scrape_period)
    # three dump steps: collector caught weight at the first two; cathode only
    # at the 2nd; the 3rd dump has no hits from any boundary.
    it = np.array([cfg.scrape_period, cfg.scrape_period,
                   2 * cfg.scrape_period])
    bnd = np.array(["zhi", "zhi", "zlo"])
    w = np.array([1.0, 1.0, 3.0])
    s = {"it": it, "bnd": bnd, "w": w,
         "px": np.zeros(3), "py": np.zeros(3), "pz": np.zeros(3)}
    steps, hist = analyze.current_history(s, cfg)
    assert list(steps) == [cfg.scrape_period, 2 * cfg.scrape_period,
                           3 * cfg.scrape_period]
    # cathode is zero at the first dump step (present, not dropped)
    assert hist["cathode"][0] == 0.0
    # collector current at step 1 = 2*e / (scrape_period*dt)
    expected = 2.0 * scc.e / (cfg.scrape_period * cfg.time_step)
    assert hist["collector"][0] == pytest.approx(expected)
    # the wholly silent 3rd dump survives as a zero row, not a dropped bin
    assert hist["collector"][2] == 0.0 and hist["cathode"][2] == 0.0


def test_current_history_empty():
    """Even when nothing was ever scraped, the grid comes from config, not
    from data -- every expected dump step is still present, valued zero."""
    cfg = load_config(CONFIG)
    s = {k: np.array([]) for k in ("it", "bnd", "w", "px", "py", "pz")}
    steps, hist = analyze.current_history(s, cfg)
    expected_n = cfg.max_steps // cfg.scrape_period
    assert steps.size == expected_n
    assert hist["collector"].size == expected_n
    assert np.all(hist["collector"] == 0.0)
