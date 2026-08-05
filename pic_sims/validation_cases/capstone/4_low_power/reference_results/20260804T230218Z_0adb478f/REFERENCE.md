# reference results -- capstone.low_power

`20260804T230218Z_0adb478f/` is the curated snapshot of the **100 V floor run (voltage-frontier cheap end)**:
full production run (115,480 steps, 800 ns), GPU build,
**PASS -- all 7 required gate(s) passed** under policy `capstone.low_power.v1`.

Measures the frontier's power-optimal end: 3.42 nN at 12.1 mW (0.283 uN/W), on the 3.4 nN pre-registered prediction. Escape degrades to 96.1 % exactly as the U-curve tax predicts but clears the 95 % gate: the floor operating point is feasible. Float 5.40 V (settles toward ~6.0 V), completing the F/P ~ 1/sqrt(V) confirmation across the full hardware range.

| gate | result | status |
|---|---|---|
| beam_escapes | 96.1196 >= 95 | PASS |
| body_floats_benign | 5.39572 <= 50 | PASS |
| steady_current_balance | 0.0148582 <= 0.05 | PASS |
| momentum_sanity_bound | 0.0882927 <= 1 | PASS |
| sheath_and_plume_contained | 0.00580626 <= 1 | PASS |
| scrape_ledger_consistent_with_dumps | 7.3284e-09 <= 0.02 | PASS |
| beam_escape_ledger_consistent_with_dumps | 5.28779e-09 <= 0.02 | PASS |
| covers_600km_mean_drag | 3.4191 >= 2 | PASS |

Provenance: run `20260804T230218Z_0adb478f`, case `0adb478f9d7b9a66...`,
git `277449dbe53c` (dirty: False), seed 42,
WarpX 26.5, analysis `20260805T045648Z_ff61c01a`, wall 2026-08-04T23:02:18Z -> 2026-08-05T03:58:33Z.

The machine-readable record is `metrics.json` + `verdict.json` + the frozen
`config_used.yaml` of the run they describe; `run_manifests.json` carries the
full run manifest. Raw dumps (fields h5, ledger CSV) stay out of git and are
reproducible from `config_used.yaml` + seed. A reference result is read only
for comparison; it never makes `simulation.py` skip a run. Ladder-wide caveats
(reduced ion mass, single grid/PPC/seed pending the convergence pass,
finite-time equilibrium on the ion clock) are documented in the stage README
and `SCALING_LAWS.md`.
