"""Config parsing/validation and analytic references for negative_cathode."""

from pathlib import Path

import pytest
import yaml

from helpers import ConfigError, load_config

CONFIG = Path(__file__).resolve().parents[1] / "config.yaml"


def test_load_real_config():
    cfg = load_config(CONFIG)
    assert cfg.stage_id == "emitter.negative_cathode"
    assert cfg.n_r == 40 and cfg.n_z == 80
    assert cfg.beam_current == pytest.approx(1.0e-5)


def test_effective_config_roundtrips(tmp_path):
    cfg = load_config(CONFIG)
    frozen = cfg.effective_config()
    p = tmp_path / "config_used.yaml"
    p.write_text(yaml.safe_dump(frozen, sort_keys=False))
    again = load_config(p)
    assert again.effective_config() == frozen


def _write(tmp_path, raw):
    p = tmp_path / "c.yaml"
    p.write_text(yaml.safe_dump(raw, sort_keys=False))
    return p


def _raw():
    return yaml.safe_load(CONFIG.read_text())


def test_reject_unknown_top_key(tmp_path):
    raw = _raw(); raw["bogus"] = 1
    with pytest.raises(ConfigError):
        load_config(_write(tmp_path, raw))


def test_reject_unknown_section_key(tmp_path):
    raw = _raw(); raw["geometry"]["oops"] = 1
    with pytest.raises(ConfigError):
        load_config(_write(tmp_path, raw))


def test_reject_missing_section(tmp_path):
    raw = _raw(); del raw["emission"]
    with pytest.raises(ConfigError):
        load_config(_write(tmp_path, raw))


def test_reject_indivisible_scrape_period(tmp_path):
    raw = _raw(); raw["numerics"]["max_steps"] = 4001
    with pytest.raises(ConfigError):
        load_config(_write(tmp_path, raw))


def test_reject_emission_radius_outside_domain(tmp_path):
    raw = _raw(); raw["emission"]["radius"] = raw["geometry"]["r_max"] * 2
    with pytest.raises(ConfigError):
        load_config(_write(tmp_path, raw))


def test_reject_scenario():
    with pytest.raises(ConfigError):
        load_config(CONFIG, scenario="anything")


def test_laplace_ramp_endpoints():
    cfg = load_config(CONFIG)
    assert cfg.laplace_ramp(cfg.z_min) == pytest.approx(cfg.v_cathode)
    assert cfg.laplace_ramp(cfg.z_max) == pytest.approx(cfg.v_collector)
    mid = 0.5 * (cfg.z_min + cfg.z_max)
    assert cfg.laplace_ramp(mid) == pytest.approx(
        0.5 * (cfg.v_cathode + cfg.v_collector))


def test_expected_collector_ke_is_9925ev():
    # Energy conservation from the emission plane -> ~99.25 eV (README anchor).
    cfg = load_config(CONFIG)
    assert cfg.expected_collector_ke_eV() == pytest.approx(99.25, abs=0.02)


def test_kt_launch_and_emit_plane():
    cfg = load_config(CONFIG)
    # per-axis launch temperature ~ 0.25 eV
    assert cfg.kt_launch_eV == pytest.approx(0.2508, abs=0.01)
    # emission plane one cell inside the cathode, strictly in the domain
    assert cfg.z_min < cfg.emit_z < cfg.z_max
    assert cfg.emit_z == pytest.approx(cfg.z_min + cfg.d_z)


def test_emitted_number_positive():
    cfg = load_config(CONFIG)
    assert cfg.emitted_number() == pytest.approx(
        (cfg.beam_current / 1.602176634e-19) * cfg.t_end, rel=1e-6)
