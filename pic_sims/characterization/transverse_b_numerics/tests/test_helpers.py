"""Config derivations, and the one cross-stage invariant: this grid and step
ARE the measurement deck's (loaded through its own helpers under a private
module name -- stages never import each other's code otherwise)."""

import importlib.util
import math
import sys
from pathlib import Path

import pytest
import yaml

from helpers import ConfigError, load_config, scenario_names

STAGE_DIR = Path(__file__).resolve().parents[1]
CONFIG = STAGE_DIR / "config.yaml"
MEASUREMENT = STAGE_DIR.parent / "magnetized_transverse"
SCENARIOS = ("gyro_1x", "gyro_10x", "exb_10x")


def _measurement_config():
    spec = importlib.util.spec_from_file_location(
        "m2_measurement_helpers", MEASUREMENT / "helpers.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod            # dataclasses resolve annotations here
    spec.loader.exec_module(mod)
    return mod.load_config(MEASUREMENT / "config.yaml", scenario="transverse_10x")


def test_scenarios_declared_in_order():
    assert tuple(scenario_names(CONFIG)) == SCENARIOS


def test_grid_and_step_are_the_measurement_decks():
    m = _measurement_config()
    n = load_config(CONFIG, scenario="gyro_10x")
    assert (n.nx, n.ny, n.nz) == (m.nx, m.ny, m.nz)
    assert n.dx == pytest.approx(m.dx) and n.zmin == pytest.approx(m.zmin)
    assert n.xmax == pytest.approx(m.xmax) and n.zmax == pytest.approx(m.zmax)
    assert n.dt == pytest.approx(m.dt, rel=1e-4)
    assert n.ke_eV == pytest.approx(m.ke_inject_eV)
    assert n.Bx_T == pytest.approx(m.Bx_T)


def test_closed_forms():
    g1 = load_config(CONFIG, scenario="gyro_1x")
    g10 = load_config(CONFIG, scenario="gyro_10x")
    ex = load_config(CONFIG, scenario="exb_10x")
    assert g1.r_gyro == pytest.approx(1.44, rel=0.01)
    assert g10.r_gyro * 1e3 == pytest.approx(144.2, rel=0.01)
    assert g10.T_c * 1e9 == pytest.approx(119.0, rel=0.01)
    assert ex.v_exb == pytest.approx(1.0e5)
    assert ex.phi_hi_z == pytest.approx(-30.0 * 0.072)
    assert ex.t_run / ex.T_c == pytest.approx(3.0, abs=0.01)
    assert g1.max_steps == math.ceil(8.0e-9 / g1.dt)


def test_particle_stays_inside_the_box_for_t_run():
    for scn in ("gyro_1x", "gyro_10x"):
        c = load_config(CONFIG, scenario=scn)
        # the arc: z advance r sin(wt) and y deflection r(1 - cos(wt)) from z0
        wt = c.omega_c * c.t_run
        assert c.z0 + c.r_gyro * math.sin(wt) < c.zmax - 2 * c.dx
        assert c.r_gyro * (1 - math.cos(wt)) < c.ymax - 2 * c.dx
    ex = load_config(CONFIG, scenario="exb_10x")
    assert ex.y0 + ex.v_exb * ex.t_run + 2 * ex.v_exb / ex.omega_c < ex.ymax - 2 * ex.dx


def test_frozen_roundtrip(tmp_path):
    for scn in SCENARIOS:
        cfg = load_config(CONFIG, scenario=scn)
        p = tmp_path / f"{scn}.yaml"
        p.write_text(yaml.safe_dump(cfg.effective_config(), sort_keys=False))
        again = load_config(p)
        assert again.effective_config() == cfg.effective_config()
        assert again.study_config() is None


def test_rejections(tmp_path):
    raw = yaml.safe_load(CONFIG.read_text())
    raw["scenarios"][0]["Bx_T"] = 0.0
    p = tmp_path / "c.yaml"; p.write_text(yaml.safe_dump(raw))
    with pytest.raises(ConfigError):
        load_config(p, scenario="gyro_1x")
    raw = yaml.safe_load(CONFIG.read_text())
    raw["scenarios"][0]["z0"] = 0.5
    p.write_text(yaml.safe_dump(raw))
    with pytest.raises(ConfigError):
        load_config(p, scenario="gyro_1x")
    with pytest.raises(ConfigError):
        load_config(CONFIG)
