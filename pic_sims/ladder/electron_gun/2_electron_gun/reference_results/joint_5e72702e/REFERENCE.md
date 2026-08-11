# reference result — emitter.holed_anode

Curated snapshot of a verified run+analysis. Read only for comparison;
its presence never makes a runner skip a run. The machine-readable
record is `metrics.json` + `verdict.json` here.

## Provenance

- **stage:** `emitter.holed_anode`
- **verdict:** **PASS** (exit 0)
- **policy:** `emitter.holed_anode.v1`  sha256 `8d7328dab7a2d54a…`
- **analysis id:** `20260801T075205Z_8d7328da`
- **git commit:** `444ecb8ee581c1a6016f177b5cd9c253ad92604e` (dirty=True)
- **WarpX:** 26.5  |  **Python:** 3.12.13

## Runs

- `20260801T073527Z_A_low_current_small_hole_2a105ad7` (scenario `A_low_current_small_hole`)  case_sha256 `2a105ad751e56d9c…`  study_sha256 `c3f07e2d61be43a6…`
- `20260801T073859Z_B_high_current_small_hole_e7f68b18` (scenario `B_high_current_small_hole`)  case_sha256 `e7f68b18493a387d…`  study_sha256 `c3f07e2d61be43a6…`
- `20260801T074128Z_C_high_current_big_hole_4eb710e4` (scenario `C_high_current_big_hole`)  case_sha256 `4eb710e4b80efa86…`  study_sha256 `c3f07e2d61be43a6…`

## Gates

- [PASS] `A_collector_transmits` — 0.972831 >= 0.96
- [PASS] `A_anode_clip_is_thermal_tail_only` — 0.0270872 <= 0.04
- [PASS] `B_collector_drops_vs_A` — 0.0730272 >= 0.03
- [PASS] `B_loss_lands_on_anode` — 0.100409 >= 0.04
- [PASS] `C_big_hole_restores_transmission` — 1.0001 >= 0.98
- [PASS] `C_anode_clip_below_B` — 0.100408 >= 0
- [PASS] `A_collector_ke_conserved` — -0.0246276 |x - 0| <= 1.5
- [PASS] `B_collector_ke_conserved` — -0.0250208 |x - 0| <= 1.5
- [PASS] `C_collector_ke_conserved` — 0.0217158 |x - 0| <= 1.5
- [PASS] `A_budget_closure` — 0.000751032 |x - 0| <= 0.1
- [PASS] `B_budget_closure` — 0.000751032 |x - 0| <= 0.1
- [PASS] `C_budget_closure` — 0.000751032 |x - 0| <= 0.1
