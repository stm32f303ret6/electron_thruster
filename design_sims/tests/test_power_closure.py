"""The power-closure analysis: unit identity, criterion, and the refusals."""

import csv as _csv
import statistics
from pathlib import Path

import pytest

import figures_of_merit as fom
import power_closure as pc

REPO_ROOT = Path(__file__).resolve().parents[2]

_HEADER = ["timestamp_utc", "altitude_km", "latitude_deg", "longitude_deg",
           "electron_density_m3", "electron_temperature_K", "ion_temperature_K",
           "drag_N", "solar_irradiance_W_m2", "shadow_function",
           "sin_alpha_sun_axis", "power_available_mW"]


def _write_csv(tmp_path, rows, header=_HEADER, solar=True):
    d = tmp_path / "case" / "results"
    d.mkdir(parents=True)
    p = d / "station_keeping.csv"
    with open(p, "w", newline="") as fh:
        w = _csv.writer(fh)
        w.writerow(header)
        w.writerows(rows)
    # the analyser reads pose and cell assumptions from the frozen config
    cfg = {"spacecraft": {"rotation": "axial"}}
    if solar:
        cfg["solar"] = {"cell_efficiency": 0.30, "packing_factor": 0.70,
                        "pointing_loss": 0.90}
    import yaml
    (d / "config_used.yaml").write_text(yaml.safe_dump(cfg), encoding="utf-8")
    return p


def _row(drag_nN, p_avail_mW, shadow=1.0, alt=400.0):
    return ["2024-01-01T12:00:00+00:00", alt, 0.0, 0.0, 1e12, 1300.0, 1000.0,
            drag_nN * 1e-9, 1361.0, shadow, 0.5, p_avail_mW]


# ----------------------------------------------------------------------
# the unit identity the whole analysis rests on
# ----------------------------------------------------------------------

def test_nN_over_uN_per_W_is_exactly_mW(tmp_path):
    """P[mW] = F[nN] / (F/P)[uN/W] -- a unit identity, not an approximation.

    Getting this wrong by 10^3 is the kind of error that makes a concept look
    feasible when it is not, so it is pinned explicitly.
    """
    p = _write_csv(tmp_path, [_row(20.0, 0.0)])
    c = pc.analyse(p, f_per_p=0.2)
    assert c.p_req_mean_mW == pytest.approx(100.0)      # 20 nN / 0.2 uN/W


def test_required_power_scales_with_drag_and_inversely_with_f_per_p(tmp_path):
    p = _write_csv(tmp_path, [_row(10.0, 0.0), _row(30.0, 0.0)])
    a = pc.analyse(p, f_per_p=0.2)
    b = pc.analyse(p, f_per_p=0.4)
    assert a.drag_mean_nN == pytest.approx(20.0)
    assert a.p_req_mean_mW == pytest.approx(100.0)
    assert b.p_req_mean_mW == pytest.approx(50.0)


# ----------------------------------------------------------------------
# the closure criterion
# ----------------------------------------------------------------------

def test_closure_is_an_orbit_mean_energy_balance_not_an_instant_one(tmp_path):
    """Eclipse guarantees zero power for part of every orbit, so an
    instant-by-instant criterion would always fail. The honest metric is the
    energy balance with a storage buffer -- and both are reported."""
    rows = [_row(10.0, 100.0, shadow=1.0)] * 6 + [_row(10.0, 0.0, shadow=0.0)] * 4
    c = pc.analyse(_write_csv(tmp_path, rows), f_per_p=0.2)
    assert c.p_req_mean_mW == pytest.approx(50.0)
    assert c.p_avail_mean_mW == pytest.approx(60.0)
    assert c.margin == pytest.approx(1.2)
    assert c.closes                                   # on orbit average
    assert c.instant_closure_frac == pytest.approx(0.6)   # but only 60 % of rows
    assert c.sunlit_fraction == pytest.approx(0.6)


def test_a_short_margin_does_not_close(tmp_path):
    rows = [_row(50.0, 10.0)] * 5
    c = pc.analyse(_write_csv(tmp_path, rows), f_per_p=0.2)
    assert not c.closes
    assert c.margin == pytest.approx(10.0 / 250.0)


def test_sunlit_mean_excludes_eclipse_rows(tmp_path):
    rows = [_row(10.0, 100.0, shadow=1.0)] * 5 + [_row(10.0, 0.0, shadow=0.0)] * 5
    c = pc.analyse(_write_csv(tmp_path, rows), f_per_p=0.2)
    assert c.p_avail_sunlit_mW == pytest.approx(100.0)
    assert c.p_avail_mean_mW == pytest.approx(50.0)


def test_p95_uses_nearest_rank(tmp_path):
    rows = [_row(float(i + 1), 0.0) for i in range(100)]
    c = pc.analyse(_write_csv(tmp_path, rows), f_per_p=0.2)
    assert c.drag_p95_nN == pytest.approx(95.0)
    assert c.p_req_p95_mW == pytest.approx(475.0)


# ----------------------------------------------------------------------
# refusals
# ----------------------------------------------------------------------

def test_a_csv_without_the_solar_ledger_is_refused(tmp_path):
    """Pre-ledger CSVs must not silently analyse as zero available power."""
    p = _write_csv(tmp_path, [_row(10.0, 0.0)[:8]], header=_HEADER[:8])
    with pytest.raises(SystemExit, match="no solar ledger"):
        pc.analyse(p, f_per_p=0.2)


def test_an_empty_csv_is_refused(tmp_path):
    p = _write_csv(tmp_path, [])
    with pytest.raises(SystemExit, match="no rows"):
        pc.analyse(p, f_per_p=0.2)


# ----------------------------------------------------------------------
# the default F/P comes from measurements, not from a literal
# ----------------------------------------------------------------------

def test_default_f_per_p_is_the_measured_mean():
    fps = [p.f_per_p_uN_per_W for p in fom.measured_points()]
    assert 0.15 <= statistics.fmean(fps) <= 0.21
    assert all(p.source.startswith("measured") for p in fom.measured_points())


def _mk(alt, margin):
    return pc.Closure(case=f"{alt}", n_rows=1, altitude_km=alt,
                      rotation="axial", f_per_p_uN_per_W=0.18,
                      drag_mean_nN=1.0, drag_p95_nN=1.0, p_req_mean_mW=1.0,
                      p_req_p95_mW=1.0, p_avail_mean_mW=margin,
                      p_avail_sunlit_mW=margin, sunlit_fraction=0.6,
                      margin=margin, instant_closure_frac=0.5,
                      net_cell_efficiency=0.189,
                      net_cell_efficiency_needed=0.189 / margin)


def test_crossover_reports_each_possible_state():
    mk = _mk
    assert "unconditional on" in pc.crossover([mk(400, 0.5), mk(550, 1.5)])
    assert "No sampled altitude closes" in pc.crossover([mk(400, 0.5), mk(550, 0.9)])
    assert "Every sampled altitude closes" in pc.crossover([mk(400, 1.2), mk(550, 2.0)])


def test_sweep_finds_the_committed_cases():
    paths = pc.sweep_cases()
    assert paths, "no orbit cases found"
    names = {p.parents[1].name for p in paths}
    assert any("400km" in n for n in names)


# ----------------------------------------------------------------------
# the assumption-independent statement
# ----------------------------------------------------------------------

def test_needed_efficiency_is_the_used_one_scaled_by_the_shortfall(tmp_path):
    """net_needed = net_used / margin -- so a reader can judge the conclusion
    without adopting our cell assumptions."""
    rows = [_row(50.0, 10.0)] * 4
    c = pc.analyse(_write_csv(tmp_path, rows), f_per_p=0.2)
    assert c.net_cell_efficiency == pytest.approx(0.30 * 0.70 * 0.90)
    assert c.net_cell_efficiency_needed == pytest.approx(
        c.net_cell_efficiency / c.margin)
    # a 25x shortfall needs an impossible cell, and must be named as such
    assert "only more area per unit drag" in c.describe()


def test_feasibility_language_escalates_correctly():
    assert "reachable with better" in pc._feasibility(0.20)
    assert "above what is reachable" in pc._feasibility(0.28)
    assert "ABOVE any photovoltaic" in pc._feasibility(0.45)


def test_an_impossible_requirement_is_named_as_a_geometry_problem():
    """The distinction that matters for the thesis: a shortfall a better cell
    could fix, versus one only more area per unit drag can."""
    text = pc._feasibility(0.60)
    assert "only more area per unit drag" in text
