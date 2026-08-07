"""Config parsing/validation, geometry invariants, and derived quantities for
the 78 V boundary-demonstration stage (same deck as the capstone, re-pinned here at the
new operating point)."""

from pathlib import Path

import numpy as np
import pytest
import yaml

from helpers import ConfigError, analytic_capacitance, load_config

CONFIG = Path(__file__).resolve().parents[1] / "config.yaml"


def _raw():
    return yaml.safe_load(CONFIG.read_text())


def _write(tmp_path, raw):
    p = tmp_path / "c.yaml"
    p.write_text(yaml.safe_dump(raw, sort_keys=False))
    return p


# ----------------------------------------------------------------------
# baseline derivations (reference values from the contactor deck itself)
# ----------------------------------------------------------------------

def test_load_baseline():
    cfg = load_config(CONFIG)
    assert cfg.stage_id == "capstone.ucurve_floor"
    assert cfg.V_GAP == 78.0
    assert cfg.i_beam == pytest.approx(0.840e-3)


def test_grid_snaps_to_contactor_values():
    cfg = load_config(CONFIG)
    assert (cfg.nr, cfg.nz) == (200, 440)
    assert cfg.rmax == pytest.approx(0.030)
    assert cfg.zmin == pytest.approx(-0.030)
    assert cfg.zmax == pytest.approx(0.036)


def test_dt_is_beam_cfl():
    cfg = load_config(CONFIG)
    assert cfg.dt == pytest.approx(7.754e-12, rel=1e-3)
    assert cfg.cfl == pytest.approx(0.3, rel=1e-6)
    assert cfg.wpe * cfg.dt < 0.2


def test_max_steps_floored_to_diag_period():
    cfg = load_config(CONFIG)
    assert cfg.max_steps % cfg.diag_period == 0
    # within one diag period of the contactor's raw count
    assert 0 <= cfg._max_steps_raw - cfg.max_steps < cfg.diag_period


def test_reservoir_shell():
    cfg = load_config(CONFIG)
    assert cfg.R_res == pytest.approx(0.0225)


def test_plasma_matches_collector_row():
    cfg = load_config(CONFIG)
    assert cfg.lamD * 1e3 == pytest.approx(1.965, abs=0.01)
    assert cfg.n0 == pytest.approx(1.627e12)
    assert cfg.ion_mass_me == 400.0


def test_child_langmuir_scale():
    cfg = load_config(CONFIG)
    # 78 V over the 4.7 mm gap through the 0.5 mm spot -> ~0.057 mA scale;
    # the fixed-thrust command deliberately exceeds the validated 1.46
    # emission-ceiling ratio -- the excursion IS the measurement
    # (../UCURVE_PLAN.md, pre-registered)
    assert cfg.I_CL * 1e3 == pytest.approx(0.0572, rel=5e-3)
    assert cfg.i_beam / cfg.I_CL == pytest.approx(14.69, rel=1e-2)


def test_analytic_capacitance_scale():
    # 4*pi*eps0*r_p for the 5 mm can -> ~0.556 pF (C-calibration sanity band)
    assert analytic_capacitance(5.0e-3) * 1e12 == pytest.approx(0.5563, rel=1e-3)


def test_effective_config_roundtrips(tmp_path):
    cfg = load_config(CONFIG)
    frozen = cfg.effective_config()
    p = tmp_path / "config_used.yaml"
    p.write_text(yaml.safe_dump(frozen, sort_keys=False))
    again = load_config(p)
    assert again.effective_config() == frozen
    assert again.max_steps == cfg.max_steps and again.dt == cfg.dt


# ----------------------------------------------------------------------
# geometry invariants + region classification
# ----------------------------------------------------------------------

def test_geometry_derived_planes():
    g = load_config(CONFIG).geometry()
    assert g.d_gap == pytest.approx(4.7e-3)
    assert g.z_emit == pytest.approx(-4.3e-3)
    assert g.r_cath_out - g.r_cath == pytest.approx(2 * g.dx)  # insulation gap


def test_region_masks_classify_and_are_disjoint():
    g = load_config(CONFIG).geometry()
    # points: cathode centre, lid ring, outer wall, floor annulus, free space
    r = np.array([0.0005, 0.003, 0.0048, 0.0030, 0.0002])
    z = np.array([-0.0047, 0.0003, -0.002, -0.0047, 0.0])
    m = g.regions(r, z)
    assert m["cathode"].tolist() == [True, False, False, False, False]
    assert m["lid"].tolist() == [False, True, False, False, False]
    assert m["wall"].tolist() == [False, False, True, False, False]
    assert m["floor_ann"].tolist() == [False, False, False, True, False]
    # cathode never overlaps a BODY region (the >=2*dx separation at work)
    body = m["wall"] | m["lid"] | m["floor_ann"]
    assert not np.any(m["cathode"] & body)


def test_potential_string_has_two_nodes():
    g = load_config(CONFIG).geometry()
    s = g.potential_string(16.0, -184.0)
    assert "16" in s and "-184" in s
    assert s.count(">0.5") == 2          # exactly two node selectors


def test_implicit_function_mentions_all_conductors():
    g = load_config(CONFIG).geometry()
    f = g.implicit_function()
    # 4 conductor primitives unioned by 3 max(); disk = 2 min(), rings = 3 each
    assert f.count("max(") == 3
    assert f.count("min(") == 11


# ----------------------------------------------------------------------
# config rejection
# ----------------------------------------------------------------------

def test_reject_unmigrated_groups(tmp_path):
    for group in ("probe", "shroud", "fields"):
        raw = _raw()
        raw[group] = {"enabled": True}
        with pytest.raises(ConfigError):
            load_config(_write(tmp_path, raw))


def test_reject_positive_cathode_offset(tmp_path):
    raw = _raw(); raw["electrical"]["cathode_offset"] = 200.0
    with pytest.raises(ConfigError):
        load_config(_write(tmp_path, raw))


def test_reject_gun_before_supply(tmp_path):
    raw = _raw(); raw["beam"]["t_on"] = 50.0e-9  # < t_supply 100 ns
    with pytest.raises(ConfigError):
        load_config(_write(tmp_path, raw))


def test_reject_unresolved_lid_hole(tmp_path):
    raw = _raw(); raw["geometry"]["r_slit"] = 0.5e-3  # dx > r_slit/5
    with pytest.raises(ConfigError):
        load_config(_write(tmp_path, raw))


def test_reject_emission_spot_wider_than_cathode(tmp_path):
    raw = _raw(); raw["geometry"]["emit_radius"] = 1.8e-3  # > r_cathode 1.5
    with pytest.raises(ConfigError):
        load_config(_write(tmp_path, raw))


def test_reject_coarse_grid(tmp_path):
    raw = _raw(); raw["numerics"]["dx"] = 3.0e-3  # > lambda_D
    with pytest.raises(ConfigError):
        load_config(_write(tmp_path, raw))


def test_reject_scenario():
    with pytest.raises(ConfigError):
        load_config(CONFIG, scenario="anything")
