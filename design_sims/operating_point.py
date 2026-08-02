#!/usr/bin/env python3
r"""operating_point.py — mission CSV in, PIC scenarios out.

    python3 operating_point.py --csv ../orbit_sims/validation_cases/400km_station_keeping_chipsat/results/station_keeping.csv
    python3 operating_point.py --csv <path> --emit scenarios.yaml --plots plots/

Reads a year of `(n_e, Te, Ti, drag_N)` from the orbit sim, reports whether the
mission closes on orbit average, and picks the TWO rows worth spending ten hours
of PIC on each.

THE SELECTION RULE, COMMITTED HERE RATHER THAN CHOSEN BY HAND
-------------------------------------------------------------
Two scenarios, deliberately at *different* binding constraints, because a pair
that both bind the same way would test the same half of the model twice.

**A_day_p95** — the row at the nearest-rank 95th percentile of ``drag_N``.
  Dayside maximum demand: dense plasma, hot electrons, and the largest thrust
  the mission ever asks for. This probes the SPACE-CHARGE/demand side, where the
  emission ceiling binds.

**B_night_worst** — the row minimising the supply margin

      i_ceiling(row, phi_max) / i_demand(row, v_max)

  i.e. the worst ratio of "current this ionosphere will give back" to "current
  this drag demands". Night, thin plasma, cold electrons. This probes the
  COLLECTION side, where the float limit binds.

  Subject to a **settle-time guard**: ``tau = C*phi/I <= 0.25*t_end``. tau grows
  as 1/n_e, so the true worst row of the year can be one whose float would still
  be climbing when a 1 us PIC run ends — such a run measures a transient, not an
  equilibrium, and no gate on it would mean anything. If the worst row violates
  the guard, the worst row that satisfies it is taken instead and BOTH are
  reported, so the substitution is disclosed rather than silent. The honest
  claim then is: continuous-thrust validation extends to the guard boundary;
  below it the mission is duty-cycled on orbit average.

No third "anchor" scenario is needed — the anchor IS the committed
`capstone.floating_body` reference the constants were fitted from.

WHAT GETS EMITTED
-----------------
A `scenarios:` block ready to paste into the PIC stage's `config.yaml`, carrying
the plasma row, the chosen `(V, I)`, the model's PREDICTIONS, and the row's
provenance (CSV sha256 + timestamp + row index). Committing that block *before*
the runs is the pre-registration: the predictions are in git with a timestamp,
so they cannot be quietly adjusted after the measurement lands.

Depends on: numpy, PyYAML, matplotlib (plots only), scipy.
"""

from __future__ import annotations

import argparse
import csv as _csv
import datetime as _dt
import math
import sys
from dataclasses import dataclass
from pathlib import Path

DESIGN_ROOT = Path(__file__).resolve().parent
REPO_ROOT = DESIGN_ROOT.parent
sys.path.insert(0, str(DESIGN_ROOT))

import yaml  # noqa: E402

import opmodel as om  # noqa: E402
from calibration import load_laws, sha256_of  # noqa: E402

#: The ion mass surrogate the whole ladder uses. NOT real O+ -- a ladder-wide
#: caveat carried into every scenario block so it travels with the numbers.
ION_MASS_ME = 400.0

#: t_end the PIC stage will run for; the settle guard is a quarter of it.
DEFAULT_T_END_S = 1.0e-6
SETTLE_GUARD_FRAC = 0.25


@dataclass(frozen=True)
class Row:
    index: int
    timestamp_utc: str
    altitude_km: float
    latitude_deg: float
    longitude_deg: float
    n_e: float
    Te_K: float
    Ti_K: float
    drag_N: float


def read_rows(path: Path) -> list[Row]:
    """Read the orbit CSV. Every column is required; a bad row aborts."""
    rows: list[Row] = []
    with open(path, newline="") as fh:
        for i, rec in enumerate(_csv.DictReader(fh)):
            try:
                rows.append(Row(
                    index=i, timestamp_utc=rec["timestamp_utc"],
                    altitude_km=float(rec["altitude_km"]),
                    latitude_deg=float(rec["latitude_deg"]),
                    longitude_deg=float(rec["longitude_deg"]),
                    n_e=float(rec["electron_density_m3"]),
                    Te_K=float(rec["electron_temperature_K"]),
                    Ti_K=float(rec["ion_temperature_K"]),
                    drag_N=float(rec["drag_N"])))
            except (KeyError, TypeError, ValueError) as exc:
                raise SystemExit(f"{path}: bad row {i}: {exc}") from exc
    if not rows:
        raise SystemExit(f"{path} has no data rows")
    return rows


# ======================================================================
# the selection rule
# ======================================================================

def supply_margin(row: Row, laws, cons: om.Constraints) -> float:
    """``i_ceiling(row, phi_max) / i_demand(row, v_max)`` — small is starved.

    The numerator is the beam current whose steady float lands exactly on
    ``phi_max``: the most this ionosphere will sustain. The denominator is the
    current this row's drag would need at full voltage, evaluated at the same
    ``phi_max`` so the ratio is a pure supply-vs-demand comparison and not
    contaminated by where the float actually settles.
    """
    i_ceiling = om.beam_current_at_phi_A(cons.phi_max, row.n_e, row.Te_K,
                                         laws.beta, laws.area_m2, laws.f_esc)
    i_demand = om.current_for_thrust_mA(
        cons.margin * row.drag_N * 1e9, cons.v_max, cons.phi_max,
        laws.k, laws.ke_ledger) * 1e-3
    if i_demand <= 0.0:
        return float("inf")
    return i_ceiling / i_demand


def settle_time_at_ceiling_s(row: Row, laws, cons: om.Constraints) -> float:
    """``tau = C*phi_max/i_ceiling`` — how long this row's float takes to settle."""
    i_ceiling = om.beam_current_at_phi_A(cons.phi_max, row.n_e, row.Te_K,
                                         laws.beta, laws.area_m2, laws.f_esc)
    return om.settle_time_s(cons.phi_max, i_ceiling, laws.capacitance_F)


def nearest_rank_row(rows: list[Row], pct: float) -> Row:
    """The row at the nearest-rank ``pct`` percentile of drag."""
    ordered = sorted(rows, key=lambda r: r.drag_N)
    idx = max(0, min(len(ordered) - 1,
                     int(math.ceil(pct / 100.0 * len(ordered))) - 1))
    return ordered[idx]


def select_night_worst(rows: list[Row], laws, cons: om.Constraints,
                       t_end_s: float) -> tuple[Row, Row, float]:
    """Worst supply margin subject to the settle guard.

    Returns ``(chosen, true_worst, tau_guard_s)``. ``chosen is true_worst``
    when the guard did not bite.
    """
    tau_guard = SETTLE_GUARD_FRAC * t_end_s
    true_worst = min(rows, key=lambda r: supply_margin(r, laws, cons))
    eligible = [r for r in rows if settle_time_at_ceiling_s(r, laws, cons) <= tau_guard]
    if not eligible:
        raise SystemExit(
            f"no row settles within {tau_guard*1e9:.0f} ns; every candidate "
            f"night point would measure a transient at t_end = {t_end_s*1e9:.0f} ns. "
            f"Raise t_end or accept a duty-cycled claim.")
    chosen = min(eligible, key=lambda r: supply_margin(r, laws, cons))
    return chosen, true_worst, tau_guard


# ======================================================================
# scenario emission
# ======================================================================

def scenario_block(name: str, row: Row, point: om.OperatingPoint, laws,
                   cons: om.Constraints, *, csv_path: Path, csv_sha: str,
                   note: str | None = None) -> dict:
    """One `scenarios:` entry: the physics, the predictions, and where it came from.

    THE PREDICTIONS ARE RECOMPUTED FROM THE ROUNDED VALUES, not copied from the
    solver. Everything the PIC deck consumes is rounded to six significant
    figures for readability, and the `law_anchor` constants are rounded the same
    way — so a prediction carried over at full solver precision would disagree
    with anything the stage could recompute for itself. Recomputing here from
    exactly the numbers that get frozen is what lets the stage's
    `prediction_consistency` gate be a real anti-post-hoc check (tolerance 1e-9)
    rather than a rounding allowance.
    """
    try:
        orbit_case = str(csv_path.resolve().relative_to(REPO_ROOT))
    except ValueError:
        orbit_case = str(csv_path)

    n0 = float(f"{row.n_e:.6g}")
    te = float(f"{row.Te_K:.6g}")
    v_drive = float(f"{point.v_drive_V:.6g}")
    i_beam = float(f"{point.i_beam_mA*1e-3:.6g}")
    anchor = law_anchor_block(laws)

    phi_pred = om.phi_for_escape_current_V(anchor["f_esc"] * i_beam, n0, te,
                                           anchor["beta"], anchor["area_m2"])
    ke_pred = om.exhaust_ke_eV(v_drive, phi_pred, anchor["ke_ledger"])
    f_pred = om.thrust_nN(i_beam * 1e3, v_drive, phi_pred, anchor["k"],
                          anchor["ke_ledger"])

    block = {
        "name": name,
        "plasma": {
            "n0": n0,
            "Te_K": te,
            "Ti_K": float(f"{row.Ti_K:.6g}"),
            "ion_mass_me": ION_MASS_ME,
        },
        "cathode_offset": -v_drive,
        "i_beam": i_beam,
        "drag_target_N": float(f"{row.drag_N:.6g}"),
        "predicted": {
            "phi_body_V": phi_pred,
            "f_beam_nN": f_pred,
            "exhaust_ke_eV": ke_pred,
            "binding": point.binding,
        },
        "provenance": {
            "orbit_case": orbit_case,
            "csv_sha256": csv_sha,
            "timestamp_utc": row.timestamp_utc,
            "row_index": row.index,
            "altitude_km": float(f"{row.altitude_km:.6g}"),
            "latitude_deg": float(f"{row.latitude_deg:.6g}"),
            "longitude_deg": float(f"{row.longitude_deg:.6g}"),
            "laws_sha256": laws.sha256,
            "tool": "design_sims/operating_point.py",
        },
        "reported": {
            "chi": float(f"{point.chi:.6g}"),
            "settle_time_ns": float(f"{point.settle_time_s*1e9:.6g}"),
            "i_over_i_cl": float(f"{point.i_over_i_cl:.6g}"),
            "i_the_uA": float(f"{point.i_the_uA:.6g}"),
            "p_supply_mW": float(f"{point.p_supply_mW:.6g}"),
            "deficit_nN": float(f"{point.deficit_nN:.6g}"),
            "debye_length_mm": float(f"{debye_mm(row.n_e, row.Te_K):.6g}"),
        },
    }
    if note:
        block["note"] = note
    return block


def debye_mm(n_e: float, Te_K: float) -> float:
    return 1e3 * math.sqrt(om.EPS0 * om.KB * Te_K / (n_e * om.E ** 2))


def law_anchor_block(laws) -> dict:
    """The `law_anchor:` block the PIC stage freezes, so the stage can recompute
    the predictions itself and catch any drift between the two opmodels."""
    anchor = laws.anchors[0] if laws.anchors else None
    return {
        "k": float(f"{laws.k:.6g}"),
        "ke_ledger": float(f"{laws.ke_ledger:.6g}"),
        "f_esc": float(f"{laws.f_esc:.6g}"),
        "beta": float(f"{laws.beta:.6g}"),
        "area_m2": float(f"{laws.area_m2:.6g}"),
        "capacitance_F": float(f"{laws.capacitance_F:.6g}"),
        "anchored_to": anchor.anchored_to if anchor else None,
        "metrics_sha256": anchor.sha256 if anchor else None,
        "laws_sha256": laws.sha256,
    }


# ======================================================================
# plots
# ======================================================================

def make_plots(out_dir: Path, rows: list[Row], picks: dict, laws,
               cons: om.Constraints) -> list[Path]:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import numpy as np

    out_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []

    t0 = _dt.datetime.fromisoformat(rows[0].timestamp_utc)
    days = np.array([(_dt.datetime.fromisoformat(r.timestamp_utc) - t0).total_seconds()
                     / 86400.0 for r in rows])
    drag_nN = np.array([r.drag_N * 1e9 for r in rows])
    f_max = np.array([om.solve_at_voltage(r.n_e, r.Te_K, r.drag_N, cons.v_max,
                                          laws, cons).f_max_nN for r in rows])
    ne = np.array([r.n_e for r in rows])

    # ---- 1: supply margin over the mission, plus a two-day diurnal zoom ----
    fig, (ax0, ax1) = plt.subplots(2, 1, figsize=(11, 8))
    step = max(1, len(rows) // 4000)
    ax0.plot(days[::step], drag_nN[::step], lw=0.5, color="tab:red",
             label="drag demand")
    ax0.plot(days[::step], f_max[::step], lw=0.5, color="tab:green",
             label=f"deliverable at {cons.v_max:.0f} V, full throttle")
    for name, (row, _pt) in picks.items():
        d = (_dt.datetime.fromisoformat(row.timestamp_utc) - t0).total_seconds() / 86400.0
        ax0.axvline(d, color="k", ls="--", lw=0.8)
        ax0.annotate(name, (d, ax0.get_ylim()[1]), rotation=90,
                     fontsize=8, va="top", ha="right")
    ax0.set_xlabel("mission elapsed [days]")
    ax0.set_ylabel("force [nN]")
    ax0.set_title("Demand vs deliverable thrust over the mission "
                  "(where the two PIC scenarios sit)")
    ax0.legend(loc="upper right", fontsize=8)
    ax0.grid(alpha=0.3)

    two_days = days <= (days[0] + 2.0)
    ax1b = ax1.twinx()
    ax1.plot(days[two_days] * 24.0, drag_nN[two_days], color="tab:red", lw=1.2,
             label="drag demand")
    ax1.plot(days[two_days] * 24.0, f_max[two_days], color="tab:green", lw=1.2,
             label="deliverable")
    ax1b.semilogy(days[two_days] * 24.0, ne[two_days], color="tab:blue",
                  lw=0.8, alpha=0.6)
    ax1b.set_ylabel("n_e [m^-3]", color="tab:blue")
    ax1.set_xlabel("mission elapsed [hours]  (first two days)")
    ax1.set_ylabel("force [nN]")
    ax1.set_title("The diurnal swing the two scenarios bracket")
    ax1.legend(loc="upper right", fontsize=8)
    ax1.grid(alpha=0.3)
    fig.tight_layout()
    p = out_dir / "margin_vs_orbit_time.png"
    fig.savefig(p, dpi=130)
    plt.close(fig)
    written.append(p)

    # ---- 2: the P-F envelope with its constraint boundaries ----------------
    fig, ax = plt.subplots(figsize=(9, 6))
    colors = {"A_day_p95": "tab:orange", "B_night_worst": "tab:blue"}
    volts = np.linspace(cons.v_min, cons.v_max, 120)
    for name, (row, pt) in picks.items():
        col = colors.get(name, "tab:gray")
        pts = [om.solve_at_voltage(row.n_e, row.Te_K, row.drag_N, v, laws, cons)
               for v in volts]
        ax.plot([q.p_max_mW for q in pts], [q.f_max_nN for q in pts],
                color=col, lw=2, label=f"{name}: full-throttle envelope")
        # mark where each ceiling takes over
        for binding, marker in (("phi_max", "s"), ("gamma_cl", "^"),
                                ("thrust_peak", "o")):
            sel = [q for q in pts if q.binding == binding]
            if sel:
                ax.plot([q.p_max_mW for q in sel], [q.f_max_nN for q in sel],
                        marker, color=col, ms=3, alpha=0.55)
        ax.plot([pt.p_supply_mW], [pt.f_nN], "*", color=col, ms=18,
                markeredgecolor="k", zorder=5)
        ax.axhline(row.drag_N * 1e9, color=col, ls=":", lw=1.2)
        ax.annotate(f"{name} demand", (ax.get_xlim()[1], row.drag_N * 1e9),
                    fontsize=8, color=col, ha="right", va="bottom")
    ax.set_xlabel("supply power I*V [mW]")
    ax.set_ylabel("thrust [nN]")
    ax.set_title("What each scenario can buy, and what stops it\n"
                 "(square = float limit binds, triangle = emission ceiling "
                 "binds, circle = thrust peak; star = chosen point)")
    ax.legend(loc="lower right", fontsize=8)
    ax.grid(alpha=0.3)
    fig.tight_layout()
    p = out_dir / "power_thrust_envelope.png"
    fig.savefig(p, dpi=130)
    plt.close(fig)
    written.append(p)
    return written


# ======================================================================
# driver
# ======================================================================

def parse_args(argv=None):
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--csv", type=Path, required=True, help="the orbit station-keeping CSV")
    ap.add_argument("--emit", type=Path, default=None,
                    help="write the scenarios+law_anchor YAML block here")
    ap.add_argument("--plots", type=Path, default=None, help="write the two plots here")
    ap.add_argument("--t-end", type=float, default=DEFAULT_T_END_S,
                    help="the PIC run length the settle guard is measured against")
    ap.add_argument("--v-min", type=float, default=om.Constraints.v_min)
    ap.add_argument("--v-max", type=float, default=om.Constraints.v_max)
    ap.add_argument("--phi-max", type=float, default=om.Constraints.phi_max)
    ap.add_argument("--gamma-cl-max", type=float, default=om.Constraints.gamma_cl_max)
    ap.add_argument("--margin", type=float, default=om.Constraints.margin)
    return ap.parse_args(argv)


def main(argv=None) -> int:
    args = parse_args(argv)
    laws = load_laws()
    cons = om.Constraints(v_min=args.v_min, v_max=args.v_max, phi_max=args.phi_max,
                          gamma_cl_max=args.gamma_cl_max, margin=args.margin)
    cons.validate()

    rows = read_rows(args.csv)
    csv_sha = sha256_of(args.csv)

    print("=" * 78)
    print(f"operating points from {args.csv}")
    print(f"  {len(rows)} rows, {rows[0].timestamp_utc} .. {rows[-1].timestamp_utc}")
    print(f"  csv sha256 {csv_sha[:16]}...")
    print(laws.describe())
    print(f"  constraints: V in [{cons.v_min:g}, {cons.v_max:g}] V, "
          f"phi <= {cons.phi_max:g} V, I <= {cons.gamma_cl_max:g}*I_CL, "
          f"margin {cons.margin:g}")
    print("=" * 78)

    summary = om.orbit_summary(rows, laws, cons)
    print(summary.describe())
    print("-" * 78)

    # ---- selection ----
    row_a = nearest_rank_row(rows, 95.0)
    row_b, true_worst, tau_guard = select_night_worst(rows, laws, cons, args.t_end)
    substituted = row_b.index != true_worst.index

    pt_a = om.solve_operating_point(row_a.n_e, row_a.Te_K, row_a.drag_N, laws, cons)
    pt_b = om.solve_operating_point(row_b.n_e, row_b.Te_K, row_b.drag_N, laws, cons)

    print(f"A_day_p95      row {row_a.index} @ {row_a.timestamp_utc}  "
          f"n_e={row_a.n_e:.3e}  Te={row_a.Te_K:.0f} K  drag={row_a.drag_N*1e9:.3f} nN")
    print(f"               {pt_a.describe()}")
    print(f"B_night_worst  row {row_b.index} @ {row_b.timestamp_utc}  "
          f"n_e={row_b.n_e:.3e}  Te={row_b.Te_K:.0f} K  drag={row_b.drag_N*1e9:.3f} nN")
    print(f"               {pt_b.describe()}")
    print(f"               supply margin {supply_margin(row_b, laws, cons):.4f}, "
          f"settle guard tau <= {tau_guard*1e9:.0f} ns")
    note_b = None
    if substituted:
        note_b = (
            f"DISCLOSED SUBSTITUTION: the true worst-margin row of the mission is "
            f"row {true_worst.index} ({true_worst.timestamp_utc}, "
            f"n_e={true_worst.n_e:.3e} m^-3, Te={true_worst.Te_K:.0f} K, margin "
            f"{supply_margin(true_worst, laws, cons):.4f}), but its float would "
            f"still be settling at t_end "
            f"(tau={settle_time_at_ceiling_s(true_worst, laws, cons)*1e9:.0f} ns > "
            f"{tau_guard*1e9:.0f} ns), so a run there would measure a transient, not "
            f"an equilibrium. This row is the worst that settles in time. "
            f"Continuous-thrust validation therefore extends to the guard boundary; "
            f"below it the mission is duty-cycled on orbit average.")
        print("  ! " + note_b)
    else:
        print("               (settle guard did not bite: this IS the worst row "
              "of the mission)")
    print("-" * 78)

    picks = {"A_day_p95": (row_a, pt_a), "B_night_worst": (row_b, pt_b)}

    if args.emit:
        doc = {
            "law_anchor": law_anchor_block(laws),
            "scenarios": [
                scenario_block("A_day_p95", row_a, pt_a, laws, cons,
                               csv_path=args.csv, csv_sha=csv_sha),
                scenario_block("B_night_worst", row_b, pt_b, laws, cons,
                               csv_path=args.csv, csv_sha=csv_sha, note=note_b),
            ],
        }
        header = (
            f"# GENERATED by design_sims/operating_point.py on "
            f"{_dt.datetime.now(_dt.timezone.utc).replace(microsecond=0).isoformat()}\n"
            f"# Selection rule: A = nearest-rank p95 of drag_N; B = minimum supply\n"
            f"# margin subject to the settle guard tau <= {SETTLE_GUARD_FRAC:g}*t_end.\n"
            f"# Paste into the PIC stage config BEFORE the runs -- the predicted:\n"
            f"# block is a pre-registration, not a post-hoc description.\n")
        args.emit.write_text(
            header + yaml.safe_dump(doc, sort_keys=False, default_flow_style=False),
            encoding="utf-8")
        print(f"scenarios -> {args.emit}")

    if args.plots:
        for p in make_plots(args.plots, rows, picks, laws, cons):
            print(f"plot -> {p}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
