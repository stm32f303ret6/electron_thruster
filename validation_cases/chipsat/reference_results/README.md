# reference results — capstone.floating_body

**None committed yet.** The full baseline run is GPU-scale (~159 k steps,
200×440 grid, ~3 M ambient macroparticles; order hours on an RTX 3060 with the
GPU build). The migrated deck has passed its unit tests and a reduced CPU
smoke of the full lifecycle, but no parity run of the float200 baseline has
been produced by THIS deck yet.

To create the reference result once the GPU build is available:

```bash
python simulation.py                                     # baseline config.yaml
python analyze.py --run outputs/<run-id> --policy acceptance.yaml   # must PASS
```

then copy that analysis's `metrics.json`, `verdict.json`,
`acceptance_used.yaml`, the run `manifest.json`, and the four figures here
with a `REFERENCE.md` recording run id, case hash, policy id/hash, git commit,
and WarpX version (see the emitter stages' reference_results for the shape).

Until then, the float200 anchors quoted in `README.md` come from the
electron_contactor lineage (`~/Desktop/repos/warpequisd/electron_contactor`,
its `results/` and `PAPER_DRAFT.md`), not from a run of this migrated deck.
