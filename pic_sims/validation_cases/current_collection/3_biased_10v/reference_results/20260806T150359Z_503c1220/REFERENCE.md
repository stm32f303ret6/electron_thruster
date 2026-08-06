# reference result — collector.biased_10v

Curated snapshot of a verified run+analysis. Read only for comparison;
its presence never makes a runner skip a run. The machine-readable
record is `metrics.json` + `verdict.json` here.

## Provenance

- **stage:** `collector.biased_10v`
- **verdict:** **PASS** (exit 0)
- **policy:** `collector.biased_10v.v1`  sha256 `fec56929cf8b7ca6…`
- **analysis id:** `20260806T162653Z_fec56929`
- **git commit:** `664747299729c3febb9f8ce32b02be7ad3ed3382` (dirty=False)
- **backend:** CUDA (GPU), 1 MPI rank, seed 42
- **WarpX:** 26.5  |  **Python:** 3.12.13

## Runs

- `20260806T150359Z_503c1220`  case_sha256 `503c1220b1e6cd58…`

## Gates

- [PASS] `electron_current_vs_oml` — 0.80881 in [0.8, 1.05]
- [PASS] `far_density_matches_n0` — 0.954148 |x - 1| <= 0.06
- [PASS] `far_field_quasineutral` — 0.00397908 <= 0.02
- [PASS] `sheath_contained` — 0.00256632 <= 0.5
