# reference results — capstone.slender_body (geometry axis)

`20260806T011847Z_5670e54c/` is the curated snapshot of the **slender-body
geometry run**: the capstone deck with the can lengthened to Ø10 × 30.5 mm
(L/r = 6) at the SAME drive and demand as the 200 V anchor — full production
run (159,160 steps, 800 ns), GPU build, **PASS — all 6 required gate(s)
passed** under policy `capstone.exploratory_axes.v1`.

## The pre-registered question, and the answer

`capstone/SLENDER_BODY_PLAN.md` recorded two competing hypotheses **before the
run**, for where the float settles when total skin area grows 3.24×
(3.4 → 11.0 cm²) at fixed escaped current:

| hypothesis | predicted φ | outcome |
|---|---|---|
| **A — area-only scaling** (the can's fitted α holds; enhancement demand drops 3.24×) | **≈ 4–5 V** | **CONFIRMED** |
| B — cylinder-limit lateral (wall collects at α ≈ 0.5) | tens of volts, possibly above the 50 V benign gate | refuted |

Measured **φ = 4.378 V** tail-averaged (4.789 V at run end). The area
arithmetic predicts 4.66 V at α = 0.893 (tail fit) and 4.14 V at α = 0.82
(settled fit); the measurement sits between them. Hypothesis B is refuted by
an order of magnitude.

**Settle caveat (as pre-registered).** φ is still rising at run end:
+3.7 / +4.7 / +7.3 / +4.4 mV/ns over the 400–600, 600–700, 700–750, 750–800 ns
windows. The settled float is plausibly ~5–6 V — still ~3× below the anchor and
far below hypothesis B, so the discrimination is robust to the caveat, but the
point value should be quoted as a band, not a number.

## Why it matters: elongation is not paid for in thrust

Against the 200 V squat-can anchor, at identical drive (−200 V), identical
commanded current (0.342 mA), identical plasma row, seed, and grid:

| | squat can (anchor) | slender can | |
|---|---|---|---|
| outer skin | 3.17 cm² | 11.0 cm² | 3.24× |
| ram silhouette (what drag charges for) | Ø10 mm cap | Ø10 mm cap | **unchanged** |
| φ_body | 16–17.7 V | **4.38 V** | 3.9× lower |
| escape fraction | 98.5 % | 98.42 % | unchanged |
| exhaust KE | ~147 eV | **159.7 eV** | +8.6 % |
| F_beam | 13.6 nN | **14.22 nN** | +4.6 % |

The slender body floats nearly 4× lower **and makes slightly more thrust**,
because less of the 200 V drive is lost to the float (KE = κ·(V − φ)). Drag
still charges only for the ram silhouette, which did not change. This is the
measured basis for the paper's "geometry lever" argument.

## Gates

| gate | result | status |
|---|---|---|
| beam_escapes | 98.4244 >= 95 | PASS |
| steady_current_balance | 0.0204476 <= 0.05 | PASS |
| momentum_sanity_bound | 0.0135117 <= 1 | PASS |
| sheath_and_plume_contained | 0.0214015 <= 1 | PASS |
| scrape_ledger_consistent_with_dumps | 2.60234e-10 <= 0.02 | PASS |
| beam_escape_ledger_consistent_with_dumps | 7.52767e-10 <= 0.02 | PASS |
| phi_vs_float200_reference (reported) | 4.37844, \|x − 16\| <= 4 | FLAG |
| benign_float (reported) | 4.37844 <= 50 | PASS |
| thrust_vs_float200_reference (reported) | 14.2241, \|x − 13.6\| <= 2.04 | PASS |

The `phi_vs_float200_reference` flag is the **intended** outcome, not a
failure: that gate is the float200 regression anchor, retained as a reported
(non-required) comparison precisely because φ is the measurement here. See the
header of `acceptance_used.yaml`.

## Geometry provenance

This run required a code change, committed **before** it launched: the optional
`geometry.cathode_standoff` key (`helpers.py`), which pins the cathode–lid gun
gap while the can grows around it. Without it, lengthening the can stretches the
gap and Child–Langmuir (`I_CL ∝ 1/d²`) chokes the emitter — the failure mode
that killed the first attempt (see the AMENDMENT in `SLENDER_BODY_PLAN.md`).
Here the gap is 4.70 mm and the demand/ceiling ratio is 1.457, matching the
anchor's measured 1.46.

Provenance: run `20260806T011847Z_5670e54c`, case `5670e54c9cb4b6fb...`,
git `a7f4106cc476` (dirty: False), seed 42, WarpX 26.5,
analysis `20260806T140956Z_aae666a6`,
wall 2026-08-06T01:18:47Z → 2026-08-06T14:08:24Z (12 h 50 min; the last ~3 h
shared the GPU with lower-rung ladder runs).

The machine-readable record is `metrics.json` + `verdict.json` + the frozen
`config_used.yaml` of the run they describe; `run_manifests.json` carries the
manifest, and `acceptance_used.yaml` the exact policy text that was applied.
