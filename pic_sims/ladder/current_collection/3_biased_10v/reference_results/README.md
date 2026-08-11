# reference results — collector.biased_10v

`20260806T150359Z_503c1220/` is the curated snapshot of the 2026-08-06 re-run
on the free GPU: **PASS on all 4 gates** — I_e/I_OML = 0.8088 (the
pre-refactor GPU baseline measured 0.809), far density 4.6 % low, quasineutral,
and THE gate to watch here — the thick +10 V sheath contained (edge |φ| =
2.6 mV). Produced on the **CUDA/GPU build** (RTX 3060, ~83 min); it retires and
replaces the earlier `20260801T094632Z_503c1220/` snapshot. GPU baseline
numbers live in git history (pre-refactor tree at commit `444ecb8`; the Phase-0
`_baseline_phase0/` snapshot was retired after Milestone A verified
reproduction).

The machine-readable record is `metrics.json` + `verdict.json` in the
snapshot; `REFERENCE.md` there carries the full provenance. A reference result
is read only for comparison; it never makes `simulation.py` skip a run.
