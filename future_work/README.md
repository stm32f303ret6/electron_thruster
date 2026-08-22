# Future work — controller optimization and geometry-specific studies

This folder holds engineering work deliberately **excluded from the
concept-feasibility argument** (scope decision below). The main
contribution claims only that the thruster mechanism is physically and
energetically plausible; everything here is about *optimizing* it for a
selected cathode, geometry, and mission.

## The scope decision (2026-08-09)

The concept paper presents the throttle as a **theoretical principle, not a
validated flight controller**: use the largest feasible *useful* (escaped)
current, then apply only enough acceleration voltage to reach the thrust
target — `F = K·I_esc·√(V−φ)`, `P_ideal = V·I` as the ideal beam-supply
power (never "spacecraft power": gate power, converter losses, control
electronics, and intercepted current are future engineering). "Feasible
current" is bounded by the emitter, ambient return-current availability,
acceptable spacecraft potential, and beam escape — acknowledged, not
modeled. Demoted from the main narrative accordingly: the 125 V universal
optimum, V ≈ 3.1φ as a global controller, the adaptive-controller design,
and geometry-specific escape-vs-perveance fits. The U-curve stays as
geometry-specific supporting evidence only (below). The full decision memo
(`CONCEPT_FEASIBILITY_SCOPE.md`) is preserved in git history.

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

The theoretical lower bound plus its measured 4–7 % closure in the
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

- **Optimization levers ledger** —
  [`OPTIMIZATION_LEVERS.md`](OPTIMIZATION_LEVERS.md): every lever from the
  measured 1.19–1.22× gap to the ideal bound plus the envelope levers,
  each with mechanism, measured tax, maximum recovery, campaign cost, and
  measurability against the ±4–7 % grid band. Priority: emission ceiling
  first (moves mission verdicts), ideal-constant recovery second.

- **Adaptive controller design** — distilled below ("The adaptive
  controller"); the full control review (2026-08-08,
  `UCURVE_CONTROL_REVIEW.md`) is preserved in git history.
- **U-curve targeting script** —
  [`ucurve_targeting.py`](ucurve_targeting.py): commanded currents for the
  fixed-thrust throttle stages, solving the calibrated laws at fixed demand.
- **The U-curve as a control surface** — a tax-aware servo needs the
  escape-vs-perveance surface those three points bracket
  ([`MODEL.md` §3](../model/MODEL.md)).
- **Magnetized axis** — tier M1 (field-aligned Bz, executed 2026-08-10)
  closed the near-field half — null at 1× LEO, an ~11 % thrust tax through
  the float at 10× (`../pic_sims/characterization/magnetized_1x/`,
  `magnetized_10x/`). Far-field current closure under transverse B (tier
  M2, the flight geometry) remains open;
  [`M2_TRANSVERSE_B.md`](M2_TRANSVERSE_B.md) holds its design.
- **Cathode selection** — Spindt / field-emitter arrays: emitting area, gate
  power, collimation (single-gate angular spread is appreciable; double-gate
  collimation is only demonstrated at 20 keV), and downstream space-charge
  limits in ambient plasma.

## The adaptive controller (distilled from the 2026-08-08 control review)

The capstone U-curve is an open-loop sweep of one geometry at one plasma
condition — not a global control law. The portable principle it supports:

> At each thrust command, estimate escaped axial current from the
> return-current and spacecraft-charge balance, regulate the minimum
> acceleration voltage that closes the thrust error, and increase emission
> only while measured total bus power falls, subject to floating-potential,
> transport, emitter, thermal, and voltage guards.

- **Control on escaped current, not emitted.** The decisive measurement:
  from 92.4 V to 78 V the emitted current rose ~40 % while escaped current
  stayed ≈ 0.48 mA — the extra emission self-scraped inside the can.
  Estimate `I_esc = I_col,net + C·dφ/dt` (a settled point drops the
  capacitive term). φ alone does not give current magnitude, so a flight
  implementation needs an instrumented collector or another net-current
  observer.
- **Thrust loop.** `F = 3.372 · I_esc · √(κ(V − φ)) · η_θ`; regulate V to
  the thrust command; a slower orbit-error loop absorbs residual κ/η_θ
  error.
- **Extremum-seeking current search.** Perturb the emission reference and
  increase useful current only while measured total bus power falls — this
  learns the local U-valley without a geometry-specific lookup table.
  Acquire from the high-voltage side: overshoot is cheap (the valley is
  shallow rightward, +13 % power at 200 V), undershoot hits escape
  collapse.
- **Hard guards.** Benign-float limit; collapse of dI_esc/dI_emit;
  emitter/gate/thermal/converter limits; voltage ceiling; unsettled φ̇ or
  current balance; unreachable thrust target → an explicit infeasible
  state and duty-cycling, never more current.
- The untaxed closed form `V_opt = ((2α+1)/α)·φ ≈ 3.1φ` is a hard **lower
  bound** only — the measured valley sits at V/φ ≈ 5.9
  (`UCURVE_PLAN.md` amendment).
- A field-emitter array improves the plant (emitting area, no heater, fast
  electronic current control, separable extraction/acceleration/
  collimation) but does not remove the collection/charging trade, and
  single-gate arrays carry appreciable angular spread — double-gate
  collimation is demonstrated only at 20 keV (Tsujino et al., Nat.
  Commun.).

## Open items (distilled 2026-08-21)

From the external optimistic-hypotheses review (2026-08-07;
`OPTIMISTIC_HYPOTHESES.md`, preserved in git history) and the thin-plasma
plan amendment — what remains open after the M1, thin-plasma, and 350 V
campaigns:

1. **`edge_phi_max` is in the wrong units** (a real defect, not an
   upside): the containment gate allows 1.0 V at the injection boundary,
   which is eφ/kTe ≈ 8.8 at kTe = 113.6 meV. Re-express it in kTe (the
   physically meaningful bound is of order 0.01 V). Fixing it moves
   results in the device's favor.
2. **Domain truncation under-collects.** The OML capture radius at the
   200 V anchor (~61 mm) exceeds rmax = 30 mm, so ambient plasma is
   injected as an undisturbed Maxwellian *inside* the device's own capture
   fan: simulated φ is an over-estimate and the committed thrust a floor.
   One run at rmax ≈ 60 mm (~2× cells) bounds it; expect φ down, F up.
3. **Long capstone with real O⁺** (gap G8): coarse grid, ≥ 20 µs. If φ,
   escape, and F land inside the existing gate tolerances, the most-cited
   caveat in the repo — 800 ns is a snapshot on the ion clock — becomes a
   measured band.
4. **The orbit-config mass is unphysical.** `mass_kg: 0.1` on the
   Ø10 × 5 mm cylinder is ~255 g/cm³ (11× osmium). No committed drag row
   changes (drag force is mass-independent), but a physical mass should be
   chosen, ΔV-authority statements re-derived, and the ~100× drop in
   attitude inertia disclosed — it makes the unaddressed attitude-control
   problem harder, not easier.
5. **Full-return null fixture.** A configuration where every beam electron
   returns to the craft, so the measured thrust must read ~0 — the
   falsification test of the momentum diagnostic itself, turning the
   momentum-cancellation objection (README FAQ) into a figure.
