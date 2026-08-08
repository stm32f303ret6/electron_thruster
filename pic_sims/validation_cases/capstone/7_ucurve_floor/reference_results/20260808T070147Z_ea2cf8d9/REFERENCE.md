# reference results -- capstone.ucurve_floor

`20260808T070147Z_ea2cf8d9/` is the curated snapshot of the **78 V boundary demonstration (the throttle curve's no-go wall)**:
full production run (103,160 steps, 800 ns), GPU build,
**PASS -- all 4 required gate(s) passed** under policy `capstone.ucurve_floor.v1`.

Boundary demonstration, not an operating point (`../UCURVE_PLAN.md`): can 13.65 nN be held at 78 V at all? Measured answer: **no** -- but the wall has a different shape than either pre-registered branch. A steady equilibrium DOES form (current balance 0.035, the reported gate passes), refuting H2's no-steady-state variant; but it is starved: escape **57.43 %**, delivered thrust **10.38 nN** (-24 % vs demand), specific power **6.31 mW/nN**, and F_net/F_beam = **0.89** -- the self-scraped beam loads the body almost as hard as the exhaust pushes it. Meeting the demand would need still more current at still lower escape: the demand has no operating point at 78 V, which is the wall the flight rule's voltage floor exists to avoid. H1's 47.3 V float never materialized (measured 23.84 V).

| gate | result | status |
|---|---|---|
| momentum_sanity_bound | 0.893398 <= 1 | PASS |
| sheath_and_plume_contained | 0.0888882 <= 1 | PASS |
| scrape_ledger_consistent_with_dumps | 2.80225e-09 <= 0.02 | PASS |
| beam_escape_ledger_consistent_with_dumps | 1.00721e-09 <= 0.02 | PASS |
| steady_current_balance | 0.0348854 <= 0.05 | PASS (reported) |
| beam_escapes | 57.4309 >= 95 | FAIL (reported) |
| body_floats_benign | 23.8397 <= 50 | PASS (reported) |
| thrust_meets_demand | 10.3835 \|x - 13.65\| <= 2.05 | FAIL (reported) |

Provenance: run `20260808T070147Z_ea2cf8d9`, case `ea2cf8d9fe06b9d9...`,
git `e98048e7b90a` (dirty: True), seed 42,
WarpX 26.5, analysis `20260808T104340Z_69f040ab`, wall 2026-08-08T07:01:47Z -> 2026-08-08T10:43:40Z.

The machine-readable record is `metrics.json` + `verdict.json` + the frozen
`config_used.yaml` of the run they describe; `run_manifests.json` carries the
full run manifest. Raw dumps (fields h5, ledger CSV) stay out of git and are
reproducible from `config_used.yaml` + seed. A reference result is read only
for comparison; it never makes `simulation.py` skip a run. Ladder-wide caveats
(reduced ion mass, single grid/PPC/seed, finite-time equilibrium on the ion
clock) are documented in the stage README and `SCALING_LAWS.md`.
