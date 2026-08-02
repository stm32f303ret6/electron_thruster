"""Config parsing, geometry invariants, and derived planes (no WarpX).

The load-bearing check: this stage's transcribed Geometry must derive the
SAME planes and grid as the capstone's own tests pin (../2_floating_body/tests), because
what this stage validates is exactly the geometry the capstone runs."""

from pathlib import Path

import pytest
import yaml

from helpers import Config, ConfigError, Geometry, load_config

CONFIG = Path(__file__).resolve().parents[1] / "config.yaml"


def test_load_config_roundtrip():
    cfg = load_config(CONFIG)
    assert cfg.stage_id == "capstone.two_node_laplace"
    assert cfg.phi_body == 16.0
    assert cfg.cathode_offset == -200.0
    assert cfg.phi_cathode == -184.0


def test_grid_matches_capstone_200x440():
    cfg = load_config(CONFIG)
    assert (cfg.nr, cfg.nz) == (200, 440)
    assert cfg.rmax == pytest.approx(0.030)
    assert cfg.zmin == pytest.approx(-30.0e-3)
    assert cfg.zmax == pytest.approx(36.0e-3)


def test_geometry_derived_planes_match_capstone():
    geom = load_config(CONFIG).geometry()
    assert geom.zfloort == pytest.approx(-4.6e-3)
    assert geom.zlidb == pytest.approx(0.1e-3)
    assert geom.d_gap == pytest.approx(4.7e-3)
    assert geom.r_cath_out == pytest.approx(1.8e-3)
    assert geom.z_emit == pytest.approx(-4.3e-3)


def test_geometry_section_matches_capstone_config():
    """The whole point of this stage: its geometry numbers must be the
    capstone's, byte for byte at the YAML level."""
    here = yaml.safe_load(CONFIG.read_text())["geometry"]
    cap_path = CONFIG.parents[1] / "2_floating_body" / "config.yaml"
    cap = yaml.safe_load(cap_path.read_text())["geometry"]
    assert {k: float(v) for k, v in here.items()} == \
           {k: float(v) for k, v in cap.items()}


def test_potential_string_contains_both_nodes():
    cfg = load_config(CONFIG)
    s = cfg.geometry().potential_string(cfg.phi_body, cfg.phi_cathode)
    assert "16" in s and "-184" in s


def test_node_masks_classify_and_are_disjoint():
    import numpy as np
    geom = load_config(CONFIG).geometry()
    r = np.linspace(0.0, 0.03, 201)
    z = np.linspace(-0.03, 0.036, 441)
    R, Z = np.meshgrid(r, z, indexing="ij")
    m = geom.node_masks(R, Z)
    assert not (m["body"] & m["cathode"]).any()
    # cathode disk center is CATHODE; the can wall is BODY; far field is neither
    assert m["cathode"][np.argmin(np.abs(r - 0.0)), np.argmin(np.abs(z + 4.8e-3))]
    assert m["body"][np.argmin(np.abs(r - 4.8e-3)), np.argmin(np.abs(z + 2e-3))]
    assert not (m["body"] | m["cathode"])[np.argmin(np.abs(r - 0.02)),
                                          np.argmin(np.abs(z - 0.02))]


def _mutated(tmp_path, mutate):
    raw = yaml.safe_load(CONFIG.read_text())
    mutate(raw)
    p = tmp_path / "mutated.yaml"
    p.write_text(yaml.safe_dump(raw))
    return p


def test_rejects_positive_offset(tmp_path):
    p = _mutated(tmp_path,
                 lambda r: r["electrical"].__setitem__("cathode_offset", 10.0))
    with pytest.raises(ConfigError):
        load_config(p)


def test_rejects_unknown_key(tmp_path):
    p = _mutated(tmp_path, lambda r: r["electrical"].__setitem__("bogus", 1.0))
    with pytest.raises(ConfigError):
        load_config(p)


def test_rejects_missing_key(tmp_path):
    p = _mutated(tmp_path, lambda r: r["geometry"].__delitem__("r_slit"))
    with pytest.raises(ConfigError):
        load_config(p)


def test_rejects_single_step(tmp_path):
    p = _mutated(tmp_path, lambda r: r["numerics"].__setitem__("max_steps", 1))
    with pytest.raises(ConfigError):
        load_config(p)
