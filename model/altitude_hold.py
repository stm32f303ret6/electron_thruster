#!/usr/bin/env python3
"""Altitude hold with a REAL thruster, against free fall with none.

The station-keeping CSVs assume an ideal thruster: thrust equals drag at every
instant.  The measured thruster cannot always do that -- drag peaks can exceed
what it delivers at the tested 350 V, or within a fixed power supply.  This
replays each year-long station-keeping case with thrust capped at the
thruster's per-row capability (mission_model laws, the body's own collection
calibration) and integrates the shortfall into an altitude deficit:

    da/dt = 2 a (F_thrust - F_drag) / (m v)        (circular orbit)

Control law: below the target altitude, fire at full capability to climb
back; at the target, match drag (or as much of it as the cap allows).  The
deficit is a post-process on the held-altitude trajectory, so it is valid
while dips stay far below the density scale height (~60 km); the report flags
any case where they do not.

Against that it sets the free-fall runs (orbit_sims, mission.thruster: off):
the same orbits flown without the thruster, until re-entry or a 5-year cap.

Run:  python model/altitude_hold.py [--out model/results]
"""
from __future__ import annotations

import argparse
import csv
import json
import re
from concurrent.futures import ProcessPoolExecutor
from datetime import datetime
from pathlib import Path

import numpy as np

import mission_model as M
import scale_analysis as S

REPO = M.REPO
CASES = REPO / "orbit_sims" / "validation_cases"
V_CAP = M.V_TESTED_MAX_V
DIP_VALID_M = 5000.0          # beyond this the no-feedback deficit is not trusted


def _cfg_value(text: str, key: str, path: Path) -> str:
    m = re.search(rf"^\s*{key}:\s*['\"]?([^'\"\n#]+)", text, re.MULTILINE)
    if not m:
        raise ValueError(f"{key} not found in {path}")
    return m.group(1).strip()


def case_meta(case_dir: Path) -> dict:
    p = case_dir / "results" / "config_used.yaml"
    t = p.read_text()
    return dict(mass=float(_cfg_value(t, "mass_kg", p)),
                alt=float(_cfg_value(t, "initial_altitude_km", p)),
                inc=float(_cfg_value(t, "inclination_deg", p)),
                start=_cfg_value(t, "start_utc", p))


def orbit_key(name: str) -> tuple[str, str]:
    """('eq'|'iss'|'sso', '2024'|'2019') from the case-name suffixes."""
    orb = "iss" if "_iss" in name else "sso" if "_sso" in name else "eq"
    return orb, ("2019" if name.endswith("_2019") else "2024")


def power_capability(cal, n, Te, P_mW: float, body: str, n_v: int = 40, n_i: int = 16):
    """Max thrust per row within a power budget P [mW]: V*I <= P, I <= emission
    ceiling, V - phi >= KE_MIN.  Grid over V (floor..V_CAP) and I fractions."""
    best = np.zeros_like(n)
    for V in np.geomspace(M.V_FLOOR_V, V_CAP, n_v):
        esc = float(cal.esc_of_V(V))
        I_top = min(P_mW / V, M.R_EMIT * float(M.i_cl_mA(V)))
        for frac in np.geomspace(0.05, 1.0, n_i):
            I = I_top * frac
            phi = cal.phi_of_Iesc(esc * I * 1e-3, n, Te, body=body)
            F = np.where(V - phi >= M.KE_MIN_V, cal.thrust_nN(I, V, phi), 0.0)
            np.maximum(best, F, out=best)
    return best


def hold(F_drag_nN, F_cap_nN, P_match_mW, P_cap_mW, alt_km, mass, dt_s):
    """Integrate the altitude deficit [m] under the capped control law."""
    a = S.R_EARTH + alt_km * 1e3
    k = 2.0 * a / (mass * np.sqrt(S.MU_EARTH / a)) * dt_s * 1e-9     # m per nN per step
    deficit = np.zeros(len(F_drag_nN))
    P_used = np.zeros(len(F_drag_nN))
    d = 0.0
    for i in range(len(F_drag_nN)):
        if d < 0.0 or F_drag_nN[i] > F_cap_nN[i]:
            # Only as much thrust as restores the target within this step (a full
            # step at capability would bill power for impulse the clamp discards);
            # P scales with F at the cap, an upper bound as in run_case.
            F = min(F_cap_nN[i], F_drag_nN[i] - d / k[i])
            P = P_cap_mW[i] * F / max(F_cap_nN[i], 1e-12)
        else:
            F, P = F_drag_nN[i], P_match_mW[i]
        d = min(0.0, d + k[i] * (F - F_drag_nN[i]))
        deficit[i] = d
        P_used[i] = P
    return deficit, P_used


def run_case(cal, case_dir: Path, budget_mW: float) -> dict:
    name = case_dir.name
    meta = case_meta(case_dir)
    body = M.case_body(case_dir / "results" / "station_keeping.csv")
    rows = list(csv.DictReader(open(case_dir / "results" / "station_keeping.csv")))
    n = np.array([float(r["electron_density_m3"]) for r in rows])
    Te = np.array([float(r["electron_temperature_K"]) for r in rows])
    F = np.array([float(r["drag_N"]) for r in rows]) * 1e9
    alt = np.array([float(r["altitude_km"]) for r in rows])
    t0, t1 = (datetime.fromisoformat(rows[i]["timestamp_utc"]) for i in (0, 1))
    dt = (t1 - t0).total_seconds()

    out = dict(case=name, body=body, orbit=orbit_key(name)[0], epoch=orbit_key(name)[1],
               alt_km=meta["alt"], mass_kg=meta["mass"], drag_mean_nN=float(F.mean()),
               drag_max_nN=float(F.max()))
    # (a) the tested voltage ceiling
    F_cap, P_cap = M.capability_nN(cal, n, Te, V=V_CAP, body=body)
    op = M.operating_point(cal, F, n, Te, vmax=V_CAP, body=body)
    # Rows with no converged operating point under the cap but F <= F_cap: at fixed
    # V, F/I falls as I (and phi) rise, so P_cap * F/F_cap bounds the power from above.
    P_match = np.where(np.isfinite(op["P_mW"]), op["P_mW"],
                       P_cap * np.minimum(F / np.maximum(F_cap, 1e-12), 1.0))
    d, P = hold(F, F_cap, P_match, P_cap, alt, meta["mass"], dt)
    out["v350"] = dict(max_dip_m=abs(float(d.min())), p99_dip_m=abs(float(np.percentile(d, 1))),
                       time_in_deficit_pct=100.0 * float((d < -1.0).mean()),
                       P_mean_mW=float(P.mean()), end_deficit_m=abs(float(d[-1])))
    # (b) the example body-mounted supply, as a continuous orbit-average cap
    F_pc = power_capability(cal, n, Te, budget_mW, body)
    op_u = M.operating_point(cal, F, n, Te, body=body)
    P_match_b = np.minimum(np.where(np.isfinite(op_u["P_mW"]), op_u["P_mW"], budget_mW),
                           budget_mW)
    d, P = hold(F, F_pc, P_match_b, np.full_like(F, budget_mW), alt, meta["mass"], dt)
    out["budget"] = dict(P_budget_mW=budget_mW, max_dip_m=abs(float(d.min())),
                         p99_dip_m=abs(float(np.percentile(d, 1))),
                         time_in_deficit_pct=100.0 * float((d < -1.0).mean()),
                         P_mean_mW=float(P.mean()), end_deficit_m=abs(float(d[-1])))
    return out


def free_fall(case_dir: Path) -> dict:
    meta = case_meta(case_dir)
    p = case_dir / "results" / "free_fall.csv"
    rows = list(csv.DictReader(open(p)))
    t0 = datetime.fromisoformat(rows[0]["timestamp_utc"])
    t1 = datetime.fromisoformat(rows[-1]["timestamp_utc"])
    days = (t1 - t0).total_seconds() / 86400.0
    # Mean over a day of samples: one sample swings +-20 km with latitude on
    # inclined orbits (circular radius over an oblate Earth).
    per_day = max(1, round(86400.0 / (t1 - t0).total_seconds() * (len(rows) - 1)))
    alt = np.array([float(r["altitude_km"]) for r in rows])
    alt_first, alt_last = float(alt[:per_day].mean()), float(alt[-per_day:].mean())
    cfg = (case_dir / "results" / "config_used.yaml").read_text()
    cap = float(_cfg_value(cfg, "duration_days", case_dir))
    floor = float(_cfg_value(cfg, "decay_floor_km", case_dir))
    reentered = days < cap - 1.0
    return dict(case=case_dir.name, orbit=orbit_key(case_dir.name)[0],
                epoch=orbit_key(case_dir.name)[1], alt_km=meta["alt"], mass_kg=meta["mass"],
                body="3u" if "_3u" in case_dir.name else "slender",
                lifetime_days=days if reentered else None, reentered=reentered,
                first_day_alt_km=alt_first, final_alt_km=alt_last,
                alt_lost_km=alt_first - alt_last, cap_days=cap, floor_km=floor)


def _life(ff):
    if ff is None:
        return "—"
    if ff["reentered"]:
        d = ff["lifetime_days"]
        return f"{d:.0f} d" if d < 365.25 else f"{d/365.25:.1f} yr"
    return f"> {ff['cap_days']/365.25:.0f} yr (−{ff['alt_lost_km']:.0f} km)"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, default=REPO / "model" / "results")
    ap.add_argument("--jobs", type=int, default=8, help="cases replayed in parallel")
    args = ap.parse_args()

    cal = M.Calibration()
    slender = next(b for b in S.BODIES if b["name"].startswith("slender"))
    harvest = S.SOLAR_CONSTANT * S.CELL_EFFICIENCY * S.ILLUMINATION_DUTY
    budget_mW = harvest * slender["skin"] * S.CELL_FRACTION_OF_SKIN * 1e3

    sk = sorted(p.parent.parent for p in CASES.glob("*_station_keeping_slender*/results/station_keeping.csv"))
    holds = []
    with ProcessPoolExecutor(args.jobs) as pool:
        for h in pool.map(run_case, [cal] * len(sk), sk, [budget_mW] * len(sk)):
            holds.append(h)
            print(f"{h['case']:48s} 350V dip {h['v350']['max_dip_m']:8.0f} m | "
                  f"{budget_mW:.0f} mW dip {h['budget']['max_dip_m']:8.0f} m", flush=True)
    ffs = [free_fall(p.parent.parent) for p in sorted(CASES.glob("*_free_fall_*/results/free_fall.csv"))]
    ff_at = {(f["body"], f["orbit"], f["epoch"], f["alt_km"]): f for f in ffs}

    ORB = {"eq": "near-equatorial 0.5°", "iss": "ISS 51.6°", "sso": "sun-synchronous 10:30"}
    L = ["# Altitude hold with the real thruster vs free fall\n",
         "Generated by `model/altitude_hold.py`. Station keeping replays each",
         "slender-body year with thrust capped at the thruster's per-row",
         f"capability: (a) at the tested {V_CAP:.0f} V ceiling, (b) within the example",
         f"body-mounted solar supply of the slender can ({budget_mW:.0f} mW orbit average,",
         "`scale_analysis.py` assumptions, battery-buffered). Below the target",
         "altitude the thruster fires at full capability; the dip is the largest",
         "altitude deficit over the year. Free fall is the same orbit with the",
         "thruster off (orbit_sims `mission.thruster: off`), to re-entry at",
         "120 km or the 5-year cap. The 3U column is the slender can scaled ×10",
         "(Ø10 cm × 30 cm, 4 kg); only its free fall is simulated here.\n"]
    for orb in ("eq", "iss", "sso"):
        for ep in ("2024", "2019"):
            rows = sorted((h for h in holds if h["orbit"] == orb and h["epoch"] == ep),
                          key=lambda h: h["alt_km"])
            if not rows:
                continue
            L += [f"## {ORB[orb]}, {ep} ({'solar maximum' if ep == '2024' else 'solar minimum'})\n",
                  "| altitude | drag mean / max (nN) | free fall, slender 3.1 g | free fall, 3U 4 kg | "
                  f"hold @ {V_CAP:.0f} V: max dip / mean P | hold @ {budget_mW:.0f} mW: max dip / "
                  "time below target |",
                  "|---|---|---|---|---|---|"]
            for h in rows:
                a, b = h["v350"], h["budget"]
                fa = " ⚠" if a["max_dip_m"] > DIP_VALID_M else ""
                fb = " ⚠" if b["max_dip_m"] > DIP_VALID_M else ""
                L.append(
                    f"| {h['alt_km']:.0f} km | {h['drag_mean_nN']:.2f} / {h['drag_max_nN']:.1f} "
                    f"| {_life(ff_at.get(('slender', orb, ep, h['alt_km'])))} "
                    f"| {_life(ff_at.get(('3u', orb, ep, h['alt_km'])))} "
                    f"| {a['max_dip_m']:.0f} m / {a['P_mean_mW']:.1f} mW{fa} "
                    f"| {b['max_dip_m']:.0f} m / {b['time_in_deficit_pct']:.0f} %{fb} |")
            L.append("")
    L += [f"⚠ = dip above {DIP_VALID_M/1e3:.0f} km: the thruster cannot keep up with this drag, the",
          "deficit keeps growing and the no-feedback estimate understates it (the craft",
          "descends into denser air). Read it as \"does not hold\", not as a dip size.\n"]

    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "ALTITUDE_HOLD.md").write_text("\n".join(L) + "\n", encoding="utf-8")
    with open(args.out / "altitude_hold.json", "w") as fh:
        json.dump(dict(budget_mW=budget_mW, v_cap=V_CAP, holds=holds, free_fall=ffs), fh, indent=2)
    print(f"\nwrote {args.out / 'ALTITUDE_HOLD.md'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
