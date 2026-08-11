# reference result — collector.floating

Curated snapshot of a verified run+analysis. Read only for comparison;
its presence never makes a runner skip a run. The machine-readable
record is `metrics.json` + `verdict.json` here.

## Provenance

- **stage:** `collector.floating`
- **verdict:** **PASS** (exit 0)
- **policy:** `collector.floating.v1`  sha256 `55d559a8b133eab4…`
- **analysis id:** `20260806T170238Z_55d559a8`
- **git commit:** `a91e126678127ef664a38440ebd290ab0da8c9a5` (dirty=True)
- **backend:** CUDA (GPU), 1 MPI rank, seed 42
- **WarpX:** 26.5  |  **Python:** 3.12.13

## Runs

- `20260806T162656Z_40e77ecd`  case_sha256 `40e77ecdd8680b96…`

## Gates

- [PASS] `floats_to_theory_bracket` — -0.250997 in [-0.4, -0.19]
- [PASS] `floating_current_balance` — 0.00888752 <= 0.15
- [PASS] `capacitance_calibration_sane` — 1.06777 in [0.8, 1.4]
- [PASS] `scrape_ledger_consistent_with_dumps` — 2.73339e-09 <= 0.02
- [PASS] `far_density_matches_n0` — 0.999811 |x - 1| <= 0.05
- [PASS] `far_field_quasineutral` — 0.00125526 <= 0.02
- [PASS] `no_spurious_edge_sheath` — 0.00584889 <= 0.2
