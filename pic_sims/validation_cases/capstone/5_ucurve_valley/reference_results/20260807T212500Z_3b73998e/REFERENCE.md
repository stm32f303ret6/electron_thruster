# reference results -- capstone.ucurve_valley

`20260807T212500Z_3b73998e/` is the curated snapshot of the **125 V fixed-thrust throttle run (the measured U-curve valley)**:
full production run (127,920 steps, 800 ns), GPU build,
**PASS -- all 5 required gate(s) passed** under policy `capstone.ucurve_valley.v1`.

First point of the pre-registered fixed-thrust slice (`../UCURVE_PLAN.md`, committed before the run): 13.65 nN demanded at 125 V with 0.464 mA (4.0x the planar perveance, 2.7x the validated ceiling). Measured: escape **93.78 %**, float **21.25 V**, delivered thrust **13.09 nN** (-4.1 % vs demand, inside the +-15 % band), exhaust 83.1 eV, specific power **4.43 mW/nN** at delivered thrust. The left-arm tax has visibly begun (escape below every frontier point) but the demand is still met. With the 92.4 V (4.79) and 200 V (5.01) points this pins the U-curve valley at ~125 V -- refuting the calibrated laws' tax-free valley (~95 V, H1) in favor of the perveance-tax branch (H2).

| gate | result | status |
|---|---|---|
| steady_current_balance | 0.033772 <= 0.05 | PASS |
| momentum_sanity_bound | 0.0625282 <= 1 | PASS |
| sheath_and_plume_contained | 0.0723367 <= 1 | PASS |
| scrape_ledger_consistent_with_dumps | 7.16571e-10 <= 0.02 | PASS |
| beam_escape_ledger_consistent_with_dumps | 1.79725e-09 <= 0.02 | PASS |
| beam_escapes | 93.7835 >= 95 | FAIL (reported) |
| body_floats_benign | 21.2505 <= 50 | PASS (reported) |
| thrust_meets_demand | 13.0923 \|x - 13.65\| <= 2.05 | PASS (reported) |

Provenance: run `20260807T212500Z_3b73998e`, case `3b73998e930520d4...`,
git `9e1240cb1089` (dirty: False), seed 42,
WarpX 26.5, analysis `20260808T023751Z_4e7cc7e0`, wall 2026-08-07T21:25:00Z -> 2026-08-08T02:37:50Z.

The machine-readable record is `metrics.json` + `verdict.json` + the frozen
`config_used.yaml` of the run they describe; `run_manifests.json` carries the
full run manifest. Raw dumps (fields h5, ledger CSV) stay out of git and are
reproducible from `config_used.yaml` + seed. A reference result is read only
for comparison; it never makes `simulation.py` skip a run. Ladder-wide caveats
(reduced ion mass, single grid/PPC/seed, finite-time equilibrium on the ion
clock) are documented in the stage README and `SCALING_LAWS.md`.
