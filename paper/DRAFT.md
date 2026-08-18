# draft — ambient-electron exchange thruster (concept-first)

working skeleton for `main.tex`. same order as the paper, note form.
edit here first, port to prose after.

## 0. claim (one paragraph)

- thruster with **no propellant, no tank, no neutralizer**: cold electron gun
  inside a sealed floating body, one aperture, ionosphere closes the circuit.
- concept = a parameter-free ideal law; pic runs = evidence that a real
  geometry sits within ~20 % of it.
- mission corridor (anchor body + any same-shape body, CubeSats included),
  stated as power demand: 8–17 mW at 550–600 km, 41 mW at 500 km; 400 km
  mean demand covered at the 350 V envelope top (charging margin
  shape-dependent), maxima/night rows stated honestly as open. supplying
  the power is mission design (body-mounted solar is the worked example,
  not a requirement).

## 1. why (intro)

- small sats below ~600 km die to drag in months–years.
- needed: nN–µN continuous thrust from mW-class power → **no flight system
  lives there** (smallest flight EP: ~5–30 µN at 8+ W, in 0.3–1 kg packages).
- idea: run the neutralizer *as* the thruster. fire electrons out, body
  charges +, ambient electrons return through the skin. propellant mass flow:
  ~ng/year, all from the ionosphere.
- five contributions:
  1. parameter-free ideal law + measured frontier validates it (within 20 %)
  2. collection law discriminated (pre-registered) on **two axes** —
     voltage (100–350 V) and density — → charging tax fixed, measured
     conservative along density
  3. momentum ledger: the return current does not cancel thrust
  4. mission corridor from year-long propagations, extrapolation flagged
  5. shape run → size cancels; corridor carries to cubesats unchanged;
     voltage × geometry factorial closed at 350 V — the laws **compose**
     (slender at the 400 km drive: φ 14.0 V predicted 11–17, F 43.3 nN
     predicted 42–43)

## 2. operating principle (the cycle)

1. supply holds cathode at $-V$ vs body → electrons accelerate away, exit
   through the aperture.
2. exit energy $\approx e(V-\varphi)$ minus space charge (measured
   KE/(V−φ) = 0.81, constant over the range).
3. each departure leaves the body +1 charge → body floats up (measured
   +16.98 V at 200 V).
4. positive body collects ambient electrons until collected = escaped
   (balance closes to 1.5–3.5 % at all points).
5. escaping beam momentum = thrust; returning electrons deposit ~1–9 %
   (gated per run).

no valves, no gimbal, no plasma stage. throttle = $(V, I)$ only.

## 3. the ideal law (the concept — before any simulation)

- beam momentum flux, nothing but $m_e$ and $e$:

$$F = \sqrt{2 m_e / e}\; I \sqrt{KE}, \qquad \sqrt{2 m_e/e} = 3.37\ \text{nN/(mA}\sqrt{\text{eV}})$$

- ideal beam-supply power $P = VI$ → fixed-thrust power law:

$$P = \frac{F \sqrt{V}}{c_{ideal}}, \qquad c_{ideal} = \sqrt{2 m_e/e}$$

- **throttle principle**: largest feasible escaped current, lowest voltage
  that meets the thrust demand.
- feasible current bounded by (acknowledge, don't optimize):
  - emitter ceiling
  - ambient return-current availability
  - acceptable spacecraft potential
  - beam escape
- this law is the concept; the rest of the paper is evidence:
  - how close does a real geometry get? → §5.1 (within 20 %)
  - does the form survive? → §5 ($1/\sqrt{V}$ within 2.5 %)
  - what sets the return current? → §6 (collection law)

## 4. simulation method + evidence contract

- warpx 26.5, RZ electrostatic, embedded-boundary conductor, charge-pump
  float (emitted − collected → φ via gauss-law capacitance).
- deck: ⌀10 mm × 5.9 mm can, 4 mm aperture, internal cathode disk.
  plasma row: $n_e = 1.627{\cdot}10^{12}$ m⁻³, $kT_e = 113.6$ meV,
  reservoir recycle. dx = 0.15 mm (debye 1.97 mm), CFL dt, 16 ppc,
  reduced ion mass 400 $m_e$, 800 ns/run (density continuation: 2.4 µs).
- evidence contract:
  - frozen + hashed configs, atomic manifests, interrupted runs discarded
  - gates fixed in versioned policy files **before** each run
  - 100/300/350 V (+ slender-350) predictions + collection-law hypotheses
    pre-registered
  - validation ladder underneath (laplace, thermal ±1 %, biased, floating,
    gun rungs); ledger-vs-dump cross-checks ~1e-9

## 5. measured frontier

| V | I (mA) | φ (V) | F (nN) | P (mW) | F/P (µN/W) | escape | KE (eV) |
|---|---|---|---|---|---|---|---|
| 100 | 0.121 | +5.40 | 3.42 | 12.1 | 0.283 | 96.1 % | 77.2 |
| 200 | 0.342 | +16.98 | 13.65 | 68.4 | 0.200 | 98.4 % | 147.5 |
| 300 | 0.630 | +36.30 | 30.13 | 189 | 0.159 | 99.0 % | 210.1 |
| 350 | 0.793 | +48.29 | 40.48 | 278 | 0.146 | 99.1 % | 237.0 |

- fixed $I/I_{CL} = 1.46$ along the path (self-similar optics).
- 100/300 V thrusts landed on pre-registered predictions to <1 %; the
  350 V extension (pre-registered 2026-08-17) landed at 0.15 %
  (40.48 vs 40.5).
- $F/P \propto 1/\sqrt{V}$ confirmed within 2.5 % over 100–300 V; the
  350 V point sits ~3 % below the ideal $1/\sqrt{V}$ — the growing float
  tax, exactly what the two-constant law predicts.
- two efficiencies, side by side on purpose:
  - energy conversion $\eta \approx 0.73$ (ion-thruster class)
  - impulse economy ~0.2 µN/W (~200× below gridded ion)
  - first explains why it deserves the nN regime, second why it owns
    nothing above it.
- error band (grid): F ±4 %, KE ±7 %, φ ±2 %.

### 5.1 validation vs the ideal law

measured / bound = **1.19–1.24** across the four points (the upward drift
is the growing float tax). the gap is a closed ledger:

| tax | value | mechanism | cost |
|---|---|---|---|
| energy fraction κ | 0.81 | injection-plane space charge | ~10 % |
| thrust slope $c_F$ | 0.97 $c_{ideal}$ | plume divergence | ~3 % |
| float tax $V/(V-\varphi)$ | 1.06–1.16 | body charging | 6–16 % |

- with measured constants ($c_{eff} = c_F\sqrt{\kappa} = 0.87\,c_{ideal}$)
  the law reproduces the powers to 4–7 %:
  model 11.7 / 65.8 / 177.9 / 258 vs measured 12.1 / 68.4 / 189 / 278 mW
  (the 7 % is 350 V, where φ/V is largest).
- off-optimum (low V, fixed thrust): 1.5–2× the bound. decomposes into
  (i) non-optimal voltage, (ii) beam interception in the can (isolated gun
  transmits 99.99 % at the same command). geometry-specific, not the law.
- confirmation inside committed data: model-optimal V for 13.65 nN is
  **196 V** → the 200 V anchor *is* that run (closes to 4 %, escape 98.4 %).
  the divergent points all commanded 2.7–10× over the emission ceiling —
  voltages the throttle principle never selects.
- role of pic: **prove the concept, not certify a mission thruster.**
  missions use the measured (conservative) calibration.

## 6. collection law (pre-registered discrimination)

$$I = \beta A\, j_{th}(n_e, T_e)\,(1+\chi)^\alpha, \qquad \chi = e\varphi/kT_e$$

predictions recorded before the 300 V run (all agree at 200 V anchor):

| α | predicted φ(300 V) | verdict |
|---|---|---|
| 1 (linear) | +31 V | refuted (float passes 31, keeps climbing) |
| 0.82 ± 0.06 | +36 V | **survives** (measured +36.30 V) |
| 0.5 (sqrt) | +90 V | refuted (nothing approaches 90) |

- caveat (pre-registered): 300 V still relaxing at 800 ns; settled
  extrapolation 42–48 V, brushes the 50 V limit. fit across all three
  points: α = 0.85–0.89.
- **350 V extension (pre-registered 2026-08-17): the fitted law holds one
  step past its fit range** — predicted φ 47 V, measured 48.29 V tail
  (endpoint 51.1 V, still +34 mV/ns: the settled float extrapolates past
  the 50 V limit at this compact geometry — see §11 for the slender
  answer).
- this law = the charging tax schedule: φ eats 5 % of supply at 100 V,
  12 % at 300 V, 14 % at 350 V.

### 6.1 the density axis (second pre-registered discrimination)

- thin plasma spoke: n0/3 (5.42e11 m⁻³), rmax 30 → 40.8 mm for the √3×
  larger λ_D, everything else the anchor deck. predictions committed
  before launch: α = 1 → 53.4 V, 0.893 → 60.9, 0.82 → 68.0, 0.5 → 160.4.
- 800 ns run: healthy (all trust gates), but unsettled — only a bound,
  φ_settled > 31.6 V. pre-registered 2.4 µs continuation closed it:
  **first settled float of the campaign** — φ = 42.5 V, late slope
  −0.14 V/µs, escape 99.1 %, balance 0.10 %, F 12.39 nN, KE 122.0 eV
  (injection-plane prediction 122.6).
- scorecard, a surprise on both ends:
  - **α = 0.5 refuted again**, independently of the voltage axis (choke
    ceiling parked above 160 V; float saturates at 42.5).
  - **every fixed α ≤ 1 overshoots**: (1+χ) rose 2.39× for the 3× density
    drop where fixed α ≤ 1 needs ≥ 3×. secant α_eff = ln 3/ln 2.39 =
    **1.26**, or equivalently β +38 % at the default α — the direction
    sheath expansion toward OML predicts as r/λ_D falls 2.5 → 1.5.
  - **benign gate passes** (42.5 < 50 V): thin plasma does *not* end the
    envelope at the anchor drive. the fitted law **over-predicts the
    float cost of thin plasma** → conservative along density.
- caveat: one 3× step (secant, not a fit), across the disclosed rmax
  change; beyond n0/3 toward the ~1e11 night minimum stays extrapolated —
  now with a measured directional bias.

### 6.2 robustness: the geomagnetic field (M1, field-aligned)

- only axial B fits the RZ deck = exactly the field-aligned-firing flight
  mode. pre-registered null bounds at 1×; tax direction (not magnitude)
  at 10×.
- **1× LEO (30 µT): null holds on every bound** — φ 17.22 V (anchor
  16.98), F 13.64 nN (anchor 13.65), escape Δ 0.06 pp. flight field
  leaves the operating point untouched.
- **10× (300 µT): a collection tax, entirely through φ** — magnetized
  skin collects less: φ +32.6 V over the anchor (unsettled → lower
  bound), KE 147 → 116 eV, F −11 %. beam formation B-independent (escape
  98.3 %; r_g,beam ≥ 0.10 m ≫ device). two-constant law reproduces both
  runs (13.56/12.03 predicted vs 13.64/12.06 measured): c_F untouched,
  whole tax enters via collection.
- mission flies at 1×, where the null holds. transverse B (far field,
  r_g ≈ 1.4 m ≫ 30 mm domain) not answerable in RZ → tier M2, future
  work.

## 7. momentum ledger — is the thrust real?

- objection: emitted current *returns*. does it cancel?
- predecessor (⌀14 mm, 800 V): full control-volume ledger every window.
  - vacuum fixture: residual +0.80 nN vs 1 nN gate
  - full-return null (escape 0 %): closed thrust −0.39 nN ≈ 0 ✓
  - operating point: closed thrust = $F_{beam}$ − 2.3 %; impact channel
    cancelled by field pull, not by the beam
- this campaign: $|F_{net}|/F_{beam}$ gated per run — 1.0 % (300 V) to
  8.8 % (100 V).
- physics ceiling: even all-astern arrival ≤ $\sqrt{\varphi/KE} \approx 41$ %;
  isotropic arrival → measured percent level.

## 8. numerical credibility

| axis | result |
|---|---|
| code-to-code (migrated vs predecessor, 200 V) | float 0.05 %, escape 0.001 %, F 0.09 % |
| thermal collection vs theory | ±1 % |
| ledger vs particle dumps | ~1e-9 (gate 2e-2) |
| ppc ×2 | ≤0.05 % — closed axis |
| grid 0.15→0.10 mm | F +4.0 %, KE +7.4 %, φ −1.8 % → the error band |
| dt, seed (predecessor) | ≤0.5 % |

- grid = leading uncertainty; sign is conservative for every gate
  (finer → more thrust, lower float). third grid point = future work.

## 9. comparison

- every incumbent's lowest operating power ≥ 10× our 300 V frontier point;
  FEEP starts at ~8 W. (the 350 V envelope top draws 278 mW — still well
  below every incumbent's floor.)
- jet efficiencies found: electrospray 28–45 %, FEEP ~35 %, hall ~31–44 %.
  ours: 68–73 % — exceeds every value found.
- but F/P ~200× below gridded ion → natural handoff: this device
  <0.1 µN, electrospray at µN, ion/hall at mN. that boundary is part of
  the claim.
- "continuous thrust" argument at nN is a **dry-system floor** argument
  (tank+feed+PPU ~0.3–1 kg does not shrink), not a propellant-mass one.

## 10. missions (year-long, real F10.7/Ap, IRI + NRLMSISE, per-5-min rows)

model applies the throttle principle per row, solves min-power $(V,I,\varphi)$
self-consistently with the collection law; out-of-envelope rows flagged,
never averaged in.

| altitude/pose | drag mean/max (nN) | feasible | duty | P mean (mW) | envelope |
|---|---|---|---|---|---|
| 400 axial | 32.9 / 92.4 | 36 % | 113 % | 175 | exits (duty > 100 % — night-side collection cap at this geometry, no longer the voltage ceiling) |
| 400 lateral | 21.7 / 60.7 | 63 % | 74 % | 129 | inside on impulse; thrust axis needs redesign |
| 500 axial | 7.6 / 28.4 | 76 % | 39 % | 41 | **inside** |
| 550 axial | 3.8 / 16.3 | 85 % | 29 % | 17 | **inside** |
| 600 axial | 2.0 / 9.6 | 93 % | 23 % | 8 | **inside** |

(model re-run 2026-08-17 at the 350 V cap; the extended envelope moved
400 axial duty 140 → 113 % and lateral 92 → 74 %. the binding constraint
at 400 axial is now the benign-float collection cap on thin night rows at
the squat geometry — the slender skin, measured to cut the float 3.4× at
this drive, is the modeled-but-not-yet-swept fix.)

- honesty flags: night rows drive the boundary; the density axis now has
  one measured, settled 3× step (§6.1) showing the law *over-predicts*
  the float there → the corridor's night edge is biased conservative;
  rows below n0/3 toward the ~2e11 night minimum remain extrapolated
  (with measured directional bias); powers are beam power $VI$ only.
- the 350 V pair moves the 400 km axial **mean** inside the measured
  envelope: 40.48 nN squat (~81 % duty at the tested dayside row) /
  43.33 nN slender (~76 %) vs the 32.9 nN mean demand. the year-model
  duty above (113 %) is the harder statement: capability-weighted over
  real rows, where thin night plasma caps collection at the 50 V float
  limit on the squat skin.
- why 400 km stays open even with the mean covered (axial pose):
  1. impulse: peak drag (92.4 nN) needs ~510 V — still far above the
     350 V envelope; no battery fixes the uncovered maxima.
  2. charging: at 350 V the squat can floats ON the 50 V limit (48.3 V
     tail, endpoint rising); the slender shape carries the margin
     (14.0 V) — coverage at 400 km is shape-dependent.
  3. energy: ideal-bound power at best V ≈ 98 mW — an order above the
     example body-mounted solar supply (cells give ~100 W/m² of skin,
     drag wants ~1450 W/m² of ram; best shape ratio 14 → margin 0.3
     against that example).
  → a design/research target, not a closed case — but now with the mean
     demand and the margin geometry both measured.

## 11. geometry + scale-free

- slender run (⌀10 × 30.5 mm, skin ×3.24, same drive/grid/seed):
  φ 16.98 → **4.38 V** (area-only hypothesis confirmed, cylinder-limit
  refuted ~10×), thrust *up* to 14.22 nN (lower float returns drive
  energy). escape 98.4 %.
- **the factorial corner (pre-registered 2026-08-17): the laws compose.**
  slender at the 400 km-enabling drive (350 V / 0.793 mA, identical to
  the squat run): φ **14.00 V** measured vs 11–17 V composed prediction,
  F **43.33 nN** vs 42–43 predicted (+7 % over the squat via the
  returned float; KE 273 vs 237 eV). 2×2 (200/350 V × L/r 0.6/6) fully
  measured → the voltage frontier and geometry law are one validated 2D
  operating map. mission reading: the shape the vehicle takes anyway
  covers the 400 km mean at ~76 % duty with 3.6× charging margin, where
  the squat can sits on the limit.
- drag buys the **ram silhouette**; collection + any body-mounted supply buy the **skin** →
  both sides of the power balance are areal → **size cancels**. what
  survives: shape ratio + altitude.

| body (skin/ram) | 400 | 500 | 550 | 600 km |
|---|---|---|---|---|
| squat can (4) | 0.1 | 0.4 | 0.8 | 1.6 |
| 1U face-on (6) | 0.1 | 0.6 | 1.2 | 2.3 |
| slender can / 3U end-on (14) | 0.3 | **1.4** | **2.8** | **5.4** |
| 6U end-on (12) | 0.3 | 1.2 | 2.4 | 4.6 |

(margin = example solar supply/demand at 100 V; the size-free ratio is the
result. 3U at 600 km: 8.8 mA, 0.88 W — cubesat-supply class.)

- larger bodies need *less* enhancement over bare thermal flux (4.3× vs
  15×) → **less extrapolation, not more**.
- caveat: cubesat radii are 25–60 $\lambda_D$ (thin-sheath regime, not
  measured). child-sheath estimate: benign at 550–600, tight at 500.
  single large-body run settles it — cheapest follow-on.

## 12. practical

- bom: conducting structure, mW-class HV supply (100–350 V), cold gun,
  aperture. no tank/valves/feed/RF/gimbal. floor = cathode + boost
  converter + the skin itself.
- retrofit: ion/hall neutralizer + spacecraft structure *is* this
  thruster after propellant exhaustion — software + wiring.
- lab demo: TODO (user's vacuum-chamber bench results).

## 13. limitations (state plainly)

1. collection law's density axis: one 3× step measured, settled,
   conservative (§6.1) — a secant, not a fit; α_eff vs β drift not
   separable with one step. below n0/3 = extrapolation with measured
   directional bias.
2. geometry axis: two shapes (L/r 0.6 and 6), each measured at two drives
   (200/350 V) — a 2×2 factorial, not a continuous map.
3. no run in the cubesat sheath regime (r/λ_D ≈ 2.5 measured vs 25–60).
4. grid resolution ±4–7 %, sign conservative.
5. anchor-row floats unsettled at 800 ns (300 V: 42–48 V band carried;
   350 V squat: 48.3 V tail with 51.1 V endpoint rising — settled value
   likely past the 50 V limit; slender-350: 14–17 V band); only the
   thin-plasma row is settled (2.4 µs).
6. reduced ion mass 400 $m_e$ (not O⁺).
7. stationary plasma (no ram wake — deferred, not estimated).
8. RZ axisymmetric. geomagnetic field: field-aligned measured (1× null,
   10× tax = lower bound, §6.2); transverse B not answerable in RZ →
   open (tier M2).
9. beam power only (no gate/converter overheads).
10. throttle optimization deferred: quoted powers = ideal bound + measured
    closure; off-optimum losses geometry-specific
    (→ `future_work/OPTIMIZATION_LEVERS.md`).

## 14. conclusion (three results)

1. measured frontier validates the parameter-free law: within 20 % of the
   bound, $1/\sqrt{V}$ within 2.5 %, η ≈ 0.73 at 0.16–0.28 µN/W.
2. the thrust is real: ledger + full-return null + per-run gates (1–9 %).
3. collection law fixes the charging tax — discriminated on voltage
   (100–350 V) *and* density (settled), measured conservative along
   density, and **composes with the geometry law** (2×2 factorial:
   slender at 350 V landed at φ 14.0 V vs 11–17 predicted);
   flight-strength field-aligned B is a null → conservative model →
   corridor: closes 550–600, impulse 500, 400 mean covered at the
   envelope top with shape-dependent charging margin (maxima and night
   rows open) — and by the areal argument the corridor is a statement
   about shape and altitude, not size.

cheap to test: a gun and a hole. retrofit path exists on every flying
ion/hall neutralizer.
