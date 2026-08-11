# OPTIMISTIC HYPOTHESES — the upside case, pre-registered

**Audience:** an AI agent picking up this repository.
**Author:** external reviewer, 2026-08-07. Not a repo maintainer.
**Status of everything below:** hypotheses and back-of-envelope algebra. Some
are exact identities on committed numbers; some are speculative and need
literature or new runs. Each is labelled. **None of this has been run through
the repo's own tooling.**

---

## 0. How to use this document

This repo is unusually good at finding its own weaknesses
(`VALIDATION_GAPS.md`, the `extrap_*` flags in `model/MODEL.md`, the honest
duty-cycle table). The consequence is a systematic bias: the caveats are
audited and the *upside* is not. Several of the repo's conservative choices
push the reported performance **down**, and one omitted physics regime
(magnetization) has never been examined at all.

This document collects the upside cases so they are as legible as the gaps.

### Hard rules for any agent acting on this

1. **Nothing here is a result.** Do not cite these numbers as measured.
   Status tags are `MEASURED` (committed in this repo), `DERIVED` (exact
   algebra on committed numbers), or `SPECULATIVE` (needs new evidence).
2. **Nothing here may enter an acceptance gate.** This obeys the same
   contract as `model/MODEL.md` §9: fitted constants and external reasoning
   stay home; PIC stages stay self-contained. A hypothesis becomes a gate
   only after a committed run measures it.
3. **Do not weaken an existing gate on the strength of an argument here.**
   Several hypotheses argue that current results are conservative. The
   correct response is a new run, not a loosened tolerance.
4. **If a hypothesis is falsified, record it.** The value of this document is
   that each item is falsifiable. A refuted hypothesis is a result.

---

## 1. Shared constants

All `MEASURED`, from committed configs and the three-anchor frontier in
`model/MODEL.md` §1.

| symbol | value | source |
|---|---|---|
| n₀ | 1.627×10¹² m⁻³ | `capstone/2_chipsat_thruster/config.yaml` |
| Te | 1318.8 K = **113.6 meV** | same |
| Ti | 936.2 K = **80.7 meV** | same |
| ion mass | 400 mₑ (reduced; ladder-wide caveat G10) | same |
| r_probe | 5.0 mm (can radius) | same |
| rmax | 30 mm (domain) | same |
| t_end | 800 ns | same |
| dx | 0.15 mm (13.1 cells/λ_De) | same |
| λ_De | ≈ 1.97 mm | derived from n₀, Te |

Voltage frontier anchors (all gates PASS):

| V | I (mA) | φ_body (V) | F_beam (nN) | KE (eV) |
|---|---|---|---|---|
| 100 | 0.121 | 5.40 | 3.42 | 77.2 |
| 200 | 0.342 | 16.98 | 13.65 | 147.5 |
| 300 | 0.630 | 36.30 | 30.13 | 210.1 |

Environment (external, not in repo):

| symbol | value | note |
|---|---|---|
| B (LEO, 400–600 km) | 2.2–5.5×10⁻⁵ T; **3×10⁻⁵ T** nominal | near-equatorial ≈ 2.5–3.2×10⁻⁵ T, near-horizontal, northward |
| v_orb | 7.67 km/s @ 400 km | |

---

## H1 — The magnetized regime is neutral at worst, and is the only place a large upside can live

**Status: DERIVED (the identity) + SPECULATIVE (the upside).**
**Priority: highest.**

### The gap being addressed

Every stage is electrostatic with **B = 0** (`model/MODEL.md:172`; `Bz` is
filed as a research variant outside the ladder). No stage can see
magnetization, because:

| scale | value | vs. capstone deck |
|---|---|---|
| beam gyroradius r_g (147.5 eV) | **1.37 m** | domain rmax is 30 mm = 1/45 r_g |
| beam gyroradius r_g (210.1 eV) | **1.63 m** | |
| gyroperiod T_c = 2πmₑ/(eB) | **1.19 µs** (energy-independent) | t_end is 800 ns = 0.67 T_c |

At the repo's chosen inclination (`inclination_deg: 0.5`, near-equatorial) B
is near-horizontal and northward while **v** is eastward, so the thrust axis
is **perpendicular to B for the entire mission**. This is the maximally
magnetized geometry, not an edge case.

### H1a — The exhaust convects away; it does not return to the craft

**DERIVED.** In the spacecraft frame the plasma streams past at v_orb. An
emitted electron's guiding centre is at rest in the *plasma* frame, so it
convects astern at

```
v_orb · T_c = 7670 m/s × 1.19 µs = 9.13 mm per gyroperiod
```

i.e. roughly one body-length (the can is 10 mm across) per turn of its own
gyration. After 10 gyroperiods it is 91 mm astern; after 1 ms, 7.7 m. The
geometric re-impact cross-section on a 10 mm body 1.4 m away, translating one
diameter per orbit, is negligible.

**Prediction:** beam recapture fraction in a magnetized run is ≪ 1 %.

### H1b — Beam reaction and Lorentz coupling are the *same number* at L = r_g (exact identity)

**DERIVED — this is algebra, not a coincidence.**

```
F_beam    = (I/e) · mₑ · v          (beam momentum flux — what the ladder measures)
r_g       = mₑ v / (e B)            (gyroradius)
⇒ I · r_g · B = I · mₑ v / e = F_beam        ∎
```

Therefore, for a current system of characteristic scale L:

```
F_Lorentz / F_beam  =  L / r_g          (exact, for any beam energy or current)
```

Checked against all three committed anchors. The few-percent shortfall is not
noise — it is **exactly** each anchor's own divergence loss c_F/c_F_ideal,
which is the strongest available confirmation that the residual is understood:

| anchor | F/(I·B) | r_g | ratio | per-anchor c_F/3.372 |
|---|---|---|---|---|
| 100 V | 0.942 m | 0.988 m | 0.954 | 3.216/3.372 = **0.954** |
| 200 V | 1.330 m | 1.365 m | 0.975 | — (fleet c_F 3.2675 → 0.969) |
| 300 V | 1.594 m | 1.629 m | 0.978 | 3.300/3.372 = **0.979** |

**Consequences, in order of importance:**

1. **No catastrophe.** The magnetized picture *reproduces* the electrostatic
   result when the current loop closes at one gyroradius. The committed
   13.65 nN is the L = r_g special case, not an artefact that magnetization
   destroys.
2. **The entire magnetized question collapses to one dimensionless number:
   L/r_g.** That is the quantity a magnetized run must measure.
3. **The upside is real but conditional.** If the field-aligned return
   current closes over L ≈ 10 m rather than 1.4 m, F ≈ 100 nN at the same
   0.342 mA — which would close 400 km axial (demand 32.9 nN mean,
   92.4 nN max) outright. Lorentz coupling pays no exhaust-energy cost, so
   the F/P penalty that `THESIS.md` concedes to tethers would soften by the
   same factor.

**Do not overclaim this.** The identity does *not* say the two mechanisms
add. It says they are two descriptions that agree at L = r_g. Whether L > r_g
depends on where the beam thermalises and where the return current closes —
genuinely open, and the reason to run it.

### Falsification / next run

A magnetized PIC run, B ⊥ thrust axis, **domain ≥ 2 m** (≥ 1.5 r_g),
**duration ≥ 5 T_c ≈ 6 µs**, measuring F_net on the body.

- If F_net/F_beam ∈ [0.9, 1.1] → L ≈ r_g. Electrostatic results stand
  unchanged. H1 resolves as "neutral," which is still a valuable result
  because it retires the largest unexamined risk.
- If F_net/F_beam > 1.1 → L > r_g. Upside confirmed; re-open the mission table.
- If F_net/F_beam < 0.5 → the concept needs a field-aligned firing constraint,
  and the 0.5° inclination choice inverts. **This is the outcome that must be
  found before a reviewer finds it.**

Cost note: a 2 m domain at 0.15 mm is not affordable. This run needs a
coarser grid and a different question — it is a momentum-coupling
measurement, not a sheath-resolution measurement. Resolve the gyro-orbit, not
λ_De.

---

## H2 — G8 (the 800 ns ion clock) is a much smaller problem than the gaps doc concedes

**Status: DERIVED. Priority: high (it is free — it costs a paragraph, not a run).**

`VALIDATION_GAPS.md` G8 concedes that 800 ns is a snapshot on the ion clock
(ion relaxation ≈ 2 µs with 400 mₑ ions; ≈ 15 µs with real O⁺). True. The
argument for why it largely does not matter is not made anywhere, and should be:

**The body floats positive, which evicts ions from the current balance.**

```
eφ/kTi = 16.98 V / 80.7 meV = 210          (200 V anchor)
eφ/kTi = 36.30 V / 80.7 meV = 450          (300 V anchor)
```

Ion collection is suppressed by exp(−210). Not small — zero to any precision
that exists. The floating equilibrium is therefore **electron emission versus
electron collection**, and both run on the electron clock:

```
ω_pe = 7.19×10⁷ rad/s  →  T_pe = 87.3 ns
t_end / T_pe = 800 / 87.3 = 9.2 full electron plasma periods
```

**Claim:** the quantities the capstone gates — φ_body, escape fraction,
F_beam, current balance — are converged on the clock that sets them. The
unconverged ion response is second-order sheath space charge.

**Residual honest caveat (keep it):** ions still set background quasi-
neutrality in the sheath, and their slow evacuation from a positively charged
body's sheath would deepen it somewhat over ~15 µs. Direction of that effect
is not established here.

**Falsification:** one long capstone run — real O⁺ mass, coarse grid,
≥ 20 µs. If φ_body, escape, and F_beam land inside the existing v2 gate
tolerances, G8 downgrades from "the tail is a snapshot" to "converged, with
the ion-sheath residual bounded at X %." That converts the most-cited caveat
in the repo into a closed gap for a cheap run.

---

## H3 — Three conservative choices all bias the reported performance *downward*

**Status: DERIVED. Priority: medium — these do not need runs to state, only to quantify.**

### H3a — Domain truncation under-collects, so the true float is *lower* than simulated

OML capture radius at the 200 V anchor:

```
χ = eφ/kTe = 16.98 / 0.1136 = 149.4
r_capture = r_p·√(1+χ) = 5 mm × 12.27 = 61.4 mm      vs.  rmax = 30 mm
```

Ambient plasma is injected as an undisturbed Maxwellian at 30 mm — inside the
device's own capture radius. This **under-estimates** collected current at a
given φ. Follow the chain through the current balance (I_collect(φ) = I_beam,
emission fixed):

| step | direction |
|---|---|
| simulated I_collect(φ) too low | → |
| simulated φ must rise higher to reach balance | **simulated φ > true φ** |
| KE = κ_KE·(V − φ), κ_KE = 0.8063 | true KE **higher** |
| F = c_F·I·√KE | true thrust **higher** |
| benign limit φ ≤ 50 V | true device clears it on **more** rows |

**Every arm moves in the device's favour.** 13.65 nN is a floor; the 40.9 %
`phi_over_benign` fraction at 400 km is an over-estimate.

**Related, and it must be fixed regardless:** the containment gate
`edge_phi_max ≤ 1.0 V` is expressed in volts, but kTe = 113.6 meV, so the gate
permits **eφ/kTe = 8.8** at the injection boundary. Re-express it in kTe. The
physically meaningful bound is ~0.01 V. *This is a real defect, not an upside
— it is listed here only because fixing it moves results the good way.*

**Next run:** double `rmax` to 60 mm. In RZ this is ~2× cells; the repo
already runs 120 000-cell variants at 8.7 GiB
(`SETUP.md`). Expect φ to fall and F to rise.

### H3b — The perveance guard is probably conservative

`I_max = 1.46 · I_CL` where `I_CL` is **planar** Child–Langmuir for a 0.5 mm
spot in a 4.7 mm gap. Gap-to-spot ratio is **9.4** — deep in the regime where
planar CL is a known severe under-estimate and convergent/spherical
(Langmuir–Blodgett) flow gives substantially more. The 1.46 was measured once
at 200 V and is held as a **hard guard** in the flight control law
(`model/MODEL.md` §2).

**Hypothesis:** the true non-planar ratio exceeds 1.46, so the emission
ceiling — and hence `F_cap`, hence the duty-cycle table — has unclaimed
headroom. **Falsify** by measuring the ratio at 100 V and 300 V; if it is
flat at 1.46, the hypothesis dies cleanly and the guard is confirmed
voltage-independent, which is itself worth having.

### H3c — The mesothermal correction lands on the species that barely matters

The body floats **positive**, so it collects **electrons**, and the electron
anisotropy from orbital motion is small:

```
v_orb / v_th,e  =  7.67 / 141.4  =  5.4 %      (rms, 1-D)
v_orb / v̄_e     =  7.67 / 225.7  =  3.4 %      (mean speed)
```

`THESIS.md` already states ~5 %. The hypersonic ion wake — the thing the
400 mₑ reduced mass genuinely does misrepresent (fake Mach 1.08 vs. real
Mach 9.3, see H6) — is a charging and drag concern for a *negatively*
floating body. This device is not one.

---

## H4 — The emitter is a component selection, not an open physics question

**Status: SPECULATIVE. Priority: medium-high (it blocks the power budget).**

`i_beam: 0.342e-3  # prescribed; no thermionic model`.

**Reframe:** prescribing the current is the *correct* abstraction, and it is
what makes the ladder portable. The emitter is a module; every ladder result
holds at that current regardless of how the electrons are freed. This is
separation of concerns, not an omission — but the module must still be named,
because the power budget depends entirely on it.

| emitter class | heater power | verdict |
|---|---|---|
| thermionic (bench: W5W bulb, 12 V / 5 W) | ~0.5–1 W radiative from a 2500 K spot | **disqualifying** — 10× the 68 mW supply, 30× the ~30 mW harvest |
| field emission (FEA / CNT) | none; gate power ≈ I·V_gate, mW | **the only candidate that closes the budget** |

0.342 mA is a modest current for a field-emission array. `lab_experiments/
electron_gun/README.md` already states thermionic is "a bench convenience,
not the flight concept" — this document's contribution is only that the
replacement must be named and costed, and that the physics results survive
the substitution untouched.

**Leads to verify (I have not confirmed these; treat as search terms, not
citations):** JAXA flew a Field Emission Cathode on the KITE electrodynamic-
tether experiment aboard HTV-6 (2017) for essentially this job — electron
emission from a LEO spacecraft. Electrodynamic-tether contactor literature is
the right body of work. **Open risk that must travel with any FEA choice:**
atomic-oxygen erosion of emitter tips at 400–600 km.

---

## H5 — Fixing the spacecraft mass upgrades the thesis and changes no result

**Status: DERIVED. Priority: high (one-line edit).**

`orbit_sims/.../config.yaml`: `mass_kg: 0.1` with r = h = 5 mm.

```
V = π r² h = 3.93×10⁻⁷ m³   →   ρ = 0.1 / 3.93×10⁻⁷ = 2.55×10⁵ kg/m³
```

**255 g/cm³ — 11.3× osmium.** Meanwhile `THESIS.md` says "gram-class."

**Nothing in the mission CSVs changes.** Drag force F = ½ρ_air v² C_d S is
mass-independent, so every drag row survives verbatim. What changes is the
capability story, and it changes upward:

| | m = 100 g | m = 1 g |
|---|---|---|
| acceleration at 13.65 nN | 1.37×10⁻⁷ m/s² | 1.37×10⁻⁵ m/s² |
| ΔV authority, 1 yr at full throttle | 4.3 m/s | **431 m/s** |

**State that honestly:** this is *available* ΔV authority at continuous full
throttle, not a mission ΔV. At 600 km the demand is only 2.0 nN mean (25 %
duty), so the realised figure is ~100 m/s/yr. Still a large number for a
propellantless system on ~8 mW mean.

**Action:** pick one mass, make all five root markdown files and the orbit
configs agree, and re-derive BC. Note that lowering the mass also cuts
attitude inertia ~100×, which makes the unaddressed attitude-control problem
*harder* — see "Known open items" below. Do not let this edit quietly hide
that trade.

---

## H6 — The narrow measured envelope is a coverage problem with one cheap fix

**Status: DERIVED. Priority: highest after H1 (best result-per-GPU-hour in the campaign).**

From `model/MODEL.md` §5:

| altitude | duty cycle needed | **in-envelope %** |
|---|---|---|
| 400 km axial | 140 % — does not close | 11.9 |
| 400 km lateral | 92 % — no margin | 33.4 |
| 500 km axial | 45 % | 29.1 |
| 550 km axial | 32 % | 8.0 |
| 600 km axial | 25 % — closes | **0.9** |

This reads as a physics failure. It is not. **Exactly one plasma row has ever
been measured** (n₀ = 1.627×10¹² m⁻³, the dayside `PLASMA_MAX` row, identical
across `collector.*` and the capstone). The `extrap_density` flag fires
outside 0.7–1.3× of it. 600 km is a lower-density regime, so essentially every
row that *closes* is flagged.

**Hypothesis:** one committed capstone run at a second, lower plasma density
opens the `extrap_density` axis — which `model/MODEL.md` §8 already identifies
as the collection law's **theory-only** axis — and moves 550/600 km from ~1–8 %
in-envelope to substantially covered, in a single run.

**Secondary benefit:** it independently tests the fitted collection exponent
α (currently 0.845–0.893, fit to a single density and, per H2's residual, to a
tail whose stationarity is bounded rather than demonstrated). α drives the
flight servo `V = ((2α+1)/α)·φ`. A second density is the only way to know
whether α is a law or a curve-fit.

**Mission framing worth adding:** 550–600 km is a defensible target
independent of this device's limits — long enough natural lifetime to be a
useful swarm altitude, short enough to stay debris-compliant. Drag
compensation there means holding formation and deferring re-entry
indefinitely on harvested sunlight.

---

## 7. What is genuinely strong, and should be defended rather than hedged

For an agent tempted to over-hedge the claims: these held up under adversarial
review.

- **The niche is real.** Nothing supplies 1–100 nN of controllable,
  continuous, propellantless thrust in a gram-class package. Electrosprays
  and FEEPs bottom out at 5–30 µN in kilogram-class systems — two to three
  orders above the demand, in packages heavier than the whole vehicle.
- **The dry-system-floor argument is the right argument**, and `THESIS.md`
  already catches that propellant *mass* is not the argument at nN scale.
  Do not regress to the mass framing.
- **η ≈ 0.73 is genuinely ion-thruster-class energy conversion.** State it
  alongside F/P ≈ 0.2 µN/W, never instead of it (existing guardrail — keep).
- **The momentum-cancellation objection was answered correctly**: measured at
  1 % (`f_net_over_f_beam` = 0.0098, gated ≤ 1), *and* bounded analytically at
  ≤ 41 % under the objection's own most hostile premise (√(36/210) per-electron
  momentum ratio). That is the right shape of answer.
- **The method itself is the repo's strongest asset**: pre-registered
  acceptance policies, hash-frozen configs, a one-way `orbit_sims → pic_sims`
  dependency so evidence cannot chase demand, and a gaps document that indicts
  its own capstone. This is why an external reviewer could produce an
  actionable punch list in an afternoon. Do not trade it for a nicer number.

---

## 8. Known open items these hypotheses do NOT address

Listed so no agent mistakes this document for a complete review.

- **Attitude control does not exist anywhere in the repo** — no actuator,
  sensor, mass, or power line item — yet `rotation: axial` (the config's own
  "single biggest lever") presupposes a held pose. Thrust exits a 2 mm lid
  hole; any CoM offset is a torque. H5 makes this *worse*, not better.
- **`edge_phi_max` is in the wrong units** (H3a). Real defect.
- **G3** (gun operating point: 4.7 mm enclosed gap vs. 1.9 mm planar; hotter
  launch temperature; ppc_beam 16 vs 128) remains open.
- **G4** (reservoir recycling ungated), **G6** (beam + ambient plasma coexist
  only at the capstone), **G10** (single grid/PPC/seed; reduced ion mass
  everywhere) remain open and are correctly documented.

---

## 9. Suggested order of work

| # | action | closes | cost |
|---|---|---|---|
| 1 | Magnetized run, B ⊥ thrust, ≥ 2 m domain, ≥ 5 T_c, coarse grid | H1 — largest unexamined risk *and* largest upside | new deck; moderate |
| 2 | Capstone at a second plasma density | H6 + independent test of α | one run |
| 3 | Long capstone, real O⁺, coarse grid, ≥ 20 µs | H2 / G8 | one run |
| 4 | `rmax` → 60 mm; re-express `edge_phi_max` in kTe | H3a + a real defect | one run + edit |
| 5 | Fix `mass_kg` across all files; re-derive BC | H5 | edit |
| 6 | Name and cost the flight cathode | H4 | desk study |

Items 4–6 are cheap and can proceed in parallel with 1–3.

**If only one thing gets done: item 1.** It is the only entry that can change
the answer by an order of magnitude in either direction, and it is the one a
reviewer will ask about first.

---

## MAINTAINER ANNOTATIONS — 2026-08-08 (not by the original reviewer)

Recorded when this document was committed, after the fixed-thrust throttle
campaign resolved. The reviewer's text above is unmodified; these annotations
correct or update specific items.

- **H1b's anchor table is circular, not confirmatory.** F/(I·B·r_g) with
  r_g built from the same KE is algebraically c_F/c_F_ideal — the same
  divergence loss computed twice. The identity itself stands and is
  restated (with this caveat) in
  `pic_sims/thruster_characterization/MAGNETIZED_PLAN.md`, which is now the
  actionable form of H1: tier M1
  (field-aligned, on the committed deck) is pre-registered; tier M2 (the
  transverse-B far-field run the reviewer asks for) is designed there.
- **H2 overstates convergence.** The committed late-slope data already
  measure a multi-volt ion-timescale drift (e.g. 300 V: 36.3 V tail →
  ~42–48 V settled extrapolation), so "φ is converged on the electron
  clock" is contradicted in-repo; the defensible form is "the current
  balance runs on the electron clock; the drift is the measured ion
  residual, quoted as a band." The long-O⁺ run suggestion remains the
  right instrument for G8.
- **H3b resolved in the hypothesized direction, with evidence.**
  `emitter.voltage_bracket` C (2026-08-07) transmitted 0.9999 at 133.5 %
  of the planar I_CL scale — the planar number is conservative for the gun
  geometry. In the capstone's own gap the throttle stages then measured
  where the real ceiling bites (escape 93.8/79.9/57.4 % at 2.7/5.6/10.1×
  the validated ceiling — `future_work/UCURVE_PLAN.md` amendment).
- **H6 misses that the second-density run already exists**, pre-registered
  and unexecuted: `pic_sims/thruster_characterization/thin_plasma/THIN_PLASMA_PLAN.md` (predictions for all four
  α candidates committed 2026-08-06). The envelope-coverage argument here
  is a new and independent reason to unchain it.
- **§8 staleness:** G3's voltage row closed 2026-08-07
  (`emitter.voltage_bracket`); its launch-temperature and ppc_beam rows
  remain open. The fixed-thrust throttle curve (this document predates it)
  is measured: valley at ~125 V, no-go wall at 78 V, servo constant demoted
  to a lower bound (`model/MODEL.md` §2).

## MAINTAINER ANNOTATIONS — 2026-08-10

- **H1's near-field half is now measured.** Tier M1 executed
  (`MAGNETIZED_PLAN.md` RESULTS): at 1× LEO axial Bz the anchor is
  unchanged (Δφ +1.2 V, ΔF +0.3 %, Δescape 0.06 pp — H-M1-null holds);
  at 10× a real collection tax appears (φ +33 V, thrust −11 %, entirely
  through the float; c_F untouched). This retires "magnetization has never
  been examined at all" (§0) for the field-aligned mode and hardens H1's
  own framing: the escape/optics upside floor is confirmed (escape is
  B-independent at both strengths), while the open quantity remains
  exactly the one this document identified — L/r_g, the tier M2
  transverse-B measurement, still unexamined.
