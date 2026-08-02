# reference result — collector.biased_3v

Curated snapshot of a verified run+analysis. Read only for comparison;
its presence never makes a runner skip a run. The machine-readable
record is `metrics.json` + `verdict.json` here.

## Provenance

- **stage:** `collector.biased_3v`
- **verdict:** **PASS** (exit 0)
- **policy:** `collector.biased_3v.v1`  sha256 `fe1c00b426b49929…`
- **analysis id:** `20260801T094341Z_fe1c00b4`
- **git commit:** `291d45b465c30a01f666ca7599db1df948e671ba` (dirty=True)
- **WarpX:** 26.5  |  **Python:** 3.12.13

## Runs

- `20260801T083928Z_1a87cbce`  case_sha256 `1a87cbceda027f43…`

## Gates

- [PASS] `electron_current_vs_oml` — 0.852579 in [0.85, 1.05]
- [PASS] `far_density_matches_n0` — 0.969862 |x - 1| <= 0.05
- [PASS] `far_field_quasineutral` — 0.00212988 <= 0.02
- [PASS] `sheath_contained` — 0.00268392 <= 0.5
