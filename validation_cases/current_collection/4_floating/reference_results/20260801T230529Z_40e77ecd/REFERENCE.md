# reference result — collector.floating (passive sphere on the charge pump)

Curated snapshot of a verified run+analysis. Read only for comparison;
its presence never makes a runner skip a run. The machine-readable
record is `metrics.json` + `verdict.json` here.

## Provenance

- **stage:** `collector.floating`
- **verdict:** **PASS** (exit 0)
- **policy:** `collector.floating.v1`  sha256 `55d559a8b133eab4…`
- **analysis id:** `20260801T234243Z_55d559a8`
- **git commit:** `4d0e4489105f6ce3af872025d2239ab719bbac38` (dirty=True)
- **WarpX:** 26.5  |  **Python:** 3.12.13

## Runs

- `20260801T230529Z_40e77ecd`  case_sha256 `40e77ecdd8680b96…`

## Gates

- [PASS] `floats_to_theory_bracket` — -0.250885 in [-0.4, -0.19]
- [PASS] `floating_current_balance` — 0.00888096 <= 0.15
- [PASS] `capacitance_calibration_sane` — 1.06777 in [0.8, 1.4]
- [PASS] `scrape_ledger_consistent_with_dumps` — 4.60548e-09 <= 0.02
- [PASS] `far_density_matches_n0` — 0.999608 |x - 1| <= 0.05
- [PASS] `far_field_quasineutral` — 0.00104967 <= 0.02
- [PASS] `no_spurious_edge_sheath` — 0.00585092 <= 0.2
