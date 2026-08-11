# reference results — collector.floating

`20260806T162656Z_40e77ecd/` is the curated snapshot of the 2026-08-06 re-run
on the free GPU: **PASS on all 7 gates**, under the pre-registered
`collector.floating.v1` policy (no calibration run was needed).  Produced on
the **CUDA/GPU build** (RTX 3060, 100k steps, 6 µs, ~36 min); it retires and
replaces the earlier `20260801T230529Z_40e77ecd/` snapshot.

Headline numbers: the capstone's charge-pump mechanism drove the passive
sphere to **φ_f = −0.251 V**, inside the two-model theory bracket
(thermal-ion −0.360 V, OML-ion −0.213 V) and leaning OML as expected for
a/λ_De = 0.38; equilibrium current balance **0.9 %** (I_e 16.16 nA vs
I_i 16.01 nA); Gauss-law C = 89.1 fF = **1.068** × 4πε₀a (the grounded-box
correction); ledger-vs-dump charge consistency **3·10⁻⁹**.

The machine-readable record is `metrics.json` + `verdict.json` in the
snapshot; `REFERENCE.md` there carries the full provenance. A reference
result is read only for comparison; its presence never makes `simulation.py`
skip a run.
