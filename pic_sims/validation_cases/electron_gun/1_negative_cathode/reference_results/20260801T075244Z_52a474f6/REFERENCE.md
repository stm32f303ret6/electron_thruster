# reference result — emitter.negative_cathode

Curated snapshot of a verified run+analysis. Read only for comparison;
its presence never makes a runner skip a run. The machine-readable
record is `metrics.json` + `verdict.json` here.

## Provenance

- **stage:** `emitter.negative_cathode`
- **verdict:** **PASS** (exit 0)
- **policy:** `emitter.negative_cathode.v1`  sha256 `82f1d1156378bd75…`
- **analysis id:** `20260801T075527Z_82f1d115`
- **git commit:** `444ecb8ee581c1a6016f177b5cd9c253ad92604e` (dirty=True)
- **WarpX:** 26.5  |  **Python:** 3.12.13

## Runs

- `20260801T075244Z_52a474f6`  case_sha256 `52a474f69f5d3acb…`

## Gates

- [PASS] `collector_current_matches_emitted` — 1.00018 in [0.995, 1.005]
- [PASS] `collector_ke_matches_analytic` — 0.0275687 |x - 0| <= 0.5
- [PASS] `cathode_return_fraction_small` — 0 <= 0.0001
- [PASS] `radial_wall_fraction_small` — 3.03591e-07 <= 0.0001
- [PASS] `vacuum_phi_matches_laplace_ramp` — 3.51035e-05 <= 0.01
- [PASS] `space_charge_depression_regression` — 0.092083 |x - 0.092| <= 0.04
- [PASS] `particle_budget_closure` — 0.000751032 |x - 0| <= 0.1
