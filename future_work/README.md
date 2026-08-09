# Future work — controller optimization and geometry-specific studies

This folder holds engineering work deliberately **excluded from the
concept-feasibility argument** (see
[`CONCEPT_FEASIBILITY_SCOPE.md`](../CONCEPT_FEASIBILITY_SCOPE.md)). The main
contribution claims only that the thruster mechanism is physically and
energetically plausible; everything here is about *optimizing* it for a
selected cathode, geometry, and mission.

## The simple power law used for the concept paper

The concept paper uses the ideal law only:

```
F [nN] = c_F · I [mA] · sqrt(kappa · V [V])
P [mW] = F · sqrt(V) / c_eff              c_eff = c_F · sqrt(kappa) = 2.934
```

Validated to 4–6 % against the three PIC frontier anchors (100/200/300 V).
See [`model/feasibility_model.py`](../model/feasibility_model.py) and
[`model/MODEL.md`](../model/MODEL.md).

The measured overhead factor (P_real / P_ideal ≈ 1.45) accounts for the
float tax, the 0.81 energy fraction, and sub-unity escape — all measured,
none optimized here.

## The U-curve throttle measurements

The fixed-thrust throttle slice ([`UCURVE_PLAN.md`](../pic_sims/validation_cases/capstone/UCURVE_PLAN.md))
measured power at a fixed 13.65 nN demand across four voltages. The PIC
simulation stages remain under `pic_sims/validation_cases/capstone/`
(stages 5–7) as geometry-specific supporting evidence.

| V | escape | delivered F (nN) | P/F (mW/nN) |
|---:|---:|---:|---:|
| 78 V | 57.4 % | 10.38 (−24 %) | 6.31 |
| 92.4 V | 79.9 % | 11.59 (−15 %) | 4.79 |
| 125 V | 93.8 % | 13.09 (−4 %) | 4.43 (valley) |
| 200 V (anchor) | 98.4 % | 13.65 | 5.01 |

The decisive observation: below ~100 V, escape collapses due to beam
self-scrape inside the capstone can geometry. The simple power model
correctly predicts operating points in the high-escape regime (≥ 96 %)
and diverges where escape collapses — that divergence IS the
geometry-specific loss that belongs here, not in the concept paper.

The same 92.4 V command transmitted 99.99 % in the clean isolated-gun
geometry, confirming the loss is attributable to the can/gap/lid, not to
a universal electron-gun limit.

## Deferred items

- **Adaptive controller design** —
  [`UCURVE_CONTROL_REVIEW.md`](UCURVE_CONTROL_REVIEW.md): escaped-current
  estimation from the return-current/charge balance, closed thrust loop,
  extremum-seeking power minimization, and hard guards.
- **U-curve targeting script** —
  [`ucurve_targeting.py`](ucurve_targeting.py): commanded currents for the
  fixed-thrust throttle stages, solving the calibrated laws at fixed demand.
- **The U-curve as a control surface** — a tax-aware servo needs the
  escape-vs-perveance surface those three points bracket
  ([`MODEL.md` §3](../model/MODEL.md)).
- **Magnetized axis** —
  [`MAGNETIZED_PLAN.md`](../pic_sims/validation_cases/capstone/MAGNETIZED_PLAN.md):
  every committed run is electrostatic (B = 0); near-field survival and
  far-field current closure in the geomagnetic field are open.
- **Cathode selection** — Spindt / field-emitter arrays: emitting area, gate
  power, collimation (single-gate angular spread is appreciable; double-gate
  collimation is only demonstrated at 20 keV), and downstream space-charge
  limits in ambient plasma.
