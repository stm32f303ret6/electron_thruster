"""Config parsing/validation, per-scenario voltage resolution, and
study/effective hashing for the voltage-bracket gun."""

from pathlib import Path

import pytest
import yaml

import ladder_contract as lc
from helpers import STAGE_ID, ConfigError, load_config, scenario_names

CONFIG = Path(__file__).resolve().parents[1] / "config.yaml"


def test_scenario_names():
    assert scenario_names(CONFIG) == [
        "A_200v_anchor_drive", "B_300v_ceiling_drive",
        "C_ucurve_overperveance"]


def test_study_requires_scenario_selection():
    with pytest.raises(ConfigError):
        load_config(CONFIG)  # no scenario


def test_reject_unknown_scenario():
    with pytest.raises(ConfigError):
        load_config(CONFIG, scenario="Z_nope")


def test_resolve_scenario_voltages_and_currents():
    a = load_config(CONFIG, scenario="A_200v_anchor_drive")
    b = load_config(CONFIG, scenario="B_300v_ceiling_drive")
    c = load_config(CONFIG, scenario="C_ucurve_overperveance")
    assert a.v_cathode == pytest.approx(-200.0)
    assert b.v_cathode == pytest.approx(-300.0)
    assert c.v_cathode == pytest.approx(-92.4)
    assert a.beam_current == pytest.approx(3.42e-4)   # the anchor command
    assert b.beam_current == pytest.approx(6.30e-4)   # the ceiling command
    assert c.beam_current == pytest.approx(6.01e-4)   # the ucurve_left_arm command
    # the aperture is fixed: the axis under study is V, not the hole
    assert a.hole_radius == b.hole_radius == c.hole_radius == pytest.approx(1.4e-3)


def test_all_scenarios_share_study_hash():
    hashes = {lc.config_sha256(load_config(CONFIG, scenario=n).study_config())
              for n in scenario_names(CONFIG)}
    assert len(hashes) == 1  # every scenario carries the same source study


def test_effective_configs_differ_between_scenarios():
    a = load_config(CONFIG, scenario="A_200v_anchor_drive")
    b = load_config(CONFIG, scenario="B_300v_ceiling_drive")
    assert (lc.config_sha256(a.effective_config())
            != lc.config_sha256(b.effective_config()))


def test_frozen_config_roundtrips(tmp_path):
    c = load_config(CONFIG, scenario="C_ucurve_overperveance")
    frozen = c.effective_config()
    p = tmp_path / "config_used.yaml"
    p.write_text(yaml.safe_dump(frozen, sort_keys=False))
    reloaded = load_config(p)  # frozen mode, no scenario arg
    assert reloaded.scenario == "C_ucurve_overperveance"
    assert reloaded.v_cathode == pytest.approx(-92.4)  # voltage survives freezing
    assert reloaded.beam_current == pytest.approx(c.beam_current)
    assert reloaded.effective_config() == frozen
    assert reloaded.study_config() is None  # a frozen scenario has no study


def test_frozen_config_rejects_wrong_scenario_arg(tmp_path):
    a = load_config(CONFIG, scenario="A_200v_anchor_drive")
    p = tmp_path / "config_used.yaml"
    p.write_text(yaml.safe_dump(a.effective_config(), sort_keys=False))
    with pytest.raises(ConfigError):
        load_config(p, scenario="B_300v_ceiling_drive")


def test_child_langmuir_scales_with_voltage():
    # 1.9 mm gap over the 0.5 mm spot: ~507 uA at 100 V scaling as V^1.5
    # (holed_anode's own pinned scale).  A/B sit at the same 23.9% fraction;
    # C is past the ceiling -- the excursion IS the scenario.
    a = load_config(CONFIG, scenario="A_200v_anchor_drive")
    b = load_config(CONFIG, scenario="B_300v_ceiling_drive")
    c = load_config(CONFIG, scenario="C_ucurve_overperveance")
    assert a.child_langmuir_uA() == pytest.approx(507.0 * 2.0**1.5, rel=0.02)
    frac_a = a.beam_current * 1e6 / a.child_langmuir_uA()
    frac_b = b.beam_current * 1e6 / b.child_langmuir_uA()
    frac_c = c.beam_current * 1e6 / c.child_langmuir_uA()
    assert frac_a == pytest.approx(frac_b, rel=0.02)      # the bracket claim
    assert frac_a == pytest.approx(0.239, rel=0.02)
    assert frac_c > 1.30                                  # over the ceiling


def test_cfl_holds_at_the_fastest_scenario():
    b = load_config(CONFIG, scenario="B_300v_ceiling_drive")  # validate() ran
    import math
    from scipy import constants as scc
    v = math.sqrt(2.0 * scc.e * abs(b.v_cathode) / scc.m_e) + 4.0 * b.rms_velocity
    assert b.time_step * v / min(b.d_r, b.d_z) < 0.5


def test_reject_anode_outside_domain(tmp_path):
    raw = yaml.safe_load(CONFIG.read_text())
    raw["anode"]["z_front"] = raw["geometry"]["z_max"] * 2  # past the collector
    p = tmp_path / "c.yaml"
    p.write_text(yaml.safe_dump(raw, sort_keys=False))
    with pytest.raises(ConfigError):
        load_config(p, scenario="A_200v_anchor_drive")


def test_stage_id():
    assert STAGE_ID == "emitter.voltage_bracket"
