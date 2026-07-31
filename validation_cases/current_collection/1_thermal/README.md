# 1_thermal: sphere at plasma potential (0 V)

The one probe problem with an exact, assumption-free answer.  At plasma
potential the sphere creates no field, so every orbit is a straight line and
each species arrives at its one-sided thermal flux:

    I_th = n0 * e * <v>/4 * 4*pi*a^2        <v> = sqrt(8kT/(pi*m))

    I_th_e = 0.10393 uA      I_th_i = 4.379 nA      I_e/I_i = 23.738

This is exact for ANY convex probe size -- the a/lambda_De << 1 requirement
belongs to OML (biased probes) only.  The species ratio
sqrt((mi/me)*(Te/Ti)) is area- and density-independent, so it cross-checks
both species' injection machinery at once.

What a PASS validates (beyond the code): the chipsat capstone's plasma row,
cell size (0.15 mm = 13.1 cells/lambda_De), ppc = 16, and the flux-reservoir
recipe -- this case is the cheapest place to catch a configuration error
before the multi-hour chipsat run.

## Layout

```
1_thermal/
├── inputs/1_thermal.yaml    # ALL parameters (no CLI arguments anywhere)
├── run_1_thermal.py         # thin wrapper -> ../cc_common.py -> outputs/diags/
├── analyze_1_thermal.py     # gates + plots -> results/   (exit 0 = PASS)
├── animate_1_thermal.py     # phi + n_e video -> results/
└── results/                 # current/fields/sheath PNGs, summary JSON, CSV
```

## Gates

| gate | reference | tolerance |
|---|---|---|
| I_e | 0.10393 uA exact | 5% (shot ~2%, EB facet ~1-2% low) |
| I_i | 4.379 nA exact | 10% (24x noisier, ion-clock slow) |
| I_e/I_i | 23.738 | 8% |
| far-field n_e | n0 | 5% |
| quasineutrality | n_e = n_i far shell | 2% of n0 |
| edge max-phi | ~0 V everywhere | 0.2 V |

Expected small deviations, both understood: electrons read ~1-2% LOW (EB
faceting at 5 cells/radius); ions read LOW until the ion transit clock
(~2 us) fills the domain steady state -- the 3 us run + last-40% window
leaves margin, but the ion gate stays at 10% for exactly this reason.

## Measured (2026-07-31, RTX 3060, 15.6 min) -- ALL 6 GATES PASS

| quantity | measured | theory | ratio |
|---|---|---|---|
| I_e | 0.10311 +- 0.00104 uA | 0.10393 uA | **0.9921** |
| I_i | 4.420 +- 0.140 nA | 4.378 nA | **1.0096** |
| I_e/I_i | 23.328 | 23.738 | 0.983 |
| far n_e/n0 | 0.9970 | 1 | -- |
| quasineutrality | 0.0051 | 0 | -- |
| edge max-phi | 0.002 V | ~0 | -- |

The 0.8% electron deficit is the expected EB-faceting systematic at 5
cells/radius (staircased sphere area < 4*pi*a^2).  This run validates the
chipsat plasma row, dx = 0.15 mm, ppc = 16 and the flux reservoir at the
sub-percent level.
