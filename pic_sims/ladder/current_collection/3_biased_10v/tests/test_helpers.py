"""Config parsing/validation and OML references for the +10 V sphere."""

from pathlib import Path

import pytest
import yaml

from helpers import ConfigError, load_config

CONFIG = Path(__file__).resolve().parents[1] / "config.yaml"


def test_load_real_config():
    cfg = load_config(CONFIG)
    assert cfg.stage_id == "collector.biased_10v"
    assert cfg.bias == 10.0
    assert cfg.n_r == 144 and cfg.n_z == 288


def test_effective_config_roundtrips(tmp_path):
    cfg = load_config(CONFIG)
    frozen = cfg.effective_config()
    p = tmp_path / "config_used.yaml"
    p.write_text(yaml.safe_dump(frozen, sort_keys=False))
    assert load_config(p).effective_config() == frozen


def test_chi_and_oml_ceiling():
    cfg = load_config(CONFIG)
    assert cfg.chi == pytest.approx(88.0, rel=0.01)
    assert cfg.I_oml_e * 1e6 == pytest.approx(9.249, rel=2e-3)  # uA


def test_largest_domain_for_thick_sheath():
    cfg = load_config(CONFIG)
    assert cfg.r_max / cfg.debye == pytest.approx(11.0, rel=0.02)


def test_debye_unchanged_same_plasma():
    cfg = load_config(CONFIG)
    assert cfg.debye * 1e3 == pytest.approx(1.965, abs=0.01)
    assert cfg.a_over_debye == pytest.approx(0.382, abs=0.005)


def test_reject_unknown_stage_id(tmp_path):
    raw = yaml.safe_load(CONFIG.read_text())
    raw["stage_id"] = "collector.bogus"
    p = tmp_path / "c.yaml"
    p.write_text(yaml.safe_dump(raw, sort_keys=False))
    with pytest.raises(ConfigError):
        load_config(p)


def test_reject_scenario():
    with pytest.raises(ConfigError):
        load_config(CONFIG, scenario="anything")
