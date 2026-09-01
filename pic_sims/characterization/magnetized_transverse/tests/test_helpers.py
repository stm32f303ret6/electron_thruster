"""Config parsing/validation, geometry invariants, and derived quantities for
the transverse-B 3D deck -- checked against the anchor's numbers where the
deck carries them verbatim."""

import math
from pathlib import Path

import numpy as np
import pytest
import yaml

import ladder_contract as lc
from helpers import ConfigError, analytic_capacitance, load_config, scenario_names

CONFIG = Path(__file__).resolve().parents[1] / "config.yaml"
SCENARIOS = ("b0_control", "transverse_1x", "transverse_10x")


def _raw():
    return yaml.safe_load(CONFIG.read_text())


def _write(tmp_path, raw):
    p = tmp_path / "c.yaml"
    p.write_text(yaml.safe_dump(raw, sort_keys=False))
    return p


# ----------------------------------------------------------------------
# the study and its scenarios
# ----------------------------------------------------------------------

def test_scenarios_declared_in_order():
    assert tuple(scenario_names(CONFIG)) == SCENARIOS


def test_source_study_requires_a_scenario():
    with pytest.raises(ConfigError):
        load_config(CONFIG)
    with pytest.raises(ConfigError):
        load_config(CONFIG, scenario="nope")


def test_control_is_unmagnetized_and_axis_is_bx():
    b0 = load_config(CONFIG, scenario="b0_control")
    x1 = load_config(CONFIG, scenario="transverse_1x")
    x10 = load_config(CONFIG, scenario="transverse_10x")
    assert b0.Bx_T is None and b0.omega_ce == 0.0
    assert x1.Bx_T == pytest.approx(3.0e-5)
    assert x10.Bx_T == pytest.approx(3.0e-4)
    # the scenarios differ ONLY in the field: same shared physics hash
    shared = [dict(c.effective_config()) for c in (b0, x1, x10)]
    for s in shared:
        s.pop("scenario"); s.pop("field")
    assert lc.config_sha256(shared[0]) == lc.config_sha256(shared[1]) == lc.config_sha256(shared[2])
    # and share one study hash (the cohort compatibility key)
    assert len({lc.config_sha256(c.study_config()) for c in (b0, x1, x10)}) == 1


def test_gyro_scales_match_the_plan():
    x1 = load_config(CONFIG, scenario="transverse_1x")
    x10 = load_config(CONFIG, scenario="transverse_10x")
    assert x1.r_gyro_beam == pytest.approx(1.44, rel=0.02)          # m, 164.5 eV at 30 uT
    assert x1.r_gyro_thermal_e * 1e3 == pytest.approx(26.8, rel=0.02)  # mm
    assert x10.r_gyro_beam * 1e3 == pytest.approx(144, rel=0.02)     # mm
    assert x10.r_gyro_thermal_e * 1e3 == pytest.approx(2.68, rel=0.02)
    assert x10.omega_ce * x10.dt < 0.01                              # Boris well inside


# ----------------------------------------------------------------------
# what is carried verbatim from the anchor
# ----------------------------------------------------------------------

def test_anchor_plasma_row_and_beam_current():
    cfg = load_config(CONFIG, scenario="b0_control")
    assert cfg.n0 == pytest.approx(1.627e12)
    assert cfg.ion_mass_me == 400.0
    assert cfg.lamD * 1e3 == pytest.approx(1.965, abs=0.01)
    assert cfg.kTe_eV * 1e3 == pytest.approx(113.6, rel=1e-3)
    assert cfg.i_beam == pytest.approx(0.342e-3)
    assert cfg.t_on == pytest.approx(150e-9) and cfg.t_end == pytest.approx(800e-9)
    assert (cfg.r_probe, cfg.z_bot, cfg.z_top) == (5.0e-3, -5.0e-3, 0.5e-3)


def test_source_energy_is_the_anchor_lid_energy():
    """KE_lid = anchor exhaust (147.52 eV) + anchor float (16.98 V)."""
    cfg = load_config(CONFIG, scenario="b0_control")
    assert cfg.ke_inject_eV == pytest.approx(147.52 + 16.98, abs=0.05)
    assert cfg.v_inject == pytest.approx(7.607e6, rel=1e-3)
    # the source flux carries exactly i_beam over the emission disk
    assert cfg.flux0 * math.pi * cfg.emit_radius**2 * 1.602176634e-19 == pytest.approx(cfg.i_beam)


# ----------------------------------------------------------------------
# grid / step derivations
# ----------------------------------------------------------------------

def test_grid_snaps_to_box():
    cfg = load_config(CONFIG, scenario="b0_control")
    assert (cfg.nx, cfg.ny, cfg.nz) == (64, 64, 72)
    assert cfg.xmax == pytest.approx(0.032) and cfg.ymax == pytest.approx(0.032)
    assert cfg.zmin == pytest.approx(-0.030) and cfg.zmax == pytest.approx(0.042)
    assert cfg.n_cells == 64 * 64 * 72
    assert cfg.lamD / cfg.dx > 1.9                    # Debye length resolved


def test_dt_is_beam_cfl():
    cfg = load_config(CONFIG, scenario="b0_control")
    assert cfg.dt == pytest.approx(3.671e-11, rel=1e-3)
    assert cfg.cfl == pytest.approx(0.3, rel=1e-6)
    assert cfg.wpe * cfg.dt < 0.2


def test_max_steps_floored_to_diag_period():
    cfg = load_config(CONFIG, scenario="b0_control")
    assert cfg.max_steps % cfg.diag_period == 0
    assert 0 <= cfg._max_steps_raw - cfg.max_steps < cfg.diag_period
    assert cfg.max_steps * cfg.dt == pytest.approx(800e-9, rel=0.05)


def test_reservoir_shell_clears_the_body():
    cfg = load_config(CONFIG, scenario="b0_control")
    xh, yh, zlo, zhi = cfg.inner_box
    assert xh == pytest.approx(0.7 * cfg.xmax)
    assert zlo < cfg.z_bot and cfg.geometry().z_emit < zhi
    assert cfg.r_probe < xh and cfg.r_probe < yh


def test_analytic_capacitance_scale():
    assert analytic_capacitance(5.0e-3) * 1e12 == pytest.approx(0.5563, rel=1e-3)


def test_effective_config_roundtrips(tmp_path):
    for scn in SCENARIOS:
        cfg = load_config(CONFIG, scenario=scn)
        frozen = cfg.effective_config()
        p = tmp_path / f"{scn}.yaml"
        p.write_text(yaml.safe_dump(frozen, sort_keys=False))
        again = load_config(p)
        assert again.effective_config() == frozen
        assert again.scenario == scn and again.Bx_T == cfg.Bx_T
        assert again.max_steps == cfg.max_steps and again.dt == cfg.dt
        assert again.study_config() is None          # frozen: no study table
        with pytest.raises(ConfigError):
            load_config(p, scenario="another")


# ----------------------------------------------------------------------
# geometry
# ----------------------------------------------------------------------

def test_geometry_solid_body_and_source_plane():
    g = load_config(CONFIG, scenario="b0_control").geometry()
    assert g.z_emit == pytest.approx(0.5e-3 + 2 * 1.0e-3)
    f = g.implicit_function()
    assert "sqrt(x*x+y*y)" in f and f.count("min(") == 2
    assert g.potential_string(17.25) == "17.25"
    x = np.array([0.0, 0.0, 0.0, 0.0049, 0.006])
    y = np.array([0.0, 0.0, 0.0, 0.0, 0.0])
    z = np.array([-0.002, 0.0025, -0.006, -0.002, -0.002])
    assert g.inside(x, y, z).tolist() == [True, False, False, True, False]


# ----------------------------------------------------------------------
# config rejection
# ----------------------------------------------------------------------

def _variant(tmp_path, mutate):
    raw = _raw()
    mutate(raw)
    return load_config(_write(tmp_path, raw), scenario="b0_control")


def test_reject_unknown_keys(tmp_path):
    with pytest.raises(ConfigError):
        _variant(tmp_path, lambda r: r.__setitem__("probe", {"enabled": True}))
    with pytest.raises(ConfigError):
        _variant(tmp_path, lambda r: r["beam"].__setitem__("flux_correction", 1.0))


def test_reject_gun_after_end(tmp_path):
    with pytest.raises(ConfigError):
        _variant(tmp_path, lambda r: r["run"].__setitem__("t_end", 100e-9))


def test_reject_coarse_grid(tmp_path):
    with pytest.raises(ConfigError):
        _variant(tmp_path, lambda r: r["numerics"].__setitem__("dx", 2.5e-3))


def test_reject_source_wider_than_body(tmp_path):
    with pytest.raises(ConfigError):
        _variant(tmp_path, lambda r: r["beam"].__setitem__("emit_radius", 6.0e-3))


def test_reject_shell_touching_body(tmp_path):
    with pytest.raises(ConfigError):
        _variant(tmp_path, lambda r: r["reservoir"].__setitem__("frac", 0.1))


def test_reject_oversized_or_zero_field(tmp_path):
    def big(r):
        r["scenarios"][1]["Bx_T"] = 0.5
    def zero(r):
        r["scenarios"][1]["Bx_T"] = 0.0
    raw = _raw(); big(raw)
    with pytest.raises(ConfigError):
        load_config(_write(tmp_path, raw), scenario="transverse_1x")
    raw = _raw(); zero(raw)
    with pytest.raises(ConfigError):
        load_config(_write(tmp_path, raw), scenario="transverse_1x")


def test_reject_duplicate_or_malformed_scenarios(tmp_path):
    raw = _raw(); raw["scenarios"].append({"name": "b0_control", "Bx_T": None})
    with pytest.raises(ConfigError):
        load_config(_write(tmp_path, raw), scenario="b0_control")
    raw = _raw(); raw["scenarios"][0] = {"name": "b0_control"}
    with pytest.raises(ConfigError):
        load_config(_write(tmp_path, raw), scenario="b0_control")
