# reference results — collector.biased_3v

`20260806T142605Z_1a87cbce/` is the curated snapshot of the 2026-08-06 re-run
on the free GPU: **PASS on all 4 gates** — I_e/I_OML = 0.8522 (the
pre-refactor GPU baseline measured 0.852: agreement to 0.03 %), far density
3 % low, quasineutral, sheath contained. Produced on the **CUDA/GPU build**
(RTX 3060, ~38 min); it retires and replaces the earlier
`20260801T083928Z_1a87cbce/` snapshot, and the original GPU baseline numbers
live in `../../../_baseline_phase0/current_collection/2_biased_3v/results/`.

The machine-readable record is `metrics.json` + `verdict.json` in the
snapshot; `REFERENCE.md` there carries the full provenance. A reference result
is read only for comparison; it never makes `simulation.py` skip a run.
