# reference result — capstone.floating_body

Curated snapshot of a verified run+analysis. Read only for comparison;
its presence never makes a runner skip a run. The machine-readable
record is `metrics.json` + `verdict.json` here.

## Provenance

- **stage:** `capstone.floating_body`
- **verdict:** **PASS** (exit 0)
- **policy:** `capstone.floating_body.v1`  sha256 `b3e25892959833cf…`
- **analysis id:** `20260801T204714Z_b3e25892`
- **git commit:** `6de15e8a06a822a9968ce39ba1a3b17d5c6dc70d` (dirty=False)
- **WarpX:** 26.5  |  **Python:** 3.12.13

## Runs

- `20260801T142601Z_2f822a95`  case_sha256 `2f822a959f20e8f5…`

## Gates

- [PASS] `beam_escapes` — 98.4364 >= 95
- [PASS] `thrust_matches_float200` — 13.6517 |x - 13.6| <= 2.04
- [PASS] `body_floats_to_float200_potential` — 16.9768 |x - 16| <= 4
- [PASS] `steady_current_balance` — 0.0316531 <= 0.05
- [PASS] `momentum_sanity_bound` — 0.00354604 <= 1
- [PASS] `sheath_and_plume_contained` — 0.037603 <= 1
- [PASS] `scrape_ledger_consistent_with_dumps` — 2.74981e-09 <= 0.02
