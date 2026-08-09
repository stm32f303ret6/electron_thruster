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

The measured overhead factor against the ideal bound (P_real / P_ideal ≈
1.4–1.5 at the off-design points) decomposes into exactly two things,
neither of which belongs in the concept argument:

1. **non-optimized voltage** — the fixed-thrust slice held the demand at
   voltages away from the minimum-power operating point, so part of the
   excess is simply operating off the optimum the ideal law would pick;
2. **real inefficiencies** — beam interception / self-scrape inside the
   can (plume divergence against the aperture), the 0.81 energy fraction,
   the float tax, and emission-type overheads (gate power etc.) — all
   geometry- and cathode-specific.

The theoretical lower bound plus its measured 4–6 % closure in the
high-escape regime is therefore sufficient for the concept paper. The
attribution is already confirmed at one demand inside the committed data:
the model's minimum feasible voltage for the anchor's own 13.65 nN demand
is 196 V — the 200 V anchor *is* effectively that run — and there the
bound closes to 4 % with 98.4 % escape, while every 1.5–2× point
commanded 2.7–10× over the emission ceiling (voltages the throttle
principle would never select). A cheap targeted PIC run at the
model-selected optimum for a *different* demand (predicted: escape ≥ 96 %,
power within ~6 % of the bound) would generalize the confirmation — a good
first item when this folder's work resumes.

## The U-curve throttle measurements

The fixed-thrust throttle slice ([`UCURVE_PLAN.md`](UCURVE_PLAN.md))
measured power at a fixed 13.65 nN demand across four voltages. The PIC
simulation stages live here under
[`ucurve_pic_stages/`](ucurve_pic_stages/) (formerly capstone stages 5–7)
as geometry-specific supporting evidence, with their reference results and
pre-registration intact.

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
