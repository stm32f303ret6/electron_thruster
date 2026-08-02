# reference result — collector.biased_10v

Curated snapshot of a verified run+analysis. Read only for comparison;
its presence never makes a runner skip a run. The machine-readable
record is `metrics.json` + `verdict.json` here.

## Provenance

- **stage:** `collector.biased_10v`
- **verdict:** **PASS** (exit 0)
- **policy:** `collector.biased_10v.v1`  sha256 `fec56929cf8b7ca6…`
- **analysis id:** `20260801T110639Z_fec56929`
- **git commit:** `f722354e3cdb13054854bcb9f43611814a7b0d0b` (dirty=True)
- **WarpX:** 26.5  |  **Python:** 3.12.13

## Runs

- `20260801T094632Z_503c1220`  case_sha256 `503c1220b1e6cd58…`

## Gates

- [PASS] `electron_current_vs_oml` — 0.808978 in [0.8, 1.05]
- [PASS] `far_density_matches_n0` — 0.954403 |x - 1| <= 0.06
- [PASS] `far_field_quasineutral` — 0.00390646 <= 0.02
- [PASS] `sheath_contained` — 0.00305679 <= 0.5
