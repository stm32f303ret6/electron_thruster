"""Config parsing/validation, scenario resolution, and study/effective hashing
for the holed electron gun."""

from pathlib import Path

import pytest
import yaml

import ladder_contract as lc
from helpers import STAGE_ID, ConfigError, load_config, scenario_names

CONFIG = Path(__file__).resolve().parents[1] / "config.yaml"


def test_scenario_names():
    assert scenario_names(CONFIG) == [
        "A_low_current_small_hole", "B_high_current_small_hole",
        "C_high_current_big_hole"]


def test_study_requires_scenario_selection():
    with pytest.raises(ConfigError):
        load_config(CONFIG)  # no scenario


def test_reject_unknown_scenario():
    with pytest.raises(ConfigError):
        load_config(CONFIG, scenario="Z_nope")


def test_resolve_scenario_currents():
    a = load_config(CONFIG, scenario="A_low_current_small_hole")
    b = load_config(CONFIG, scenario="B_high_current_small_hole")
    c = load_config(CONFIG, scenario="C_high_current_big_hole")
    assert a.beam_current == pytest.approx(1.0e-5)
    assert b.beam_current == pytest.approx(4.0e-4)
    assert c.hole_radius == pytest.approx(1.4e-3)
    assert b.hole_radius == pytest.approx(7.0e-4)


def test_all_scenarios_share_study_hash():
    hashes = {lc.config_sha256(load_config(CONFIG, scenario=n).study_config())
              for n in scenario_names(CONFIG)}
    assert len(hashes) == 1  # every scenario carries the same source study


def test_effective_configs_differ_between_scenarios():
    a = load_config(CONFIG, scenario="A_low_current_small_hole")
    b = load_config(CONFIG, scenario="B_high_current_small_hole")
    assert (lc.config_sha256(a.effective_config())
            != lc.config_sha256(b.effective_config()))


def test_frozen_config_roundtrips(tmp_path):
    a = load_config(CONFIG, scenario="A_low_current_small_hole")
    frozen = a.effective_config()
    p = tmp_path / "config_used.yaml"
    p.write_text(yaml.safe_dump(frozen, sort_keys=False))
    reloaded = load_config(p)  # frozen mode, no scenario arg
    assert reloaded.scenario == "A_low_current_small_hole"
    assert reloaded.beam_current == pytest.approx(a.beam_current)
    assert reloaded.effective_config() == frozen
    assert reloaded.study_config() is None  # a frozen scenario has no study


def test_frozen_config_rejects_wrong_scenario_arg(tmp_path):
    a = load_config(CONFIG, scenario="A_low_current_small_hole")
    p = tmp_path / "config_used.yaml"
    p.write_text(yaml.safe_dump(a.effective_config(), sort_keys=False))
    with pytest.raises(ConfigError):
        load_config(p, scenario="B_high_current_small_hole")


def test_child_langmuir_scale():
    a = load_config(CONFIG, scenario="A_low_current_small_hole")
    # 1.9 mm gap at 100 V over the 0.5 mm spot -> ~507 uA (README scale).
    assert a.child_langmuir_uA() == pytest.approx(507.0, rel=0.02)


def test_reject_anode_outside_domain(tmp_path):
    raw = yaml.safe_load(CONFIG.read_text())
    raw["anode"]["z_front"] = raw["geometry"]["z_max"] * 2  # past the collector
    p = tmp_path / "c.yaml"
    p.write_text(yaml.safe_dump(raw, sort_keys=False))
    with pytest.raises(ConfigError):
        load_config(p, scenario="A_low_current_small_hole")


def test_stage_id():
    assert STAGE_ID == "emitter.holed_anode"
