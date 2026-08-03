#!/usr/bin/env python3
r"""power_closure.py — does the spacecraft's own skin power its own drag makeup?

    python3 power_closure.py --csv ../orbit_sims/validation_cases/*/results/station_keeping.csv
    python3 power_closure.py --sweep            # every case under orbit_sims/
    python3 power_closure.py --sweep --markdown

THE CLAIM SAYS "a power level the spacecraft's own skin can harvest". This turns
that from an estimate into a computed statement, and it is the ONE analysis the
thesis needs that no existing artifact provides.

WHY THE CALCULATION IS SPLIT ACROSS TWO TREES. `orbit_sims/` computes what is
AVAILABLE -- irradiance, eclipse, the pose-dependent projected area -- because
that is pure orbital mechanics and spacecraft geometry. It cannot compute what is
REQUIRED, because that depends on the thruster's figures of merit, and
`orbit_sims/` reads nothing from `design_sims/` by design. So the loop closes
here:

    P_required = drag_N / (F/P)          F/P from figures_of_merit.py
    P_available = the CSV's own column    (already eclipse-corrected)

F/P is the right quantity to divide by precisely because it is **independent of
current** (both F and P are linear in I), so it converts a drag demand into a
power demand with no operating-point assumption smuggled in. It is also
independent of the collection law, which rung 9 falsified -- so this closure
statement survives that finding intact.

WHAT "CLOSES" MEANS. Not "every instant" -- eclipse guarantees P_available = 0
for ~35 % of every orbit. The honest criterion is an ENERGY balance over the
orbit with a storage buffer, so the metric is the ratio of orbit-mean available
to orbit-mean required. A battery big enough to ride out eclipse is assumed and
stated, not hidden.

Depends on: numpy, PyYAML, scipy.
"""

from __future__ import annotations

import argparse
import csv as _csv
import math
import statistics
import sys
from dataclasses import dataclass
from pathlib import Path

DESIGN_ROOT = Path(__file__).resolve().parent
REPO_ROOT = DESIGN_ROOT.parent
sys.path.insert(0, str(DESIGN_ROOT))

import figures_of_merit as fom  # noqa: E402

ORBIT_CASES = REPO_ROOT / "orbit_sims" / "validation_cases"

#: Columns the solar ledger adds. A CSV without them predates the ledger.
_SOLAR_COLS = ("solar_irradiance_W_m2", "shadow_function", "sin_alpha_sun_axis",
               "power_available_mW")


@dataclass(frozen=True)
class Closure:
    case: str
    n_rows: int
    altitude_km: float
    rotation: str
    f_per_p_uN_per_W: float
    drag_mean_nN: float
    drag_p95_nN: float
    p_req_mean_mW: float
    p_req_p95_mW: float
    p_avail_mean_mW: float
    p_avail_sunlit_mW: float
    sunlit_fraction: float
    margin: float               # <P_avail> / <P_req>; >= 1 closes on orbit average
    instant_closure_frac: float  # fraction of rows where the panel alone suffices
    net_cell_efficiency: float   # the declared eff x packing x derate this used
    net_cell_efficiency_needed: float   # what would be needed to reach margin 1

    @property
    def closes(self) -> bool:
        return self.margin >= 1.0

    def describe(self) -> str:
        verdict = "CLOSES" if self.closes else "does NOT close"
        return (
            f"{self.case}\n"
            f"  altitude {self.altitude_km:.0f} km, pose {self.rotation}, "
            f"{self.n_rows} rows, sunlit {self.sunlit_fraction*100:.1f} % of the time\n"
            f"  drag        mean {self.drag_mean_nN:7.3f} nN   p95 {self.drag_p95_nN:7.3f} nN\n"
            f"  P required  mean {self.p_req_mean_mW:7.2f} mW   p95 {self.p_req_p95_mW:7.2f} mW"
            f"   (at F/P = {self.f_per_p_uN_per_W:.3f} uN/W)\n"
            f"  P available mean {self.p_avail_mean_mW:7.2f} mW   "
            f"{self.p_avail_sunlit_mW:7.2f} mW while sunlit\n"
            f"  energy margin <P_avail>/<P_req> = {self.margin:.2f}  ->  {verdict}\n"
            f"  net cell efficiency: used {self.net_cell_efficiency*100:.1f} %, "
            f"would need {self.net_cell_efficiency_needed*100:.1f} % to close"
            f"{'' if self.closes else _feasibility(self.net_cell_efficiency_needed)}")


#: A triple-junction cell is ~30-32 % BOL.  Multiplied by any realistic packing
#: factor on a curved body, a NET (efficiency x packing x derate) above ~25 % is
#: not reachable, and above 32 % is impossible with photovoltaics at all.
_NET_REACHABLE = 0.25
_NET_IMPOSSIBLE = 0.32


def _feasibility(needed: float) -> str:
    """State plainly whether the required efficiency is even physical.

    Without this a reader could mistake a shortfall for something better cells
    would fix.  Beyond ~32 % net it is not a cell problem at all -- it is a
    geometry problem, and the answer is more sunlit area per unit ram area.
    """
    if needed > _NET_IMPOSSIBLE:
        return ("  <- ABOVE any photovoltaic cell's raw efficiency: no cell "
                "choice closes this, only more area per unit drag")
    if needed > _NET_REACHABLE:
        return "  <- above what is reachable on a curved body-mounted array"
    return "  <- reachable with better cells/packing"


def _nearest_rank(vals: list[float], pct: float) -> float:
    s = sorted(vals)
    idx = max(0, min(len(s) - 1, int(math.ceil(pct / 100.0 * len(s))) - 1))
    return s[idx]


def analyse(csv_path: Path, f_per_p: float) -> Closure:
    """One mission CSV -> its power-closure statement."""
    drag_nN: list[float] = []
    p_avail: list[float] = []
    alts: list[float] = []
    sunlit = 0
    instant_ok = 0
    with open(csv_path, newline="") as fh:
        reader = _csv.DictReader(fh)
        missing = [c for c in _SOLAR_COLS if c not in (reader.fieldnames or [])]
        if missing:
            raise SystemExit(
                f"{csv_path} has no solar ledger (missing {missing}). Re-run "
                f"orbit_sims for this case; the ledger was added 2026-08-03.")
        for rec in reader:
            d = float(rec["drag_N"]) * 1e9
            pa = float(rec["power_available_mW"])
            drag_nN.append(d)
            p_avail.append(pa)
            alts.append(float(rec["altitude_km"]))
            if float(rec["shadow_function"]) > 0.5:
                sunlit += 1
            if pa >= d / f_per_p:
                instant_ok += 1
    if not drag_nN:
        raise SystemExit(f"{csv_path} has no rows")

    # P[mW] = F[nN] / (F/P)[uN/W]   -- nN/(uN/W) == mW exactly
    p_req = [d / f_per_p for d in drag_nN]
    n = len(drag_nN)
    sunlit_vals = [p for p in p_avail if p > 0.0]
    cfg = csv_path.parent / "config_used.yaml"
    rotation, net_eff = "?", float("nan")
    if cfg.is_file():
        import yaml
        doc = yaml.safe_load(cfg.read_text(encoding="utf-8"))
        rotation = doc["spacecraft"]["rotation"]
        sol = doc.get("solar") or {}
        if sol:
            net_eff = (float(sol["cell_efficiency"]) * float(sol["packing_factor"])
                       * float(sol["pointing_loss"]))
    return Closure(
        case=csv_path.parents[1].name, n_rows=n,
        altitude_km=statistics.fmean(alts), rotation=rotation,
        f_per_p_uN_per_W=f_per_p,
        drag_mean_nN=statistics.fmean(drag_nN),
        drag_p95_nN=_nearest_rank(drag_nN, 95.0),
        p_req_mean_mW=statistics.fmean(p_req),
        p_req_p95_mW=_nearest_rank(p_req, 95.0),
        p_avail_mean_mW=statistics.fmean(p_avail),
        p_avail_sunlit_mW=statistics.fmean(sunlit_vals) if sunlit_vals else 0.0,
        sunlit_fraction=sunlit / n,
        margin=(statistics.fmean(p_avail) / statistics.fmean(p_req)
                if statistics.fmean(p_req) > 0 else float("inf")),
        instant_closure_frac=instant_ok / n,
        net_cell_efficiency=net_eff,
        net_cell_efficiency_needed=(
            net_eff * statistics.fmean(p_req) / statistics.fmean(p_avail)
            if statistics.fmean(p_avail) > 0 else float("inf")))


def sweep_cases() -> list[Path]:
    if not ORBIT_CASES.is_dir():
        return []
    return sorted(p for p in ORBIT_CASES.glob("*/results/station_keeping.csv"))


def render_table(rows: list[Closure], markdown: bool) -> str:
    out: list[str] = []
    if markdown:
        out.append("| altitude | pose | ⟨drag⟩ | ⟨P required⟩ | ⟨P available⟩ | "
                   "energy margin | net cell eff. needed | closes? |")
        out.append("|---|---|---|---|---|---|---|---|")
        for r in rows:
            out.append(f"| {r.altitude_km:.0f} km | {r.rotation} | "
                       f"{r.drag_mean_nN:.2f} nN | {r.p_req_mean_mW:.1f} mW | "
                       f"{r.p_avail_mean_mW:.1f} mW | **{r.margin:.2f}** | "
                       f"{r.net_cell_efficiency_needed*100:.0f} % | "
                       f"{'**yes**' if r.closes else 'no'} |")
    else:
        out.append(f"{'alt':>6s} {'pose':>9s} {'<drag>':>9s} {'<P_req>':>9s} "
                   f"{'<P_av>':>9s} {'margin':>7s} {'eff.need':>9s}  closes?")
        out.append("-" * 72)
        for r in rows:
            out.append(f"{r.altitude_km:6.0f} {r.rotation:>9s} "
                       f"{r.drag_mean_nN:8.2f}n {r.p_req_mean_mW:8.1f}m "
                       f"{r.p_avail_mean_mW:8.1f}m {r.margin:7.2f} "
                       f"{r.net_cell_efficiency_needed*100:8.1f}%  "
                       f"{'YES' if r.closes else 'no'}")
    return "\n".join(out)


def crossover(rows: list[Closure]) -> str:
    """The altitude where the concept becomes unconditional on body-mounted cells."""
    ordered = sorted(rows, key=lambda r: r.altitude_km)
    below = [r for r in ordered if not r.closes]
    above = [r for r in ordered if r.closes]
    if not above:
        return ("No sampled altitude closes on body-mounted cells alone. The "
                "levers are a plate geometry (A_solar/A_ram >~ 10) or duty "
                "cycling; both are stated in the claim's boundaries.")
    if not below:
        return (f"Every sampled altitude closes (lowest: "
                f"{above[0].altitude_km:.0f} km at margin {above[0].margin:.2f}).")
    return (f"Crossover between {below[-1].altitude_km:.0f} km "
            f"(margin {below[-1].margin:.2f}) and {above[0].altitude_km:.0f} km "
            f"(margin {above[0].margin:.2f}): the concept is unconditional on "
            f"body-mounted cells at and above {above[0].altitude_km:.0f} km, and "
            f"needs a plate geometry or duty cycling below it.")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--csv", type=Path, nargs="*", default=None)
    ap.add_argument("--sweep", action="store_true",
                    help="every case with a station_keeping.csv under orbit_sims/")
    ap.add_argument("--markdown", action="store_true")
    ap.add_argument("--f-per-p", type=float, default=None,
                    help="override the thrust-per-watt [uN/W] (default: the mean "
                         "over every committed measured operating point)")
    args = ap.parse_args(argv)

    points = fom.measured_points()
    fps = [p.f_per_p_uN_per_W for p in points]
    f_per_p = args.f_per_p if args.f_per_p is not None else statistics.fmean(fps)

    paths = list(args.csv or [])
    if args.sweep or not paths:
        paths = sweep_cases()
    if not paths:
        raise SystemExit("no station_keeping.csv found; run orbit_sims first")

    print("=" * 74)
    print("POWER CLOSURE — can the skin run the thruster?")
    print(f"  F/P = {f_per_p:.4f} uN/W, the mean over {len(points)} committed "
          f"MEASURED operating points")
    print(f"        (range {min(fps):.3f}-{max(fps):.3f}; independent of current, "
          f"and of the collection law rung 9 falsified)")
    print("  P_available is the orbit sim's own eclipse-corrected column.")
    print("  'Closes' = orbit-MEAN energy balance, i.e. a storage buffer big "
          "enough to ride out eclipse.")
    print("=" * 74)

    rows = [analyse(p, f_per_p) for p in paths]
    for r in rows:
        print(r.describe())
        print()
    print(render_table(rows, args.markdown))
    print()
    print(crossover(rows))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
