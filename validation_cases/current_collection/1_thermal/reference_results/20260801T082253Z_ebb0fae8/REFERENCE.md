# reference result — collector.thermal

Curated snapshot of a verified run+analysis. Read only for comparison;
its presence never makes a runner skip a run. The machine-readable
record is `metrics.json` + `verdict.json` here.

## Provenance

- **stage:** `collector.thermal`
- **verdict:** **PASS** (exit 0)
- **policy:** `collector.thermal.v1`  sha256 `f38a61c0837b18a3…`
- **analysis id:** `20260801T083910Z_f38a61c0`
- **git commit:** `99de947101df5495466b4aff771456e87f60a925` (dirty=True)
- **WarpX:** 26.5  |  **Python:** 3.12.13

## Runs

- `20260801T082253Z_ebb0fae8`  case_sha256 `ebb0fae8b8d0617f…`

## Gates

- [PASS] `electron_current_matches_thermal` — 0.992142 |x - 1| <= 0.05
- [PASS] `ion_current_matches_thermal` — 1.00955 |x - 1| <= 0.1
- [PASS] `species_ratio_matches_theory` — 0.982754 |x - 1| <= 0.08
- [PASS] `far_density_matches_n0` — 0.996999 |x - 1| <= 0.05
- [PASS] `far_field_quasineutral` — 0.00506265 <= 0.02
- [PASS] `no_spurious_edge_sheath` — 0.00215704 <= 0.2
