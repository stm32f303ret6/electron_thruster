# reference result — collector.biased_3v

Curated snapshot of a verified run+analysis. Read only for comparison;
its presence never makes a runner skip a run. The machine-readable
record is `metrics.json` + `verdict.json` here.

## Provenance

- **stage:** `collector.biased_3v`
- **verdict:** **PASS** (exit 0)
- **policy:** `collector.biased_3v.v1`  sha256 `fe1c00b426b49929…`
- **analysis id:** `20260806T150357Z_fe1c00b4`
- **git commit:** `91052aab12ea443fd58dfac12e94966035b3adbe` (dirty=False)
- **backend:** CUDA (GPU), 1 MPI rank, seed 42
- **WarpX:** 26.5  |  **Python:** 3.12.13

## Runs

- `20260806T142605Z_1a87cbce`  case_sha256 `1a87cbceda027f43…`

## Gates

- [PASS] `electron_current_vs_oml` — 0.8522 in [0.85, 1.05]
- [PASS] `far_density_matches_n0` — 0.969619 |x - 1| <= 0.05
- [PASS] `far_field_quasineutral` — 0.00191598 <= 0.02
- [PASS] `sheath_contained` — 0.00251852 <= 0.5
