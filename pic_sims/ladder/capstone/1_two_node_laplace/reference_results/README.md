# reference results — capstone.two_node_laplace

`20260806T142600Z_f44044c6/` is the curated snapshot of the 2026-08-06 re-run
on the free GPU: **PASS on all 5 gates** (cathode
surface potential exact, body 0.22 V cut-cell interpolation, maximum
principle exact, independent stair-step solver within 1.86 V at ≥ 20 cells,
per-step `set_potential_on_eb` rewrite bit-exactly idempotent). Produced on
the **CUDA/GPU build** in seconds — five Laplace solves, no particles; it
retires and replaces the earlier `20260801T225643Z_f44044c6/` snapshot
(bit-identical, being a deterministic vacuum solve).

Judged under policy `capstone.two_node_laplace.v2`. The first-ever run
(`20260801T225210Z_f44044c6`) was a disclosed **calibration run** under v1
(see the stage README's calibration disclosure): it exposed two analysis
methodology errors (comparison distance inside the cathode-edge stair-step
skin; drift metric capturing first-solve convergence), which v2 fixed without
loosening any tolerance. This snapshot is a FRESH run judged under v2.

The machine-readable record is `metrics.json` + `verdict.json` in the
snapshot; `REFERENCE.md` there carries the full provenance. A reference
result is read only for comparison; its presence never makes `simulation.py`
skip a run.
