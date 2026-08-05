# reference results -- capstone.high_thrust

`20260804T154756Z_b854dcbe/` is the curated snapshot of the **300 V ceiling run (voltage-frontier top point)**:
full production run (192,680 steps, 800 ns), GPU build,
**PASS -- all 7 required gate(s) passed** under policy `capstone.high_thrust.v1`.

Discriminates the pre-registered collection-law hypotheses: linear (31 V) and sqrt (90 V) refuted; alpha=0.82 (36 V) survives against the 36.30 V tail-averaged float. Late slope still decaying (+27 mV/ns at run end; settled float extrapolates to ~42-48 V -- see SCALING_LAWS.md section 4 verdict). Thrust 30.13 nN vs 30 pre-registered; covers the 500 km worst-case drag gate (28.4 nN).

| gate | result | status |
|---|---|---|
| beam_escapes | 98.9897 >= 95 | PASS |
| body_floats_benign | 36.3006 <= 50 | PASS |
| steady_current_balance | 0.0353352 <= 0.05 | PASS |
| momentum_sanity_bound | 0.0099833 <= 1 | PASS |
| sheath_and_plume_contained | 0.10791 <= 1 | PASS |
| scrape_ledger_consistent_with_dumps | 1.40795e-09 <= 0.02 | PASS |
| beam_escape_ledger_consistent_with_dumps | 1.48292e-09 <= 0.02 | PASS |
| covers_500km_worst_drag | 30.1328 >= 28.4 | PASS |

Provenance: run `20260804T154756Z_b854dcbe`, case `b854dcbee9697717...`,
git `277449dbe53c` (dirty: False), seed 42,
WarpX 26.5, analysis `20260805T002119Z_d81b7f96`, wall 2026-08-04T15:47:56Z -> 2026-08-04T23:02:16Z.

The machine-readable record is `metrics.json` + `verdict.json` + the frozen
`config_used.yaml` of the run they describe; `run_manifests.json` carries the
full run manifest. Raw dumps (fields h5, ledger CSV) stay out of git and are
reproducible from `config_used.yaml` + seed. A reference result is read only
for comparison; it never makes `simulation.py` skip a run. Ladder-wide caveats
(reduced ion mass, single grid/PPC/seed pending the convergence pass,
finite-time equilibrium on the ion clock) are documented in the stage README
and `SCALING_LAWS.md`.
