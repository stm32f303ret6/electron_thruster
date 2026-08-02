#!/usr/bin/env python3
r"""refit_laws.py — fit the design constants from the promoted PIC records.

    python3 refit_laws.py                    # show the fit, write nothing
    python3 refit_laws.py --write            # regenerate calibration/laws.yaml
    python3 refit_laws.py --check            # exit 1 if laws.yaml is stale

THIS IS THE ONLY WRITER OF ``calibration/laws.yaml``.

Each constant is an exact algebraic inversion of one measured operating point
(see :func:`opmodel.anchor_constants`); with several records the fit is the
weighted mean across them and the spread is reported, because a constant that
moves between operating points is a law-form problem, not a precision problem,
and the spread is the only place that shows.

    k          = F_beam / (I_beam * sqrt(KE))
    ke_ledger  = KE / (V - phi)
    f_esc      = escape_pct / 100
    beta       = f_esc * I_beam / (I_the(n,Te) * (1 + e*phi/kTe))

Every constant is written with the in-tree ``metrics.json`` it came from and
that file's SHA-256, which is what makes ``calibration.load_laws()`` able to
refuse a constant whose evidence has moved or vanished.

CHANGING A CONSTANT INVALIDATES DOWNSTREAM EVIDENCE. A PIC stage that gated a
prediction made with the old constants is no longer testing the model that now
exists; it needs a new policy version and fresh runs. ``--write`` says so out
loud every time.

Depends on: PyYAML, scipy.
"""

from __future__ import annotations

import argparse
import datetime as _dt
import math
import statistics
import sys
from pathlib import Path

DESIGN_ROOT = Path(__file__).resolve().parent
REPO_ROOT = DESIGN_ROOT.parent
sys.path.insert(0, str(DESIGN_ROOT))

import yaml  # noqa: E402

import opmodel  # noqa: E402
from calibration import CALIB_DIR, load_runs, sha256_of  # noqa: E402

LAWS_PATH = CALIB_DIR / "laws.yaml"

#: Which record field each constant is derived from, for the provenance block.
_METRIC_FOR = {
    "k": "f_beam_nN / (i_beam_mA * sqrt(exhaust_ke_mean_eV))",
    "ke_ledger": "exhaust_ke_mean_eV / (V_drive - phi_body_V)",
    "f_esc": "escape_fraction_pct / 100",
    "beta": "f_esc * i_beam / (I_the(n0, Te_K) * (1 + e*phi_body_V/kTe))",
}


def hull_area_m2(r_probe: float, z_bot: float, z_top: float) -> float:
    """Convex-hull area of the can: side wall + both end caps [m^2].

    This is the conducting area an unmagnetised plasma sees. The lid's exhaust
    hole does not change the hull, so the perforation is deliberately ignored.
    """
    height = z_top - z_bot
    return 2.0 * math.pi * r_probe * height + 2.0 * math.pi * r_probe ** 2


def constants_from_record(rec: dict) -> dict:
    """Invert the laws at one promoted record's operating point."""
    m, drive, plasma, geo = rec["measured"], rec["drive"], rec["plasma"], rec["geometry"]
    area = hull_area_m2(float(geo["r_probe_m"]), float(geo["z_bot_m"]),
                        float(geo["z_top_m"]))
    out = opmodel.anchor_constants(
        f_beam_nN=float(m["f_beam_nN"]),
        phi_body_V=float(m["phi_body_V"]),
        escape_fraction_pct=float(m["escape_pct"]),
        exhaust_ke_eV=float(m["exhaust_ke_eV"]),
        i_beam_A=float(drive["i_beam_A"]),
        v_drive_V=float(drive["voltage_V"]),
        n_e=float(plasma["n0_m3"]), Te_K=float(plasma["Te_K"]), area_m2=area)
    out["area_m2"] = area
    out["capacitance_F"] = opmodel.analytic_capacitance_F(float(geo["r_probe_m"]))
    return out


def fit(records: dict[str, dict]) -> tuple[dict, dict]:
    """Fit each constant across every record. Returns (values, per-record table)."""
    if not records:
        raise SystemExit(
            "no promoted records under calibration/runs/. Run promote.py first; "
            "laws.yaml is generated from measurements, never hand-written.")
    table = {name: constants_from_record(rec) for name, rec in sorted(records.items())}

    def _mean(key: str) -> float:
        return statistics.fmean(t[key] for t in table.values())

    values = {key: _mean(key)
              for key in ("k", "ke_ledger", "f_esc", "beta", "area_m2",
                          "capacitance_F")}
    values["k_ideal"] = _ideal_k(records)
    return values, table


def _ideal_k(records: dict[str, dict]) -> float:
    """The analytic ceiling of ``k``: every electron escapes with the full gap.

    ``F = I*m_e*v/e`` with ``v = sqrt(2eV/m_e)``, rewritten in the law's units
    (nN, mA, sqrt(eV)) is a pure constant: ``k_ideal = 1e6*sqrt(2*m_e/e)``.
    Independent of the records, but computed here so nothing is hand-typed.
    """
    return 1e6 * math.sqrt(2.0 * opmodel.ME / opmodel.E)


def spreads(table: dict[str, dict]) -> dict[str, float]:
    """|ln(max/min)| per constant across records: 0 for a single record."""
    out = {}
    for key in ("k", "ke_ledger", "f_esc", "beta"):
        vals = [t[key] for t in table.values() if t[key] > 0]
        out[key] = abs(math.log(max(vals) / min(vals))) if len(vals) > 1 else 0.0
    return out


HEADER = """\
# =============================================================================
# laws.yaml -- the design constants, GENERATED by design_sims/refit_laws.py.
#
# DO NOT HAND-EDIT. Every constant here is an exact algebraic inversion of a
# measurement in a committed pic_sims analysis, and every entry names the
# metrics.json it came from plus that file's SHA-256. calibration/__init__.py
# REFUSES to load a constant without that pair, so an entry cannot quietly
# outlive its evidence.
#
# The predecessor's laws.yaml stated the rule -- "an entry without provenance is
# an assumption wearing a measurement's clothes" -- and then shipped anyway with
# every cited run deleted. That state is now unloadable rather than merely
# documented.
#
# THE LAWS
#   thrust      F[nN]     = k * I[mA] * sqrt(KE[eV]),  KE = ke_ledger*(V - phi)
#   escape      I_escape  = f_esc * I_beam
#   collection  I_return  = beta * I_the(n_e,Te) * (1 + e*phi/kTe)
#               I_the     = e * A * n_e * sqrt(kTe/(2*pi*m_e))
#   body        tau       ~ C * phi / I          (settle time; advisory only)
#
# CHANGING A CONSTANT INVALIDATES DOWNSTREAM EVIDENCE. Any pic_sims stage that
# gated a prediction made with the previous values is no longer testing the
# model that now exists: it needs a new policy version and fresh runs.
# =============================================================================
"""


def render(values: dict, table: dict, records: dict[str, dict],
           now: _dt.datetime) -> str:
    sp = spreads(table)
    fitted_from = sorted(records)

    def prov(constant: str) -> dict:
        # With one record the provenance is that record; with several, the first
        # is named as the anchor and `fitted_from` lists them all.
        anchor = records[fitted_from[0]]["source"]
        return {
            "anchored_to": anchor["metrics_path"],
            "sha256": anchor["metrics_sha256"],
            "metric": _METRIC_FOR[constant],
            "fitted_from": fitted_from,
            "spread_log": round(sp[constant], 6),
        }

    doc = {
        "generated_utc": now.replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "generator": "design_sims/refit_laws.py",
        "n_records": len(records),
        "thrust": {
            "k": float(f"{values['k']:.6g}"),
            "k_ideal": float(f"{values['k_ideal']:.6g}"),
            "ke_ledger": float(f"{values['ke_ledger']:.6g}"),
            "units": "F[nN] = k * I[mA] * sqrt(KE[eV]); KE = ke_ledger*(V - phi)",
            "provenance": {"k": prov("k"), "ke_ledger": prov("ke_ledger")},
        },
        "beam": {
            "f_esc": float(f"{values['f_esc']:.6g}"),
            "units": "I_escape = f_esc * I_beam",
            "provenance": {"f_esc": prov("f_esc")},
        },
        "collection": {
            "beta": float(f"{values['beta']:.6g}"),
            "area_m2": float(f"{values['area_m2']:.6g}"),
            "units": ("I_return = beta * I_the * (1 + e*phi/kTe); "
                      "I_the = e*A*n_e*sqrt(kTe/(2*pi*m_e))"),
            "provenance": {"beta": prov("beta"),
                           "area_m2": dict(prov("beta"),
                                           metric="2*pi*r*(z_top-z_bot) + 2*pi*r^2 "
                                                  "from the frozen run geometry")},
        },
        "body": {
            "capacitance_F": float(f"{values['capacitance_F']:.6g}"),
            "units": "F; advisory only -- sets the settle time tau ~ C*phi/I",
            "provenance": {"capacitance_F": dict(
                prov("beta"),
                metric="4*pi*eps0*r_probe from the frozen run geometry")},
        },
    }
    return HEADER + yaml.safe_dump(doc, sort_keys=False, default_flow_style=False)


def report(values: dict, table: dict) -> str:
    lines = ["fitted constants:"]
    for key in ("k", "k_ideal", "ke_ledger", "f_esc", "beta"):
        lines.append(f"  {key:<12s} {values[key]:.6g}")
    lines.append(f"  {'area_m2':<12s} {values['area_m2']:.6g} "
                 f"({values['area_m2']*1e4:.4f} cm^2)")
    lines.append(f"  {'capacitance':<12s} {values['capacitance_F']*1e12:.4f} pF")
    lines.append(f"  k / k_ideal  {values['k']/values['k_ideal']:.4f} "
                 f"(the escape + injection-offset penalty)")
    lines.append("per record:")
    for name, t in sorted(table.items()):
        lines.append(f"  {name}: k={t['k']:.4f} ke_ledger={t['ke_ledger']:.4f} "
                     f"f_esc={t['f_esc']:.4f} beta={t['beta']:.4f} "
                     f"(I_the={t['i_the_A']*1e6:.3f} uA, chi={t['chi']:.1f})")
    sp = spreads(table)
    if any(v > 0 for v in sp.values()):
        lines.append("spread |ln(max/min)| across records: "
                     + ", ".join(f"{k}={v:.4f}" for k, v in sorted(sp.items())))
    return "\n".join(lines)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--write", action="store_true", help="regenerate laws.yaml")
    ap.add_argument("--check", action="store_true",
                    help="exit 1 if laws.yaml differs from the current fit")
    args = ap.parse_args(argv)

    records = load_runs()
    values, table = fit(records)
    print(report(values, table))

    if not (args.write or args.check):
        return 0

    now = _dt.datetime.now(_dt.timezone.utc)
    text = render(values, table, records, now)

    if args.check:
        if not LAWS_PATH.is_file():
            print(f"\n[STALE] {LAWS_PATH} does not exist", file=sys.stderr)
            return 1
        old = LAWS_PATH.read_text(encoding="utf-8")
        # generated_utc changes every run; compare everything else.
        def _strip(t: str) -> str:
            return "\n".join(ln for ln in t.splitlines()
                             if not ln.startswith("generated_utc:"))
        if _strip(old) != _strip(text):
            print(f"\n[STALE] {LAWS_PATH} does not match the current fit; "
                  f"run refit_laws.py --write", file=sys.stderr)
            return 1
        print(f"\n[OK] {LAWS_PATH} matches the current fit")
        return 0

    LAWS_PATH.write_text(text, encoding="utf-8")
    print(f"\nwrote {LAWS_PATH}  (sha256 {sha256_of(LAWS_PATH)[:12]}...)")
    print("REMINDER: any pic_sims stage that froze the PREVIOUS constants into "
          "its config and gated a prediction against them is now validating a "
          "model that no longer exists. Bump that stage's policy version and "
          "re-run it; do not retro-fit the gate.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
