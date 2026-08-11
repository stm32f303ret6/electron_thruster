"""Config parsing/validation and OML references for the +3 V sphere."""

from pathlib import Path

import pytest
import yaml

from helpers import ConfigError, load_config

CONFIG = Path(__file__).resolve().parents[1] / "config.yaml"


def test_load_real_config():
    cfg = load_config(CONFIG)
    assert cfg.stage_id == "collector.biased_3v"
    assert cfg.bias == 3.0
    assert cfg.n_r == 96 and cfg.n_z == 192


def test_effective_config_roundtrips(tmp_path):
    cfg = load_config(CONFIG)
    frozen = cfg.effective_config()
    p = tmp_path / "config_used.yaml"
    p.write_text(yaml.safe_dump(frozen, sort_keys=False))
    assert load_config(p).effective_config() == frozen


def test_chi_and_oml_ceiling():
    cfg = load_config(CONFIG)
    assert cfg.chi == pytest.approx(26.4, rel=0.01)
    assert cfg.I_oml_e * 1e6 == pytest.approx(2.847, rel=2e-3)  # uA


def test_debye_and_a_over_debye_unchanged():
    cfg = load_config(CONFIG)  # same plasma as thermal
    assert cfg.debye * 1e3 == pytest.approx(1.965, abs=0.01)
    assert cfg.a_over_debye == pytest.approx(0.382, abs=0.005)


def test_domain_holds_several_debye():
    cfg = load_config(CONFIG)
    assert cfg.r_max / cfg.debye == pytest.approx(7.3, rel=0.02)


def test_reject_bad_stage_id(tmp_path):
    raw = yaml.safe_load(CONFIG.read_text())
    raw["stage_id"] = "collector.thermal"  # wrong stage for this folder's policy
    p = tmp_path / "c.yaml"
    p.write_text(yaml.safe_dump(raw, sort_keys=False))
    # helpers accepts any known collector id; the stage/policy match is enforced
    # in analyze.py.  Here we just confirm an UNKNOWN id is rejected.
    raw["stage_id"] = "collector.bogus"
    p.write_text(yaml.safe_dump(raw, sort_keys=False))
    with pytest.raises(ConfigError):
        load_config(p)


def test_reject_scenario():
    with pytest.raises(ConfigError):
        load_config(CONFIG, scenario="anything")
