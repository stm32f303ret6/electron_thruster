# Phase 0 baseline freeze

This folder is a **temporary, read-only snapshot** of the validation results as
they stood immediately before the architecture refactor (see
`../ARCHITECTURE_REFACTOR_PLAN.md`, Phase 0). It exists so the migration can be
checked for *numerical parity* against the pre-refactor numbers, and is expected
to be deleted once Milestone A parity has been confirmed.

## Provenance

- **Git commit:** `444ecb8ee581c1a6016f177b5cd9c253ad92604e`
- **Commit date:** 2026-07-31 17:50:03 -0300
- **Snapshot taken:** 2026-08-01 (Phase 0 of the refactor)

## What is captured here

The committed, small provenance artifacts of the pre-refactor runs, copied
verbatim with their original relative paths:

- `*/results/summary_*.json` — machine-readable per-case/scenario summaries
  (the authoritative baseline numbers to reproduce).
- `*/results/*.csv` — collected-current and energy-spectrum tables.
- `*/results/*.png` — baseline figures (potential, density, current, sheath,
  transmission).
- `*/outputs/**/config_used.yaml` — the exact physics config each baseline run
  used (the pre-refactor "finished-run marker" file).

## Raw artifacts that are NOT available

The heavy raw simulation output was never committed (it is git-ignored — see the
old `validation_cases/.gitignore`, which excluded `outputs/**/*.h5`,
`outputs/**/*.bp`, and `reducedfiles/`). Therefore:

- **No openPMD field/particle/scrape `*.h5` files** survive for any case. Only
  the `paraview.pmd` index stubs were tracked. Re-deriving any metric not
  already in `summary_*.json` / the CSVs requires **re-running** the case.
- **No reduced-diagnostic `reducedfiles/*.txt`** survive (particle number /
  energy heartbeats), so the particle-budget closure numbers can only be read
  from the committed `summary_*.json`, not recomputed.

## How to use it

The migrated stages must reproduce these baseline numbers within
numerical/reporting precision **before** any Phase 5 scientific correction is
made (Milestone A, item 9). Compare:

- `electron_gun/1_negative_cathode/results/summary_negative_cathode.json`
- `electron_gun/2_electron_gun/results/summary_electron_gun.json`
- `current_collection/{1_thermal,2_biased_3v,3_biased_10v}/results/summary_*.json`

against the corresponding `metrics.json` / `verdict.json` produced by the
migrated `analyze.py` on a fresh run of the same config.
