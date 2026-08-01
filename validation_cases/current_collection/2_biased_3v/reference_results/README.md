# reference results — collector.biased_3v

`20260801T083928Z_1a87cbce/` is the curated snapshot of the first verified run
of the migrated stage: **PASS on all 4 gates** — I_e/I_OML = 0.8526 (the
pre-refactor GPU baseline measured 0.852: agreement to 0.07 %), far density
3 % low, quasineutral, sheath contained. Produced on the **CPU build**
(10 OpenMP threads, ~65 min); the GPU baseline numbers live in
`../../../_baseline_phase0/current_collection/2_biased_3v/results/`.

The machine-readable record is `metrics.json` + `verdict.json` in the
snapshot; `REFERENCE.md` there carries the full provenance. A reference result
is read only for comparison; it never makes `simulation.py` skip a run.
