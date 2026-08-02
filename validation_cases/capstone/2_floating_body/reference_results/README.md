# reference results — capstone.floating_body

`20260801T142601Z_2f822a95/` is the curated snapshot of the **float200 parity
run** of the migrated deck: full baseline (159 160 steps, 800 ns, 200×440,
~3 M macroparticles), completed in **6.34 h on the CPU build** (14 OpenMP
threads), **PASS on all 8 gates** (judged under policy
`capstone.floating_body.v2`, which added the beam-escape ledger-vs-dump
cross-check — the dominant charge-pump channel — to the v1 set):

| quantity | float200 anchor | this run |
|---|---|---|
| escape fraction | ~98.5 % | 98.44 % |
| F_beam | ~13.6 nN | 13.65 nN |
| φ_body | ~+16 V | +16.98 V |
| exhaust KE (reported) | ~146 eV | 147.5 eV (ledger closes to 0.6 eV) |
| current balance | ≤ 5 % | 3.2 % |
| edge \|φ\| | ≤ 1 V | 38 mV |
| ledger-vs-dump (ambient-e) | ≤ 2 % | 2.7e-9 |
| ledger-vs-dump (beam escape) | ≤ 2 % | 4.9e-9 |

The machine-readable record is `metrics.json` + `verdict.json`; `REFERENCE.md`
carries the full provenance (run id, case hash, policy id/hash, git commit,
WarpX version). A reference result is read only for comparison; it never makes
`simulation.py` skip a run. Scientific caveats (finite-time equilibrium on the
ion clock, single grid/PPC/seed, reduced ion mass) are documented in the stage
README and `../VALIDATION_GAPS.md`.
