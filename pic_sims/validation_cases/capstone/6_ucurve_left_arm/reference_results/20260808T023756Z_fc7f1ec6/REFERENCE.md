# reference results -- capstone.ucurve_left_arm

`20260808T023756Z_fc7f1ec6/` is the curated snapshot of the **92.4 V fixed-thrust throttle run (the measured left arm)**:
full production run (111,400 steps, 800 ns), GPU build,
**PASS -- all 5 required gate(s) passed** under policy `capstone.ucurve_left_arm.v1`.

The pre-registered discriminator (`../UCURVE_PLAN.md`): H1 put the specific-power valley at ~95 V (P/F here BELOW the 125 V point); H2 put it right of here. Measured: escape **79.95 %** (H2's collapse), float 23.72 V, delivered thrust **11.59 nN** (-15 % vs the 13.65 nN demand -- the reported `thrust_meets_demand` gate records the shortfall), specific power **4.79 mW/nN** at delivered thrust -- ABOVE the 125 V point's 4.43. **The sign of P/F(92.4) - P/F(125) settles the discrimination for H2**: the left arm exists, and the untaxed servo constant (2a+1)/a underestimates V_opt. F_net/F_beam rose to 0.30 (self-scraped beam loading the body) while every accounting gate held at 1e-9.

| gate | result | status |
|---|---|---|
| steady_current_balance | 0.0342283 <= 0.05 | PASS |
| momentum_sanity_bound | 0.304871 <= 1 | PASS |
| sheath_and_plume_contained | 0.0892366 <= 1 | PASS |
| scrape_ledger_consistent_with_dumps | 3.60938e-09 <= 0.02 | PASS |
| beam_escape_ledger_consistent_with_dumps | 1.93954e-09 <= 0.02 | PASS |
| beam_escapes | 79.9462 >= 95 | FAIL (reported) |
| body_floats_benign | 23.7157 <= 50 | PASS (reported) |
| thrust_meets_demand | 11.5869 \|x - 13.65\| <= 2.05 | FAIL (reported) |

Provenance: run `20260808T023756Z_fc7f1ec6`, case `fc7f1ec6a45aaf01...`,
git `9e1240cb1089` (dirty: True), seed 42,
WarpX 26.5, analysis `20260808T070143Z_ca8fe1f2`, wall 2026-08-08T02:37:56Z -> 2026-08-08T07:01:42Z.

The machine-readable record is `metrics.json` + `verdict.json` + the frozen
`config_used.yaml` of the run they describe; `run_manifests.json` carries the
full run manifest. Raw dumps (fields h5, ledger CSV) stay out of git and are
reproducible from `config_used.yaml` + seed. A reference result is read only
for comparison; it never makes `simulation.py` skip a run. Ladder-wide caveats
(reduced ion mass, single grid/PPC/seed, finite-time equilibrium on the ion
clock) are documented in the stage README and `SCALING_LAWS.md`.
