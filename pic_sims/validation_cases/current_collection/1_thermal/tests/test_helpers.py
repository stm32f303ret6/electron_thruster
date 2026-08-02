"""Config parsing/validation, Debye length, and thermal-current references."""

from pathlib import Path

import pytest
import yaml

from helpers import ConfigError, load_config

CONFIG = Path(__file__).resolve().parents[1] / "config.yaml"


def test_load_real_config():
    cfg = load_config(CONFIG)
    assert cfg.stage_id == "collector.thermal"
    assert cfg.bias == 0.0
    assert cfg.n_r == 80 and cfg.n_z == 160


def test_effective_config_roundtrips(tmp_path):
    cfg = load_config(CONFIG)
    frozen = cfg.effective_config()
    p = tmp_path / "config_used.yaml"
    p.write_text(yaml.safe_dump(frozen, sort_keys=False))
    assert load_config(p).effective_config() == frozen


def _raw():
    return yaml.safe_load(CONFIG.read_text())


def _write(tmp_path, raw):
    p = tmp_path / "c.yaml"
    p.write_text(yaml.safe_dump(raw, sort_keys=False))
    return p


def test_reject_unknown_key(tmp_path):
    raw = _raw(); raw["plasma"]["oops"] = 1
    with pytest.raises(ConfigError):
        load_config(_write(tmp_path, raw))


def test_reject_bad_stage_id(tmp_path):
    raw = _raw(); raw["stage_id"] = "collector.not_a_stage"
    with pytest.raises(ConfigError):
        load_config(_write(tmp_path, raw))


def test_reject_indivisible_scrape(tmp_path):
    raw = _raw(); raw["numerics"]["max_steps"] = 50001
    with pytest.raises(ConfigError):
        load_config(_write(tmp_path, raw))


def test_reject_scenario():
    with pytest.raises(ConfigError):
        load_config(CONFIG, scenario="anything")


def test_debye_length_1p965mm():
    cfg = load_config(CONFIG)
    assert cfg.debye * 1e3 == pytest.approx(1.965, abs=0.01)
    assert cfg.a_over_debye == pytest.approx(0.382, abs=0.005)


def test_thermal_currents_match_readme():
    cfg = load_config(CONFIG)
    assert cfg.I_th_e * 1e6 == pytest.approx(0.10393, rel=1e-3)  # uA
    assert cfg.I_th_i * 1e9 == pytest.approx(4.379, rel=2e-3)    # nA
    assert cfg.species_ratio_theory == pytest.approx(23.74, rel=1e-3)


def test_oml_equals_thermal_at_zero_bias():
    cfg = load_config(CONFIG)
    assert cfg.chi == 0.0
    assert cfg.I_oml_e == pytest.approx(cfg.I_th_e)  # (1 + max(chi,0)) = 1


def test_cells_per_debye():
    cfg = load_config(CONFIG)
    assert cfg.debye / cfg.d_r == pytest.approx(13.1, rel=0.02)
