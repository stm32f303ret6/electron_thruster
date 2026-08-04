#!/usr/bin/env python3
r"""run_station_keeping.py — propagate one case's orbit and measure its drag demand.

    python3 run_station_keeping.py --list
    python3 run_station_keeping.py 400km_station_keeping_chipsat            # full year (~13 min CPU)
    python3 run_station_keeping.py 400km_station_keeping_chipsat --days 1   # 1-day smoke test

Environment: conda activate tudat-sk

THE QUESTION: how much drag must this vehicle actually cancel, and in what
ionosphere?

A tiny satellite is propagated with TudatPy while an idealised thruster fires
continuously to cancel drag exactly, so altitude is held and the per-row drag
force IS the thrust a real system must supply. Every exported pose is enriched
with IRI-2020 electron density and electron/ion temperature, which is what lets
the PIC side be run at the ionosphere the vehicle actually flies through.

THE DELIVERABLE IS THE CSV. It is spacecraft-independent in its environment
columns: because drag is cancelled the altitude holds, so rho(t), v(t), n_e(t),
Te(t) and Ti(t) do not depend on the vehicle that flew through them. Only
`drag_N` carries the geometry. PIC scenario conditions are picked from this CSV
by inspection and frozen into the PIC stage's config.

Output: validation_cases/<case>/results/{station_keeping.csv, config_used.yaml}
"""

import argparse
import datetime as _dt
import os
import sys
from pathlib import Path

ORBIT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ORBIT_ROOT))     # flat sibling imports, from any cwd

from tudatpy.astro import time_representation as tr  # noqa: E402
from tudatpy.interface import spice  # noqa: E402
import tudatpy  # noqa: E402

import config as config_mod  # noqa: E402
import environment as env_mod  # noqa: E402
import propagate as prop_mod  # noqa: E402
import spacecraft as sc_mod  # noqa: E402

CASES_DIR = ORBIT_ROOT / "validation_cases"


def available_cases():
    if not CASES_DIR.is_dir():
        return []
    return sorted(p.name for p in CASES_DIR.iterdir()
                  if (p / "inputs" / "config.yaml").is_file())


def resolve_case(name):
    cases = available_cases()
    if name not in cases:
        listing = "\n".join(f"  {c}" for c in cases) or "  (none found)"
        raise SystemExit(
            f"unknown case {name!r}. Available cases in {CASES_DIR}:\n{listing}")
    return CASES_DIR / name


def parse_args(argv=None):
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("case", nargs="?",
                    help="validation case name, e.g. 400km_station_keeping_chipsat")
    ap.add_argument("--days", type=float, default=None,
                    help="override mission.duration_days (for a quick smoke test)")
    ap.add_argument("--list", action="store_true", help="list available cases and exit")
    return ap.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)

    if args.list:
        for name in available_cases():
            print(f"  {name}")
        return 0
    if not args.case:
        raise SystemExit("give a case name (or --list). See --help.")

    case_dir = resolve_case(args.case)
    cfg = config_mod.load(case_dir / "inputs" / "config.yaml")
    if args.days is not None:
        if args.days <= 0.0:
            raise SystemExit("--days must be positive")
        # Override BOTH the live config and its raw dict, so config_used.yaml
        # records what actually ran rather than what the file said.
        cfg.mission.duration_days = args.days
        cfg.raw["mission"]["duration_days"] = args.days
    craft = sc_mod.build(cfg)

    out_dir = case_dir / "results"
    os.makedirs(out_dir, exist_ok=True)
    csv_path = out_dir / "station_keeping.csv"

    spice.load_standard_kernels()
    mu = spice.get_body_gravitational_parameter("Earth")

    print("=" * 78)
    print(f"orbit_sims station keeping — {args.case}")
    print(f"  TudatPy {tudatpy.__version__} via {env_mod.TUDAT_NAMESPACE}")
    print(f"  spacecraft: {craft.describe()}")
    print(f"  output -> {out_dir}/")
    print("=" * 78)

    print("  " + env_mod.assert_models_available())
    start_dt = _dt.datetime.fromisoformat(cfg.mission.start_utc)
    start_epoch = float(tr.epoch_from_date_time_components(
        start_dt.year, start_dt.month, start_dt.day,
        start_dt.hour, start_dt.minute, float(start_dt.second)))
    end_dt = tr.date_time_from_epoch(
        start_epoch + cfg.mission.duration_days * 86400.0).to_python_datetime()
    print("  " + env_mod.assert_iri_coverage(start_dt, end_dt))

    cfg.dump(out_dir / "config_used.yaml")
    bodies = env_mod.build_bodies(cfg, craft)
    accelerations = prop_mod.build_accelerations(cfg, bodies, craft)

    print(f"  propagating {cfg.mission.duration_days:g} day(s) from "
          f"{start_dt.isoformat()} UTC in {cfg.mission.arc_days:g}-day arcs, "
          f"{cfg.mission.integration_step_s:g}s RKF7(8), "
          f"{cfg.mission.output_step_s:g}s CSV cadence", flush=True)

    n_rows, stats, wall = prop_mod.run(
        cfg, craft, bodies, accelerations, mu, start_epoch, csv_path)
    if n_rows == 0:
        raise SystemExit("no rows written -- propagation produced nothing")

    print("-" * 78)
    print(f"Done: {n_rows} rows in {wall:.1f}s -> {csv_path}")
    alt_min, alt_mean, alt_max = stats.triple("alt")
    drag_min, drag_mean, drag_max = stats.triple("drag")
    ne_min, ne_mean, ne_max = stats.triple("ne")
    te_min, te_mean, te_max = stats.triple("te")
    ti_min, ti_mean, ti_max = stats.triple("ti")
    print(f"  altitude   {alt_min:.2f} / {alt_mean:.2f} / {alt_max:.2f} km "
          f"(drift {stats.alt_drift:+.3f} km)")
    print(f"  drag       {drag_min*1e9:.2f} / {drag_mean*1e9:.2f} / {drag_max*1e9:.2f} nN")
    print(f"  n_e        {ne_min:.3e} / {ne_mean:.3e} / {ne_max:.3e} m^-3")
    print(f"  Te         {te_min:.0f} / {te_mean:.0f} / {te_max:.0f} K")
    print(f"  Ti         {ti_min:.0f} / {ti_mean:.0f} / {ti_max:.0f} K")
    print("  (min / mean / max)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
