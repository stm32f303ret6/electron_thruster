# 2_biased_3v: sphere at +3 V (chi = eV/kTe = 26.4)

First biased rung.  For a sub-Debye attracting sphere the Orbit-Motion-
Limited (OML) result bounds the electron current:

    I_OML = I_th * (1 + chi) = 0.10393 uA * 27.398 = 2.847 uA

OML is a CEILING, exact only as a/lambda_De -> 0.  At this case's
a/lambda_De = 0.382 the electron_contactor OML study measured 93% of the
ceiling, so the gate accepts [0.85, 1.05] -- above 1.05 would mean an
injection bug, well below 0.85 a resolution/containment problem.

Ions are Boltzmann-repelled by exp(-eV/kTi) ~ 7e-17: effectively zero.
The measured ion trickle is the ion-clock start-up bias (ions already in
the domain at t = 0 never climbed the barrier) -- reported, not gated.

## Layout

```
2_biased_3v/
├── inputs/2_biased_3v.yaml   # ALL parameters (no CLI arguments anywhere)
├── run_2_biased_3v.py        # thin wrapper -> ../cc_common.py -> outputs/diags/
├── analyze_2_biased_3v.py    # gates + plots -> results/   (exit 0 = PASS)
├── animate_2_biased_3v.py    # phi + n_e video -> results/
└── results/
```

## Gates

| gate | reference | window |
|---|---|---|
| I_e / I_OML | 2.847 uA ceiling | [0.85, 1.05] |
| far-field n_e | n0 | 5% |
| quasineutrality | far shell | 2% of n0 |
| edge max-phi | sheath contained | 0.5 V |

Compare `results/sheath_2_biased_3v.png` with the 10 V case: the |phi| =
kTe/e surface should sit at ~2-3 lambda_De here and further out at +10 V.

## Measured (2026-07-31, RTX 3060, 36.5 min) -- ALL 4 GATES PASS

| quantity | measured | reference | ratio |
|---|---|---|---|
| I_e | 2.4260 +- 0.0079 uA | I_OML = 2.8474 uA | **0.8520** |
| far n_e/n0 | 0.9705 | 1 | -- |
| quasineutrality | 0.0027 | 0 | -- |
| sheath radius | 4.13 mm = **2.10 lambda_De** | -- | -- |
| edge max-phi | 0.003 V | < 0.5 V | contained |

Why 85% and not the contactor study's 93%: (1) the far-field density sits
3% below n0 -- the flux-only reservoir does not recycle the 2.4 uA the
sphere eats, and the dip matches the collected/boundary-influx ratio;
normalizing by the ACTUAL ambient density gives I_e/I_OML(n_local) ~ 0.88.
(2) EB faceting takes ~1-2%.  (3) The remainder is genuine barrier
deepening at a/lambda_De = 0.38, which must GROW with chi -- see the
+10 V case.  All three effects push DOWN, none can push above the
ceiling, and the ceiling holds.
