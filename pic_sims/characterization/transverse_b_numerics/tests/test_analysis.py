"""Analysis math on exact synthetic trajectories (no WarpX)."""

from pathlib import Path

import numpy as np
import pytest

import analyze
import ladder_contract as lc
from helpers import load_config

STAGE_DIR = Path(__file__).resolve().parents[1]
CONFIG = STAGE_DIR / "config.yaml"
POLICY = STAGE_DIR / "acceptance.yaml"
ME, E, CC = analyze.ME, analyze.E, analyze.CC


def _exact_gyro(cfg, n=300):
    t = np.arange(n) * cfg.dt
    w = cfg.omega_c
    p = cfg.gamma0 * ME * cfg.v0
    r = cfg.r_gyro
    # electron in Bx > 0 launched along +z rotates toward -y
    return dict(t=t, x=np.zeros(n), y=cfg.y0 - r * (1 - np.cos(w * t)),
                z=cfg.z0 + r * np.sin(w * t), px=np.zeros(n),
                py=-p * np.sin(w * t), pz=p * np.cos(w * t),
                gamma=np.full(n, cfg.gamma0))


def test_gyro_metrics_exact_on_closed_form():
    for scn in ("gyro_1x", "gyro_10x"):
        cfg = load_config(CONFIG, scenario=scn)
        m = analyze.gyro_metrics(cfg, _exact_gyro(cfg))
        assert m["omega_ratio"] == pytest.approx(1.0, abs=1e-9)
        assert m["rg_ratio"] == pytest.approx(1.0, abs=1e-6)
        assert m["ke_drift"] == 0.0


def test_exb_metrics_exact_on_cycloid():
    cfg = load_config(CONFIG, scenario="exb_10x")
    n = cfg.max_steps
    t = np.arange(n) * cfg.dt
    w = cfg.omega_c
    vd = cfg.v_exb
    rl = vd / w
    tr = dict(t=t, x=np.zeros(n), y=cfg.y0 + vd * t - rl * np.sin(w * t),
              z=cfg.z0 + rl * (1 - np.cos(w * t)), px=np.zeros(n),
              py=np.zeros(n), pz=np.zeros(n), gamma=np.ones(n))
    m = analyze.exb_metrics(cfg, tr)
    assert m["vd_ratio"] == pytest.approx(1.0, abs=1e-9)
    assert m["vz_over_vd"] == pytest.approx(0.0, abs=1e-9)
    assert m["gyroperiods"] == pytest.approx(3.0, abs=0.01)


def test_policy_passes_on_exact_values_and_fails_closed():
    per = {"gyro_1x": {"omega_ratio": 1.0, "rg_ratio": 1.0, "ke_drift": 0.0},
           "gyro_10x": {"omega_ratio": 1.0, "rg_ratio": 1.0, "ke_drift": 0.0},
           "exb_10x": {"vd_ratio": 1.0, "vz_over_vd": 0.0}}
    verdict = lc.evaluate_gates(analyze.build_metrics(per), lc.load_policy(POLICY))
    assert verdict.status == lc.V_PASS
    per["gyro_10x"]["rg_ratio"] = 1.02
    verdict = lc.evaluate_gates(analyze.build_metrics(per), lc.load_policy(POLICY))
    assert verdict.status == lc.V_FAIL
    del per["exb_10x"]
    verdict = lc.evaluate_gates(analyze.build_metrics(per), lc.load_policy(POLICY))
    assert verdict.status == lc.V_ERROR and verdict.exit_code == 2


def test_trace_parser(tmp_path):
    red = tmp_path / "reducedfiles"; red.mkdir()
    cols = ["step()", "time(s)", "x_mean(m)", "y_mean(m)", "z_mean(m)", "px_mean(kg*m/s)",
            "py_mean(kg*m/s)", "pz_mean(kg*m/s)", "gamma_mean()", "charge(C)"]
    hdr = "#" + " ".join(f"[{i}]{c}" for i, c in enumerate(cols)) + "\n"
    rows = "".join(f"{i} {i*1e-11} 0 {i*1e-4} {i*2e-4} 0 1e-25 7e-24 1.0003 -1.6e-19\n"
                   for i in range(20))
    (red / "beam_relevant.txt").write_text(hdr + rows)
    tr = analyze.load_trace(tmp_path)
    assert tr["t"].shape == (20,) and tr["y"][3] == pytest.approx(3e-4)
