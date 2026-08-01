# reference results — collector.thermal

**None committed yet.** This stage's simulation is GPU-only (~25-50 min on an RTX
3060; the ambient-plasma particle counts make CPU infeasible), so no verified
run+analysis has been produced in the current refactor.

To create the reference result once a GPU is available:

```bash
conda activate warpx-cpu-mpich-dev
python simulation.py
python analyze.py --run outputs/<run-id> --policy acceptance.yaml   # must PASS
```

then copy that analysis's `metrics.json`, `verdict.json`,
`acceptance_used.yaml`, the run `manifest.json`, and the key figures/CSV here,
alongside a `REFERENCE.md` recording the run id, case hash, policy id/hash, git
commit, and WarpX version (see the emitter stages' reference_results for the
exact shape).

Until then, compare against the **committed baseline** numbers in
`../../_baseline_phase0/current_collection/1_thermal/results/` — those were produced by
the pre-refactor code and the migrated deck reproduces the physics verbatim.
