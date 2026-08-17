"""Config parsing/validation, geometry invariants, and derived quantities for
the chipsat capstone -- checked against the contactor's own derived numbers."""

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
    assert cfg.stage_id == "characterization.350V_400km_slender"
    assert cfg.V_GAP == 350.0
    assert cfg.i_beam == pytest.approx(0.793e-3)


def test_grid_snaps_to_contactor_values():
    cfg = load_config(CONFIG)
    assert (cfg.nr, cfg.nz) == (200, 608)
    assert cfg.rmax == pytest.approx(0.030)
    assert cfg.zmin == pytest.approx(-0.055)      # slender can: z_bot -30 mm
    assert cfg.zmax == pytest.approx(0.0362)     # snapped up by the grid


def test_dt_is_beam_cfl():
    cfg = load_config(CONFIG)
    assert cfg.dt == pytest.approx(3.859e-12, rel=1e-3)
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
    # 350 V over the 4.7 mm gap through the 0.5 mm spot -> ~0.543 mA scale
    assert cfg.I_CL * 1e3 == pytest.approx(0.5434, rel=5e-3)


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
    # 5 primitives (pedestal + bottom cap) unioned by 4 max()
    assert f.count("max(") == 4
    assert f.count("min(") == 13


# ----------------------------------------------------------------------
# cathode standoff (elongated cans; optional key, baseline-preserving)
# ----------------------------------------------------------------------

def _slender(tmp_path, standoff=4.7e-3, z_bot=-30.0e-3):
    raw = _raw()                     # this deck IS slender; standoff=None strips
    raw["geometry"]["z_bot"] = z_bot  # the key to reproduce the flawed attempt
    if standoff is not None:
        raw["geometry"]["cathode_standoff"] = standoff
    else:
        raw["geometry"].pop("cathode_standoff", None)
    return load_config(_write(tmp_path, raw))


def test_standoff_is_pinned_in_this_deck(tmp_path):
    """This deck's load-bearing line: the slender can keeps the SHORT design
    gap (the 2026-08-06 fix; without it the gun self-scrapes ~60x over I_CL)."""
    base = load_config(CONFIG)
    assert base.cathode_standoff == pytest.approx(4.7e-3)
    assert base.effective_config()["geometry"]["cathode_standoff"] == \
        pytest.approx(4.7e-3)
    g = base.geometry()
    assert g.z_floorb == pytest.approx(-5.0e-3)       # pedestal top assembly
    assert g.d_gap == pytest.approx(4.7e-3)


def test_standoff_pins_the_gun_gap_when_the_can_grows(tmp_path):
    """Lengthening the can 6x must grow the BODY, not the gun gap: I_CL ~ 1/d^2,
    so a stretched gap would put the commanded beam far over its ceiling."""
    stretched = _slender(tmp_path, standoff=None)     # the flawed first attempt
    assert stretched.d_gap == pytest.approx(29.7e-3)  # gap dragged along: wrong
    assert stretched.i_beam / stretched.I_CL > 50     # ~60x over the ceiling

    pinned = _slender(tmp_path)
    assert pinned.d_gap == pytest.approx(4.7e-3)      # gap held at the baseline
    base = load_config(CONFIG)
    assert pinned.I_CL == pytest.approx(base.I_CL)    # same emitter ceiling
    assert pinned.geometry().z_emit == pytest.approx(base.geometry().z_emit)


def test_standoff_seals_the_can_bottom(tmp_path):
    """The pedestal leaves a cavity; a BODY cap closes it so the outer skin is a
    full cylinder and no plasma path reaches the interior."""
    g = _slender(tmp_path).geometry()
    assert g.z_floorb == pytest.approx(-5.0e-3)       # pedestal top assembly
    f = g.implicit_function()
    assert f.count("max(") == 4                       # 5 primitives now
    # cathode centre, bottom cap, sealed-cavity void, lid ring
    r = np.array([0.0005, 0.0005, 0.0005, 0.003])
    z = np.array([-0.0047, -0.0298, -0.015, 0.0003])
    m = g.regions(r, z)
    assert m["cathode"].tolist() == [True, False, False, False]
    assert m["floor_ann"].tolist() == [False, True, False, False]
    assert m["lid"].tolist() == [False, False, False, True]
    body = m["wall"] | m["lid"] | m["floor_ann"]
    assert not np.any(m["cathode"] & body)


def test_reject_pedestal_that_collides_with_the_bottom_cap(tmp_path):
    with pytest.raises(ConfigError):
        _slender(tmp_path, standoff=29.5e-3)


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


# ----------------------------------------------------------------------
# axial external field (magnetized variants; optional key, baseline-preserving)
# ----------------------------------------------------------------------

def _magnetized(tmp_path, bz):
    raw = _raw()
    raw["plasma"]["Bz_T"] = bz
    return load_config(_write(tmp_path, raw))


def test_absent_bz_is_exactly_the_baseline():
    """The optional key must not perturb the committed anchor: no stray key in
    the frozen dict, so every existing case hash stays valid."""
    base = load_config(CONFIG)
    assert base.Bz_T is None
    assert "Bz_T" not in base.effective_config()["plasma"]


def test_bz_roundtrips_and_validates(tmp_path):
    cfg = _magnetized(tmp_path, 3.0e-5)          # 1x LEO nominal
    assert cfg.Bz_T == pytest.approx(3.0e-5)
    assert cfg.effective_config()["plasma"]["Bz_T"] == pytest.approx(3.0e-5)
    cfg10 = _magnetized(tmp_path, 3.0e-4)        # 10x amplification
    assert cfg10.Bz_T == pytest.approx(3.0e-4)


def test_bz_rejects_zero_and_oversized(tmp_path):
    with pytest.raises(ConfigError):
        _magnetized(tmp_path, 0.0)               # zero field: omit the key
    with pytest.raises(ConfigError):
        _magnetized(tmp_path, 0.5)               # far past the gyro-resolving review bound
