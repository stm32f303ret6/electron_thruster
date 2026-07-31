# 3_biased_10v: sphere at +10 V (chi = eV/kTe = 88.0)

Strong-bias rung: the sheath-growth demonstration.

    I_OML = I_th * (1 + chi) = 0.10393 uA * 88.993 = 9.249 uA

Two things to demonstrate, one to compare:

1. **Sheath growth** -- `results/sheath_3_biased_10v.png` shows the midplane
   |phi|(r) profile expanding in time and the sheath radius (|phi| = kTe/e
   surface) settling several lambda_De out, well beyond the +3 V case's.
   The sheath forms on the ELECTRON clock (electrons pile in fast); the ion
   density cavity around it deepens on the slower ion clock.
2. **Barrier deepening** -- the collected fraction of the OML ceiling drops
   with chi even at fixed a/lambda_De (the contactor study saw 38% -> 16%
   from 10 V -> 100 V on a fat probe; at our 0.382 the effect is a few
   percent).  Expect I_e/I_OML slightly BELOW the +3 V case's ratio: the
   gate floor is 0.80 vs 0.85 for exactly this reason.
3. **Containment** -- this case is the deliberate stressor of the
   edge-|phi| gate: the domain is 11 lambda_De so the 10 V perturbation
   dies out before the grounded walls.  A clipped sheath fakes extra
   collected current, so if the edge gate FAILS, the current gate cannot
   be trusted (enlarge the domain and rerun).

## Layout

```
3_biased_10v/
├── inputs/3_biased_10v.yaml   # ALL parameters (no CLI arguments anywhere)
├── run_3_biased_10v.py        # thin wrapper -> ../cc_common.py -> outputs/diags/
├── analyze_3_biased_10v.py    # gates + plots -> results/   (exit 0 = PASS)
├── animate_3_biased_10v.py    # phi + n_e video -> results/
└── results/
```

## Gates

| gate | reference | window |
|---|---|---|
| I_e / I_OML | 9.249 uA ceiling | [0.80, 1.05] |
| far-field n_e | n0 | 6% |
| quasineutrality | far shell | 2% of n0 |
| edge max-phi | sheath contained | 0.5 V |

## Measured (2026-07-31, RTX 3060, 82.5 min) -- ALL 4 GATES PASS

| quantity | measured | reference | ratio |
|---|---|---|---|
| I_e | 7.479 +- 0.047 uA | I_OML = 9.2487 uA | **0.8087** |
| far n_e/n0 | 0.9554 | 1 | -- |
| quasineutrality | 0.0050 | 0 | -- |
| sheath radius | 6.88 mm = **3.50 lambda_De** | +3 V case: 2.10 | grew |
| edge max-phi | 0.003 V | < 0.5 V | contained |

The three demonstrations landed: (1) **sheath growth** 2.10 -> 3.50
lambda_De from +3 V to +10 V (and the sheath_*.png time history shows it
forming); (2) **barrier deepening** -- the fraction of the OML ceiling
falls monotonically 0.992 (0 V) -> 0.852 (+3 V) -> 0.809 (+10 V), the
signature the electron_contactor OML study predicts; (3) **containment**
-- edge |phi| = 3 mV in an 11 lambda_De domain, so the current gates are
trustworthy.  The far-field density dip (4.5%) again matches the
collected/boundary-influx ratio of the flux-only reservoir.
