"""Config parsing and the floating-potential references (no WarpX)."""

import math
from pathlib import Path

import pytest
import yaml

from helpers import ConfigError, load_config

CONFIG = Path(__file__).resolve().parents[1] / "config.yaml"


def test_load_config_roundtrip():
    cfg = load_config(CONFIG)
    assert cfg.stage_id == "collector.floating"
    assert cfg.phi_init == 0.0
    assert cfg.probe_radius == pytest.approx(7.5e-4)


def test_shares_thermal_plasma_and_grid():
    """The whole point: same sphere, plasma, grid, dt as collector.thermal."""
    cfg = load_config(CONFIG)
    thermal = yaml.safe_load(
        (CONFIG.parents[1] / "1_thermal" / "config.yaml").read_text())
    assert cfg.n0 == float(thermal["plasma"]["n0"])
    assert cfg.Te_K == float(thermal["plasma"]["Te_K"])
    assert cfg.Ti_K == float(thermal["plasma"]["Ti_K"])
    assert cfg.ion_mass_me == float(thermal["plasma"]["ion_mass_me"])
    assert cfg.probe_radius == float(thermal["probe"]["radius"])
    assert cfg.r_max == float(thermal["geometry"]["r_max"])
    assert cfg.n_r == int(thermal["geometry"]["n_r"])
    assert cfg.time_step == float(thermal["numerics"]["time_step"])
    assert cfg.ppc == int(thermal["numerics"]["ppc"])


def test_thermal_ion_floating_potential():
    """phi_f = -kTe/e * ln(sqrt((mi/me)(Te/Ti))) = -0.360 V for this plasma."""
    cfg = load_config(CONFIG)
    assert cfg.species_ratio_theory == pytest.approx(23.737, rel=1e-3)
    assert cfg.phi_float_thermal_ion == pytest.approx(-0.360, abs=2e-3)


def test_oml_ion_floating_potential():
    """The OML-ion root of exp(phi/kTe)*R = 1 - phi/kTi is -0.213 V, and it
    must satisfy the balance equation to solver precision."""
    cfg = load_config(CONFIG)
    phi = cfg.phi_float_oml_ion
    assert phi == pytest.approx(-0.213, abs=2e-3)
    lhs = math.exp(phi / cfg.kTe_eV) * cfg.species_ratio_theory
    rhs = 1.0 - phi / cfg.kTi_eV
    assert lhs == pytest.approx(rhs, rel=1e-9)


def test_floating_potential_ordering():
    """OML-enhanced ion current needs less electron retardation, so the
    OML-ion answer is strictly less negative; both are below 0."""
    cfg = load_config(CONFIG)
    assert cfg.phi_float_thermal_ion < cfg.phi_float_oml_ion < 0.0


def test_anchors_inside_acceptance_bracket():
    """Both model anchors must sit inside the gate bracket [-0.40, -0.19]."""
    cfg = load_config(CONFIG)
    for phi in (cfg.phi_float_thermal_ion, cfg.phi_float_oml_ion):
        assert -0.40 < phi < -0.19


def test_analytic_capacitance_scale():
    cfg = load_config(CONFIG)
    # 4*pi*eps0*a for a 0.75 mm sphere = 83.4 fF
    assert cfg.analytic_capacitance == pytest.approx(83.4e-15, rel=1e-2)


def _mutated(tmp_path, mutate):
    raw = yaml.safe_load(CONFIG.read_text())
    mutate(raw)
    p = tmp_path / "mutated.yaml"
    p.write_text(yaml.safe_dump(raw))
    return p


def test_rejects_unknown_key(tmp_path):
    p = _mutated(tmp_path, lambda r: r["electrical"].__setitem__("bias", 3.0))
    with pytest.raises(ConfigError):
        load_config(p)


def test_rejects_missing_key(tmp_path):
    p = _mutated(tmp_path, lambda r: r["electrical"].__delitem__("phi_init"))
    with pytest.raises(ConfigError):
        load_config(p)


def test_rejects_indivisible_log_window(tmp_path):
    p = _mutated(tmp_path, lambda r: r["electrical"].__setitem__("log_every", 7))
    with pytest.raises(ConfigError):
        load_config(p)


def test_rejects_wrong_stage_id(tmp_path):
    p = _mutated(tmp_path,
                 lambda r: r.__setitem__("stage_id", "collector.thermal"))
    with pytest.raises(ConfigError):
        load_config(p)
