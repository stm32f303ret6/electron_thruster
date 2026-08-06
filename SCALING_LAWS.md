# SCALING_LAWS — the physics scalings behind the operating points

Reference notes for the paper. **PIC is the authority**: these closed-form
scalings exist to pick operating points, pre-register predictions, and
organize the narrative — no constant here feeds an acceptance gate, and every
number below is labelled either **measured** (from a committed
`reference_results/*/metrics.json`) or **predicted** (a scaling extrapolation
awaiting its run).

The single measured anchor throughout is the committed
`capstone.floating_body` reference (float200 parity run, PASS on all 8
gates): **200 V, 0.342 mA → 13.65 nN, φ_body = +16.98 V, escape 98.44 %,
exhaust 147.5 eV**, in the capstone plasma row (n₀ = 1.627·10¹² m⁻³,
kTe = 113.6 meV).

---

## 1. The thrust law

The escaping beam carries momentum flux

```
F = (m_e/e) · I_esc · v_ex ,      v_ex = sqrt(2 e KE / m_e)
```

which in engineering units is

```
F [nN] = 3.372 · I [mA] · sqrt(KE [eV])        (ideal: every electron, full energy)
```

Two measured corrections:

- **Effective slope.** The committed run gives `F/(I·√KE) = 3.286` — 97.5 %
  of ideal. The deficit is the ~1.6 % of beam that lands back on the craft
  plus net-vs-beam momentum bookkeeping.
- **Energy ledger.** The beam is born two cells above the cathode face, so it
  never sees the whole gap: `KE ≈ 0.81·(V − φ)` (measured 147.5 eV against
  V − φ = 183.0 V).

The body floats at `+φ`, and the cathode rides at `φ − V`, so the accelerating
potential that matters is always **V − φ**: *the float robs the beam.*

## 2. Power at fixed thrust — why low voltage wins

Supply power is `P = I·V`. Fix a thrust target F and eliminate I via the
thrust law:

```
P(V) = F · V / (c · sqrt(V − φ))          c = 3.29e-3 nN/(mA·√eV) · √0.81
```

- `dP/dV = 0` at **V = 2φ** — the unconstrained power optimum sits just above
  the float.
- For `V ≫ φ`, `P ∝ F·√V`: **at fixed thrust, every doubling of voltage costs
  ~40 % more power.** Slow-and-many beats fast-and-few on momentum per watt.
- Thrust-per-watt: `F/P = c·√(V − φ)/V ≈ c/√V`.

Measured/predicted frontier over the hardware range (same I/I_CL = 1.46):

| V | I | φ (V) | F (nN) | P (mW) | F/P (µN/W) | status |
|---|---|---|---|---|---|---|
| 100 | 0.121 mA | ~6 | ~3.4 | 12.1 | ~0.28 | predicted — `capstone.low_power` |
| 200 | 0.342 mA | **+16.98** | **13.65** | 68.4 | **0.20** | **measured, committed** |
| 300 | 0.63 mA | ~31 | ~30 | 189 | ~0.16 | predicted — `capstone.high_thrust` |

## 3. The space-charge emission ceiling — why you can't just go low

The planar Child–Langmuir current density over the emission spot
(r = 0.5 mm, gap d = 4.7 mm):

```
j_CL = (4/9) ε₀ sqrt(2e/m_e) V^1.5 / d²
I_CL = 0.083 / 0.235 / 0.431 mA at 100 / 200 / 300 V
```

This is a **scale, not a bound**: the real non-planar geometry emits
**1.46×** planar (measured at 200 V; both new stages hold that ratio). The
consequences:

- Maximum thrust scales as `F_max ∝ I_CL·√V ∝ V²` — steep. The 300 V ceiling
  buys 2.2× the thrust of 200 V.
- The feasibility floor at low V: at 100 V the spot sources only ~0.12 mA no
  matter how dense the plasma is. **Low V is where power is cheap and where
  feasibility runs out** — the optimum is the boundary: the lowest V whose
  ceilings still meet the thrust demand.
- The geometry knobs (not exercised in this repo): `I_CL ∝ 1/d²` and spot
  area — a shorter gap or wider spot moves the whole frontier without
  touching V.

## 4. Collection and the floating potential — the return circuit

Every escaping electron must be replaced by a collected ambient one; the body
potential is whatever makes that balance close.

- **Thermal collection** (validated at rung `collector.thermal` to ±1 %):
  one-sided random flux `I_the = e·A·n_e·sqrt(kTe/2π m_e)`.
- **OML-style enhancement**: a body at `+φ` pulls a wider impact-parameter
  fan, `I ≈ β·I_the·(1 + χ)` with `χ = eφ/kTe` and β an order-0.5 geometry
  factor (a can is not a sphere). Rungs `collector.biased_*` measured the
  finite-size fractions of this ceiling at χ = 26 and 88.
- **The float condition**: `I_esc = β·I_the·(1 + χ)` inverts to

  ```
  φ ≈ (kTe/e) · ( I_esc / (β·I_the) − 1 )
  ```

  φ rises ~linearly with emitted current; the stiffness (volts per amp) goes
  as `1/(n_e·√Te)` — **the night ionosphere is a much stiffer spring**, which
  is why the collection side, not the emission side, binds at night.
- At χ ≫ 1 the collectable current at a *fixed* φ goes as `n_e·φ/√Te`: per
  unit density, **hot dayside electrons are harder to collect**, not easier.
- **Extrapolation caveat for the paper**: the (1+χ) linearity is anchored at
  one point (χ ≈ 150). The 300 V run probes χ ≈ 270; if the measured φ
  deviates, that is a finding about the law form.
- **PRE-REGISTERED COMPETING HYPOTHESES** (recorded 2026-08-04, before the
  300 V run completed). Three candidate forms `I_collect ∝ (1+χ)^α` exist in
  the project lineage, agreeing at the shared anchor region (χ ≈ 140–150)
  and diverging at the 300 V operating point:

  | α | source | predicted φ at the 300 V run |
  |---|---|---|
  | 1 (linear OML) | this repo's anchor inversion (one point) | ~31 V |
  | **0.82 ± 0.06** | `electron_contactor` U-curve campaign, **fitted across six equilibria** (φ = +11 to +45 V, plus a choke at ~1.3 mA) | **~36 V** |
  | 0.5 (square root) | `electron_gun_probe` converged reservoir run (one point + transient) | ~90 V — would fail the 50 V gate and approach the 100 V choke |

  The predecessor's direct price list on the same can geometry (0.43 mA →
  +21 V, 0.74 mA → +45 V) brackets our 0.62 mA escaping current at roughly
  +35–40 V, favoring α ≈ 0.82. The 300 V run discriminates. A caveat
  travels with the comparison: the gun-probe study showed the high-χ sheath
  equilibrates on the ion timescale (~1.6 µs there), so an 800 ns plateau at
  high χ must be checked against its own late slope before any α is declared
  the winner.
- **VERDICT (2026-08-05 — both frontier runs complete, all gates PASS).**
  Measured φ at 300 V: 36.3 V tail-averaged (policy window), 38.8 V at run
  end with the late slope still decaying (+44 → +27 mV/ns over the final
  200 ns); extrapolating the slope decay puts the settled float at ~42–48 V.
  - **α = 1 (linear) is refuted** — φ passed its 31 V prediction near 650 ns
    and kept climbing.
  - **α = 0.5 is refuted** — nothing in the trajectory heads toward 90 V;
    the extrapolated ceiling stays below 50 V.
  - **α = 0.82 survives and is favored**: 36 V predicted vs 36.3 V
    tail-averaged. The pre-registered late-slope caveat applies in full: the
    true equilibrium is plausibly a few volts above the point prediction
    (upper half of the ±0.06 band, i.e. α slightly below 0.82), and its
    extrapolated top edge brushes the 50 V benign gate. A longer-tail 300 V
    run is the instrument if that band must be closed; not scheduled.
  - The 100 V run measured φ = 5.4 V (tail) extrapolating to ~6.0 V settled,
    on the ~6 V prediction — consistent, but at low χ the candidate laws
    converge, so the 100 V point confirms the anchor rather than
    discriminating α.
  - Thrust landed on its pre-registered predictions to <1 % at both
    endpoints: 30.13 nN vs 30 predicted (300 V), 3.42 nN vs 3.4 (100 V).
    The beam/exhaust side is clean; law uncertainty lives entirely on the
    collection/float side.
  - **F/P ∝ 1/√V confirmed across the full hardware range**: measured
    0.283 / 0.200 / 0.159 µN/W at 100 / 200 / 300 V vs 0.283 / (anchor) /
    0.163 predicted from the 200 V anchor — within 2.5 % everywhere.
  - Escape degrades toward low V exactly as the U-curve tax predicts
    (96.1 % at 100 V vs 98.4–99.0 % at 200–300 V) but still clears the 95 %
    gate at the cheap end — the floor operating point is feasible.

## 5. Settle time — when a PIC run measures an equilibrium

The body is a capacitor charged by the escaping beam:

```
C ≈ 4π ε₀ r_p = 0.556 pF (5 mm can; Gauss-law measured 0.5–1 pF)
τ ≈ C·φ / I_esc ≈ 28 ns at the 200 V reference
```

A run must span many τ to gate a steady state (800 ns ≈ 29τ here). τ grows
as `1/n_e` at fixed demand — thin night plasmas settle slowest, which is why
night-row validation runs need the settle check *before* trusting any gate.

## 6. Two efficiencies — do not conflate them in the paper

- **Energy conversion** `η = P_jet/P_supply = f_esc · (KE/(V−φ)) · (V−φ)/V ≈ 0.73`
  at the reference — ion-thruster-class conversion, nearly flat in V.
- **Impulse economy** `F/P ≈ 0.2 µN/W ∝ 1/√V` — ~200× below gridded ion.

Both are true simultaneously because the exhaust is electrons: superb
energy-to-jet conversion at tiny momentum per watt. This pair is the core of
the thesis claim — the second number is *why* the device only owns the nN
regime, the first is why it deserves to.

## 7. Mission coupling — the throttle strategy

From the committed 2024 orbit sweep (5 mm chipsat, real F10.7/Ap):

| altitude / pose | drag mean | drag max |
|---|---|---|
| 400 km axial | 32.9 nN | 92.4 nN |
| 400 km lateral | 21.7 nN | 60.7 nN |
| 500 km axial | 7.6 nN | 28.4 nN |
| 550 km axial | 3.9 nN | 16.3 nN |
| 600 km axial | 2.0 nN | 9.6 nN |

Demand swings ~10× over an orbit (diurnal) and ~15× across 400–600 km.

**The throttle rule — corrected by the predecessor's measured U-curve.**
The naive rule from §2 alone ("throttle V as low as feasible; P ∝ F·√V")
assumes escape stays high and current is free. The `electron_contactor`
campaign (`UCURVE_explained.md`, five converged runs at fixed ~13.6 nN
demand: 78 / 92.4 / 125 / 200 / 300 V) measured what actually happens at
fixed thrust when V drops: the required current rises, and two taxes explode
— the charging tax (φ eats 27.6 % of V at 78 V vs 8.7 % at 200 V) and escape
collapse (68.6 % at 78 V; space charge blows the beam open at high
perveance and the can eats its own beam). Specific power P/F is a **U**:
5.18 / 4.44 / **4.31 (min)** / 5.02 / 5.90 mW/nN — and below ~91 V that
thrust demand has **no equilibrium at all** (the death spiral is documented
and was confirmed by a pre-registered counterexample run, which failed by
beam optics before charging even bound).

> **Sit at the U-valley for the instantaneous demand — not as low as
> feasible.** The valley has a closed form, `V_opt ≈ 3.2·φ_eq` (injection
> offset included), and φ_eq depends on the demanded current and the local
> plasma — so the *rule* travels across rows and orbits while the *number*
> (125 V on a dense dayside row at 13.6 nN) does not. Never operate below
> the no-equilibrium boundary for the current demand.

Two slices of the (V, I) plane, not to be confused:

- **Fixed thrust, varying V** (the contactor U-curve): perveance I/I_CL
  explodes at low V — this is where the left-arm taxes live.
- **Fixed I/I_CL = 1.46, varying V** (this repo's frontier stages): the
  perveance-preserving path — beam optics stay self-similar, escape should
  stay high at all three points, and thrust varies as ~V² along it. It
  measures the *envelope boundary*; the U-curve measures the *cost inside
  it*.

The feasibility floor is the emission ceiling by day (demand-side) and the
collection stiffness by night (supply-side) — measured at the frontier's
ends by `capstone.low_power` and `capstone.high_thrust` respectively.

### 7b. The flight rule — a two-line servo on the spacecraft's own float

The U-valley collapses into a controller that needs **no model of the
ionosphere and no lookup table**:

```
1. V  ≈ 3.2 · φ                                  (servo V to the measured float)
2. I  = F_required / (c·√(V − φ))                (current from the thrust demand)
   guards:  I ≤ 1.5·I_CL(V)   and   φ ≤ 50 V
            infeasible → duty-cycle at the valley; never push V below it
```

Why this works, and why it is the paper's cleanest claim:

- **φ is the sensor.** Plasma density, electron temperature, day/night, and
  the vehicle's own current draw all collapse into where the body floats —
  and the body measures that by existing. Nothing environmental is
  hardcoded: a different orbit, altitude, or solar cycle just produces
  different φ readings, and the servo follows. This is the structural
  answer to the hardcoding trap of §9 — the rule never predicted the
  environment, so it cannot be wrong about it.
- **The 3.2 is physics, not tuning:** the marginal-cost balance gives
  `V_opt = ((2α+1)/α)·φ_eq`, ≈ 3.0–3.25 for α between 1 and 0.82, shifted
  by the measured injection offset. The only baked-in numbers are this
  factor and the two guard ceilings (I_CL is analytic; φ_max is a design
  choice).
- **The valley is shallow** (measured flat over ~110–160 V on the dayside
  row), so a 20 % error in the factor costs a few percent in power. Dummy
  rules work here because the optimum is forgiving.
- **What simulations are for, under this rule:** not a lookup table — they
  (a) measure the few constants (offset, α, escape at fixed perveance),
  (b) validate the rule's form at a stress point per axis (one dayside, one
  night row), and (c) map the guard edges (the choke boundary, the night
  stiffness). A handful of runs total; the rule flies itself, the PIC
  evidence certifies it.

One sentence for the paper: *a propellantless thruster whose optimal
controller is a two-line servo on its own floating potential.*

## 8. Plasma scaling — what one plasma row does and does not cover

Every capstone operating-point stage (100 / 200 / 300 V) runs at the **same
fixed plasma row**, inherited ladder-wide from the collector rungs:

```
n0 = 1.627e12 m^-3    Te = 1318.8 K (113.6 meV)    Ti = 936.2 K
```

A dense, dayside-like 400 km value. The 2024 orbit sweep spans
n_e = 3·10¹⁰ – 3.4·10¹² m⁻³ and Te = 845 – 3500 K — a factor ~100 in density
that the PIC evidence does **not** yet cover. The split for the paper:

**Plasma-independent (transfers to any row where φ ≪ V):**

- The thrust law `F ∝ I·√(V − φ)` and the emission ceiling `I_CL ∝ V^1.5`
  are gun physics — beam acceleration and space charge inside the can. The
  ambient plasma enters only through φ.
- At the measured row, φ/V = 17/200 ≈ 0.08: the entire voltage frontier of
  §2 (the `P ∝ F·√V` law, the F/P column) carries a ≲ 10 % plasma correction.

**Plasma-dependent (does not transfer):**

- The plasma enters the operating point through ONE dimensionless ratio,
  `I_esc/(β·I_the)` with `I_the ∝ A·n_e·√Te`, which sets the float via §4.
  The float stiffness goes as `1/(n_e·√Te)`: at the night minimum
  (n_e ≈ 30× below the measured row) the same beam current pushes φ tens of
  volts higher — toward the 50 V design limit and the 100 V choke — and the
  φ-correction to thrust stops being small. **The collection-limited night
  corner is a qualitatively different regime, and nothing in the ladder has
  measured it.**

**Numerical couplings (why night runs are safe but slow):**

- Grid: `λ_D ∝ √(Te/n)` = 1.965 mm at the measured row, and dx = 0.15 mm was
  sized for it. Thinner plasma → longer λ_D → *easier* to resolve; the
  committed row is near the densest the grid was designed for.
- Time: the settle time of §5 grows as `1/n_e` — a night-density run needs a
  proportionally longer t_end before its plateau means equilibrium, and the
  settle check must be applied before trusting any gate.

**The missing measurement:** the three-point frontier of §2 measures the
*voltage* scaling at fixed dense plasma; a run at a night-row density
(voltage fixed) would measure the *plasma* scaling — the collection-limited
corner where the concept is most stressed.

**Status (2026-08-06): pre-registered, deliberately not run.** Predictions
were committed (α = 1 → 53.4 V, 0.893 → 60.9 V, 0.82 → 68.0 V, 0.5 →
160.4 V) in `pic_sims/validation_cases/capstone/THIN_PLASMA_PLAN.md`, then
the run was cut on re-examination of what it buys. The law's density
dependence is `I ∝ n·(1+χ)^α`: the `n`-linear term is the one-sided thermal
flux, **already validated to ±1 % at rung `collector.thermal`**, and χ has no
density dependence at all. α is already discriminated on the voltage axis
(§4). What remains under test is one residual assumption — that α and β do
not drift as `r_probe/λ_D` goes 2.5 → 1.5 — and the settle limit of §5 would
blur a 53–68 V discrimination anyway. It is a **gross-breakdown detector,
not a measurement**, and stays ready rather than spent.

## 8b. Geometry scaling — MEASURED (2026-08-06)

Drag charges for the **ram silhouette**; collection and solar harvest buy the
**total skin**. The two are different areas, so body shape is a free design
lever — *if* the collection law survives the shape change. Theory says it
might not: OML gives α = 1 for a sphere and α = 0.5 for a long cylinder, and
the squat can's fitted 0.82–0.89 sits between the limits, so a slender body
should slide toward the cylinder value and pay a hidden charging tax.

Pre-registered (`capstone/SLENDER_BODY_PLAN.md`) and then measured, at
identical drive, commanded current, plasma row, grid and seed:

| hypothesis | predicted φ | measured |
|---|---|---|
| **A — area-only** (fitted α holds; demand drops 3.24×) | 4–5 V | **4.38 V** |
| B — cylinder-limit lateral (α → 0.5 on the wall) | tens of V | refuted ~10× |

Area arithmetic brackets it: 4.66 V at α = 0.893, 4.14 V at α = 0.82.
**The fitted exponent survives a 3.24× skin-area change and an aspect-ratio
change from L/r = 0.6 to 6.**

The scaling rule that follows: at fixed demand, **φ falls as skin area rises**,
as `(1+χ) ∝ A^(−1/α)` — a 3.24× area buys a 3.83× drop in enhancement demand.
And because `KE = κ(V − φ)`, **a lower float returns thrust**: 13.65 → 14.22 nN
at the same current and the same drag bill. Growing the collector is a thrust
*bonus*, not a penalty. This is why the concept scales along the rod, not into
the cube.

Still extrapolation: L/r beyond 6, where the cylinder limit must eventually
bite, and radii approaching λ_D, which converge on bare-tether collection
(Sanmartín 1993).

## 8c. Scale invariance — why this is not a chipsat result

The measured bodies are Ø10 mm. The mission table is a 100 g craft. Neither is
a useful spacecraft, so the question that decides whether any of this matters
is: **does the feasibility condition contain a size?**

It does not. The argument is two lines of area bookkeeping.

- **Demand is areal.** Drag goes as the ram silhouette `A_ram`. Holding
  altitude needs `F = F_drag`, so `I = F/(c_F·√KE) ∝ A_ram` and
  `P = I·V ∝ A_ram`. Power *per unit ram area* is a function of altitude and
  drive voltage only.
- **Supply is areal.** Harvest goes as cell area, which is a fraction of the
  skin `A_skin`. Power available per unit skin area is a property of the cells.

Divide: the closure margin is `(harvest/m² · A_skin) / (demand/m² · A_ram)` —
**size cancels, and what remains is the shape ratio `A_skin/A_ram` and the
altitude.** Note also that station-keeping thrust equals drag *regardless of
mass*, so vehicle mass never enters either.

Computed from the committed mission CSVs (`model/scale_analysis.py`):

| power demand per m² of ram silhouette | 400 km | 500 km | 550 km | 600 km |
|---|---|---|---|---|
| at 100 V | 1451 W | 335 W | 170 W | 88 W |

| body | skin/ram | 500 km | 550 km | 600 km |
|---|---|---|---|---|
| Ø10 mm can, squat (measured) | 4 | 0.4× | 0.8× | 1.6× |
| 1U cube, face-on | 6 | 0.6× | 1.2× | 2.3× |
| **Ø10 mm can, slender (measured)** | **14** | **1.4×** | **2.8×** | **5.4×** |
| **3U CubeSat, end-on** | **14** | **1.4×** | **2.8×** | **5.4×** |
| 6U CubeSat, end-on | 12 | 1.2× | 2.4× | 4.6× |

The slender can and the 3U CubeSat return *identical* margins. The 400 km wall
is scale-free too: nothing closes there. In absolute terms a 3U end-on needs
**8.8 mA / 0.88 W at 600 km**, 17 mA / 1.7 W at 550 km, 34 mA / 3.4 W at
500 km.

**Two things get easier with size.** The enhancement demanded over bare
thermal collection *falls* as skin grows — a 3U needs 4.3× the thermal flux at
600 km where the chipsat needs 15×, and the chipsat frontier runs at
χ ≈ 150–320. Since bare thermal collection is the rung validated to ±1 % and
the enhancement exponent is the fitted quantity, **larger bodies rest on less
extrapolation, not more.** And lower χ means a lower float, which by
`KE = κ(V−φ)` returns drive energy to the beam.

**The regime caveat.** Every committed run is at `r/λ_D ≈ 2.5`. CubeSat radii
are 25–60 λ_D, where OML does not apply: the sheath is thin and grows with φ,
so enhancement is an area ratio `(r_s/r)²` with `r_s − r ~ λ_D(2χ)^{3/4}`.
That model — an **estimate, not a calibration** — puts a 3U at ~12 V (600 km),
~25 V (550 km), ~47 V (500 km): benign in the corridor, tightening below it.
The areal power balance above does not depend on this; only the floats do.

## 9. From scaling laws to a model — the plan, and what buys confidence

These sections are algebra applied by hand. Once the two frontier runs land,
the plan is a **minimal executable model** — one file, on the order of a few
hundred lines — that:

- derives every law constant from **all committed** `metrics.json` files (by
  then three points, not one), with the fit residuals printed, not hidden;
- sweeps any orbit CSV to make mission-level statements (duty cycle,
  feasibility fraction, closure vs altitude) and the paper figures;
- **flags every row that falls outside the measured envelope** — density,
  χ, or perveance beyond what any committed run has measured — and splits
  every mission claim into "measured-envelope rows" and "extrapolated rows,
  needing a targeted PIC run". This is the guard against the hardcoding
  trap: a new orbit (inclination, local-time coverage, solar cycle — not
  just altitude) changes which rows land in which bucket, never the laws
  themselves, and the flagged bucket says exactly where the next GPU-hours
  go;
- evaluates optimization rules **per row** (e.g. the §7 U-valley
  `V_opt ≈ 3.2·φ_eq`), never as frozen numbers: fitted constants stay home,
  physics forms travel;
- **never feeds an acceptance gate** — PIC stages stay self-contained, and
  the model remains a targeting/analysis tool with no authority over
  evidence.

No promotion machinery, no calibration registry: with this few points the
provenance *is* the anchor table below.

**What buys model confidence — placement, not count:**

- **Overdetermination tests the law form.** One anchor point fits constants
  and can test nothing. Three voltage points overdetermine them for the
  first time: `k` must fit all three at once, and the float must follow the
  `(1+χ)` line at χ ≈ 50 / 150 / 270 simultaneously. Every point past the
  first is a falsification opportunity.
- **Points along one axis only test that axis.** The three frontier points
  will make the voltage laws solid and say nothing about the plasma laws
  (§8). A fourth voltage point adds almost nothing; the first night-density
  point adds a tested dimension.
- **Confidence extends over the measured envelope, not beyond it.** Inside
  the span of measured points the model interpolates; outside it
  extrapolates, whatever the point count. The mission spans ~100× in
  density; the measured envelope spans 1×.
- **Numerical confidence is a separate budget.** Same point, different
  seed/grid/PPC — currently zero measured everywhere in the ladder
  (disclosed caveat). One repeat run bounds it.

Priority order per GPU-hour: voltage frontier (**complete 2026-08-05**) →
convergence repeat at the 200 V anchor → minimal model → night-density
point only if the model predicts a thin night margin.

---

## Anchor bookkeeping

| quantity | value | provenance |
|---|---|---|
| F, φ, escape, KE at 200 V | 13.65 nN, +16.98 V, 98.44 %, 147.5 eV | **measured** — `capstone/2_chipsat_thruster/reference_results/20260801T142601Z_2f822a95/metrics.json` |
| I/I_CL emission ratio | 1.46 | **measured** — same run vs planar CL scale |
| thermal collection | ±1 % of exact | **measured** — `collector.thermal` reference |
| F, φ, escape, KE at 300 V | 30.13 nN, +36.3 V (tail; §4 verdict), 98.99 %, 210.1 eV | **measured** — `capstone/3_high_thrust/reference_results/20260804T154756Z_b854dcbe/metrics.json` |
| F, φ, escape, KE at 100 V | 3.42 nN, +5.4 V (→ ~6.0 V settled), 96.12 %, 77.2 eV | **measured** — `capstone/4_low_power/reference_results/20260804T230218Z_0adb478f/metrics.json` |

Ladder-wide caveats travel with every number: reduced ion mass (400 mₑ),
electrostatic (no B, no ram drift), single grid/PPC/seed, finite-time
equilibrium on the ion clock.
