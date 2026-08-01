#!/usr/bin/env python3
"""Cross-stage checks for the validation ladder.

These read the machine-readable ``metrics.json`` of each COMPLETE stage analysis
(and the frozen run configs) and assert the relationships the ladder as a whole
is supposed to demonstrate: the collector current-fraction trend, the
sheath-radius ordering, shared plasma parameters, and emitter transmission
consistency.  Each check is PASS / FAIL / SKIP (SKIP when the stages it compares
were not all run and passing).  No physics formula lives here beyond simple
orderings; the numbers come from the stages' own metrics.
"""

from __future__ import annotations

import math
from pathlib import Path
from typing import Optional

import ladder_contract as lc
from ladder import STAGE_BY_ID

PASS, FAIL, SKIP = lc.GATE_PASS, lc.GATE_FAIL, lc.GATE_SKIP


def _stage_passed(results: dict, stage_id: str) -> bool:
    return results.get(stage_id, {}).get("verdict_status") == lc.V_PASS


def _metrics(results: dict, root: Path, stage_id: str) -> dict[str, float]:
    """id -> value for the OK metrics of a passing stage's analysis."""
    res = results.get(stage_id, {})
    mpath = res.get("metrics_path")
    if not mpath:
        return {}
    doc = lc.read_json_strict(root / mpath)
    out = {}
    for m in doc["metrics"]:
        if m["status"] == "OK" and m["value"] is not None:
            out[m["id"]] = float(m["value"])
    return out


def _run_config(results: dict, stage_id: str, run_index: int = 0) -> Optional[dict]:
    res = results.get(stage_id, {})
    run_ids = res.get("run_ids") or []
    if run_index >= len(run_ids):
        return None
    stage = STAGE_BY_ID.get(stage_id)
    if stage is None:
        return None
    cfg_path = stage.path / "outputs" / run_ids[run_index] / "config_used.yaml"
    if not cfg_path.is_file():
        return None
    import yaml
    return yaml.safe_load(cfg_path.read_text(encoding="utf-8"))


def _result(id: str, status: str, detail: str) -> dict:
    return {"id": id, "status": status, "detail": detail}


# ----------------------------------------------------------------------
# individual checks
# ----------------------------------------------------------------------

def _collector_current_trend(results, root) -> dict:
    stages = ["collector.thermal", "collector.biased_3v", "collector.biased_10v"]
    if not all(_stage_passed(results, s) for s in stages):
        return _result("collector_current_fraction_trend", SKIP,
                       "not all collector stages passed")
    fracs = []
    for s in stages:
        m = _metrics(results, root, s)
        v = m.get("electron_current_over_oml")
        if v is None:
            return _result("collector_current_fraction_trend", SKIP,
                           f"{s}: no electron_current_over_oml metric")
        fracs.append(v)
    tol = 0.02  # noise floor on the monotone trend
    ok = fracs[0] >= fracs[1] - tol and fracs[1] >= fracs[2] - tol
    return _result(
        "collector_current_fraction_trend", PASS if ok else FAIL,
        f"I_e/pred 0V={fracs[0]:.3f} >= 3V={fracs[1]:.3f} >= 10V={fracs[2]:.3f} "
        f"(barrier deepening with chi)")


def _sheath_radius_ordering(results, root) -> dict:
    pairs = [("collector.biased_3v", 3.0), ("collector.biased_10v", 10.0)]
    if not all(_stage_passed(results, s) for s, _ in pairs):
        return _result("collector_sheath_radius_ordering", SKIP,
                       "biased collector stages not both passed")
    radii = []
    for s, _ in pairs:
        m = _metrics(results, root, s)
        r = m.get("sheath_radius_mm")
        if r is None or not math.isfinite(r):
            return _result("collector_sheath_radius_ordering", SKIP,
                           f"{s}: no finite sheath radius")
        radii.append(r)
    ok = radii[1] >= radii[0]
    return _result("collector_sheath_radius_ordering", PASS if ok else FAIL,
                   f"sheath radius 3V={radii[0]:.2f} mm <= 10V={radii[1]:.2f} mm")


def _shared_plasma(results, root) -> dict:
    stages = ["collector.thermal", "collector.biased_3v", "collector.biased_10v"]
    present = [s for s in stages if _stage_passed(results, s)]
    if len(present) < 2:
        return _result("collector_shared_plasma_parameters", SKIP,
                       "fewer than two collector stages passed")
    ref = None
    for s in present:
        cfg = _run_config(results, s)
        if cfg is None:
            return _result("collector_shared_plasma_parameters", SKIP,
                           f"{s}: frozen config unavailable")
        key = (cfg["plasma"], cfg["numerics"]["ppc"], cfg["probe"]["radius"])
        key_hash = lc.config_sha256({"plasma": cfg["plasma"],
                                     "ppc": cfg["numerics"]["ppc"],
                                     "radius": cfg["probe"]["radius"]})
        if ref is None:
            ref = key_hash
        elif key_hash != ref:
            return _result("collector_shared_plasma_parameters", FAIL,
                           f"{s} plasma/ppc/probe differs from the first stage")
    return _result("collector_shared_plasma_parameters", PASS,
                   f"{len(present)} collector stages share plasma/ppc/probe radius")


def _emitter_transmission(results, root) -> dict:
    if not (_stage_passed(results, "emitter.negative_cathode")
            and _stage_passed(results, "emitter.holed_anode")):
        return _result("emitter_low_current_transmission_consistency", SKIP,
                       "both emitter stages not passed")
    nc = _metrics(results, root, "emitter.negative_cathode")
    ha = _metrics(results, root, "emitter.holed_anode")
    plain = nc.get("collector_current_over_emitted")
    holed_a = ha.get("A_low_current_small_hole__collector_fraction")
    if plain is None or holed_a is None:
        return _result("emitter_low_current_transmission_consistency", SKIP,
                       "required emitter metrics missing")
    # The stiff low-current beam reaches the collector at ~100% without the
    # plate and still >= 95% through the small hole (only the thermal tail clips).
    ok = plain >= 0.98 and holed_a >= 0.95 and holed_a <= plain + 0.02
    return _result(
        "emitter_low_current_transmission_consistency", PASS if ok else FAIL,
        f"no-plate={plain:.3f}, holed(A)={holed_a:.3f} "
        f"(hole clips only the thermal tail)")


_CHECKS = (_collector_current_trend, _sheath_radius_ordering, _shared_plasma,
           _emitter_transmission)


def evaluate(results: dict, root: Path) -> list[dict]:
    """Run every cross-stage check; return their results in declaration order."""
    return [check(results, root) for check in _CHECKS]
