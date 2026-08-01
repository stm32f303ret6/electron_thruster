# reference results — collector.thermal

`20260801T082253Z_ebb0fae8/` is the curated snapshot of the first verified run
of the migrated stage: **PASS on all 6 gates** (electron current within 0.8 %
of the exact thermal-flux law, ion 1.0 %, species ratio 1.7 %, far density
0.3 %, quasineutral, no edge sheath). Produced on the **CPU build**
(10 OpenMP threads, ~16 min); the pre-refactor GPU baseline numbers live in
`../../../_baseline_phase0/current_collection/1_thermal/results/`.

The machine-readable record is `metrics.json` + `verdict.json` in the
snapshot; `REFERENCE.md` there carries the full provenance (run id, case hash,
policy id/hash, git commit, WarpX version). A reference result is read only
for comparison; its presence never makes `simulation.py` skip a run.
