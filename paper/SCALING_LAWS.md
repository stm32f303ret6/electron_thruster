# SCALING_LAWS: the physics scalings behind the operating points

Reference notes for the paper. PIC is the authority. These closed-form
scalings exist to pick operating points, pre-register predictions, and
organize the narrative. No constant here feeds an acceptance gate, and every
number below is labelled either measured (from a committed
`reference_results/*/metrics.json`) or predicted (a scaling extrapolation
awaiting its run).

The single measured anchor throughout is the committed
`capstone.floating_body` reference (float200 parity run, PASS on all 8
gates): 200 V, 0.342 mA → 13.65 nN, φ_body = +16.98 V, escape 98.44 %,
exhaust 147.5 eV, in the capstone plasma row (n₀ = 1.627·10¹² m⁻³,
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

1. Effective slope. The committed run gives `F/(I·√KE) = 3.286`, 97.5 %
   of ideal. The deficit is the ~1.6 % of beam that lands back on the craft
   plus net-vs-beam momentum bookkeeping.
2. Energy ledger. The beam is born two cells above the cathode face, so it
   never sees the whole gap: `KE ≈ 0.81·(V − φ)` (measured 147.5 eV against
   V − φ = 183.0 V). A vacuum field solve puts the launch plane 19 % of V
   above the cathode, and the measured deficit is 17–18 % of V in every run
   at this loading, whatever φ: it scales with V, not V − φ, and a real
   cathode would give κ ≈ 1 (`future_work/CATHODE_LAUNCH_PLAN.md`).

The body floats at `+φ` and the cathode rides at `φ − V`, so the accelerating
potential that matters is always V − φ. The float robs the beam.

## 2. Power at fixed thrust: why low voltage wins

Supply power is `P = I·V`. Fix a thrust target F and eliminate I via the
thrust law:

```
P(V) = F · V / (c · sqrt(V − φ))          c = 3.29e-3 nN/(mA·√eV) · √0.81
```

- `dP/dV = 0` at V = 2φ. The unconstrained power optimum sits just above
  the float.
- For `V ≫ φ`, `P ∝ F·√V`: at fixed thrust, every doubling of voltage costs
  ~40 % more power. Slow-and-many beats fast-and-few on momentum per watt.
- Thrust-per-watt: `F/P = c·√(V − φ)/V ≈ c/√V`.

Measured/predicted frontier over the hardware range (same I/I_CL = 1.46):

| V | I | φ (V) | F (nN) | P (mW) | F/P (µN/W) | status |
|---|---|---|---|---|---|---|
| 100 | 0.121 mA | ~6 | ~3.4 | 12.1 | ~0.28 | predicted — `capstone.low_power` |
| 200 | 0.342 mA | **+16.98** | **13.65** | 68.4 | **0.20** | **measured, committed** |
| 300 | 0.63 mA | ~31 | ~30 | 189 | ~0.16 | predicted — `capstone.high_thrust` |

## 3. The space-charge emission ceiling: why you cannot just go low

The planar Child–Langmuir current density over the emission spot
(r = 0.5 mm, gap d = 4.7 mm):

```
j_CL = (4/9) ε₀ sqrt(2e/m_e) V^1.5 / d²
I_CL = 0.083 / 0.235 / 0.431 mA at 100 / 200 / 300 V
```

This is a scale, not a bound: the real non-planar geometry emits
1.46× planar (measured at 200 V; both new stages hold that ratio). The
consequences:

- Maximum thrust scales as `F_max ∝ I_CL·√V ∝ V²`, which is steep. 300 V
  buys 2.2× the thrust of 200 V; the measured 350 V point delivers 2.97×
  (40.48 vs 13.65 nN) against the 3.06× the pure V² law predicts.
- The feasibility floor at low V: at 100 V the spot sources only ~0.12 mA no
  matter how dense the plasma is. Low V is where power is cheap and where
  feasibility runs out. The optimum is the boundary: the lowest V whose
  ceilings still meet the thrust demand.
- The geometry knobs (not exercised in this repo): `I_CL ∝ 1/d²` and spot
  area. A shorter gap or wider spot moves the whole frontier without
  touching V.

## 4. Collection and the floating potential: the return circuit

Every escaping electron must be replaced by a collected ambient one; the body
potential is whatever makes that balance close.

- Thermal collection (validated at step `collector.thermal` to ±1 %):
  one-sided random flux `I_the = e·A·n_e·sqrt(kTe/2π m_e)`.
- OML-style enhancement: a body at `+φ` pulls a wider impact-parameter
  fan, `I ≈ β·I_the·(1 + χ)` with `χ = eφ/kTe` and β an order-0.5 geometry
  factor (a can is not a sphere). Steps `collector.biased_*` measured the
  finite-size fractions of this ceiling at χ = 26 and 88.
- The float condition `I_esc = β·I_the·(1 + χ)` inverts to

  ```
  φ ≈ (kTe/e) · ( I_esc / (β·I_the) − 1 )
  ```

  φ rises ~linearly with emitted current; the stiffness (volts per amp) goes
  as `1/(n_e·√Te)`. The night ionosphere is a much stiffer spring, which
  is why the collection side, not the emission side, binds at night.
- At χ ≫ 1 the collectable current at a fixed φ goes as `n_e·φ/√Te`: per
  unit density, hot dayside electrons are harder to collect, not easier.
- Extrapolation caveat for the paper: the (1+χ) linearity is anchored at
  one point (χ ≈ 150). The 300 V run probes χ ≈ 270; if the measured φ
  deviates, that is a finding about the law form.
- Pre-registered competing hypotheses (recorded 2026-08-04, before the
  300 V run completed). Three candidate forms `I_collect ∝ (1+χ)^α` were on
  the table, agreeing at the shared anchor region (χ ≈ 140–150)
  and diverging at the 300 V operating point:

  | α | source | predicted φ at the 300 V run |
  |---|---|---|
  | 1 (linear OML) | sphere OML theory; this repo's anchor inversion (one point) | ~31 V |
  | **0.82 ± 0.06** | intermediate candidate between the OML sphere (α = 1) and cylinder (α = 0.5) limits — a can is neither — **pre-registered with a ±0.06 band** | **~36 V** |
  | 0.5 (square root) | OML-cylinder / thin-sheath square-root theory | ~90 V — a 30 % float tax on the 300 V drive, approaching the 100 V choke |

  The 300 V run discriminates. The fixed-thrust throttle stages
  (`future_work/UCURVE_PLAN.md`, resolved 2026-08-08; stages now under
  `future_work/ucurve_pic_stages/`)
  extended the measured (I_esc, φ) price list to a second slice: all six
  committed equilibria fit `(1+χ)^α` with α_all = 0.922 and residuals
  ≤ 9.3 % (`model/mission_model.py --calibrate`). One caveat
  travels with the comparison: at high χ the sheath equilibrates on the ion
  timescale, so an 800 ns plateau must be checked against its own late slope
  before any α is declared the winner (the late-dφ/dt line every capstone
  analysis reports).
- Verdict (2026-08-05, both frontier runs complete, all gates PASS).
  Measured φ at 300 V: 36.3 V tail-averaged (policy window), 38.8 V at run
  end with the late slope still decaying (+44 → +27 mV/ns over the final
  200 ns); extrapolating the slope decay puts the settled float at ~42–48 V.
  1. α = 1 (linear) is refuted. φ passed its 31 V prediction near 650 ns
     and kept climbing.
  2. α = 0.5 is refuted. Nothing in the trajectory heads toward 90 V;
     the extrapolated ceiling stays below 50 V.
  3. α = 0.82 survives and is favored: 36 V predicted vs 36.3 V
     tail-averaged. The pre-registered late-slope caveat applies in full: the
     true equilibrium is plausibly a few volts above the point prediction
     (upper half of the ±0.06 band, i.e. α slightly below 0.82), and its
     extrapolated top edge reaches about 50 V, a 17 % tax on the 300 V
     drive. A longer-tail 300 V
     run is the instrument if that band must be closed; not scheduled.
  4. The 100 V run measured φ = 5.4 V (tail) extrapolating to ~6.0 V settled,
     on the ~6 V prediction. Consistent, but at low χ the candidate laws
     converge, so the 100 V point confirms the anchor rather than
     discriminating α.
  5. Thrust landed on its pre-registered predictions to <1 % at both
     endpoints: 30.13 nN vs 30 predicted (300 V), 3.42 nN vs 3.4 (100 V).
     The beam/exhaust side agrees; law uncertainty lives entirely on the
     collection/float side.
  6. F/P ∝ 1/√V confirmed across the full hardware range: measured
     0.283 / 0.200 / 0.159 µN/W at 100 / 200 / 300 V vs 0.283 / (anchor) /
     0.163 predicted from the 200 V anchor, within 2.5 % everywhere.
  7. Escape degrades toward low V exactly as the low-voltage escape tax predicts
     (96.1 % at 100 V vs 98.4–99.0 % at 200–300 V) but still clears the 95 %
     gate at the cheap end. The floor operating point is feasible.

## 5. Settle time: when a PIC run measures an equilibrium

The body is a capacitor charged by the escaping beam:

```
C ≈ 4π ε₀ r_p = 0.556 pF (5 mm can; Gauss-law measured 0.5–1 pF)
τ ≈ C·φ / I_esc ≈ 28 ns at the 200 V reference
```

A run must span many τ to gate a steady state (800 ns ≈ 29τ here). τ grows
as `1/n_e` at fixed demand. Thin night plasmas settle slowest, which is why
night-row validation runs need the settle check before trusting any gate.

## 6. Two efficiencies: do not conflate them in the paper

1. Energy conversion `η = P_jet/P_supply = f_esc · (KE/(V−φ)) · (V−φ)/V ≈ 0.73`
   at the reference. Ion-thruster-class conversion, nearly flat in V.
2. Impulse economy `F/P ≈ 0.2 µN/W ∝ 1/√V`, ~200× below gridded ion.

Both are true simultaneously because the exhaust is electrons: very good
energy-to-jet conversion at tiny momentum per watt. This pair is the centre of
the thesis claim. The second number is why the device only owns the nN
regime; the first is why it deserves to.

## 7. Mission coupling: the throttle strategy

From the committed orbit sweeps (the mission body: the slender Ø10 × 30 mm
can, 3.1 g, flown axial; near-equatorial, ISS and sun-synchronous orbits;
real F10.7/Ap; ranges span the three orbit families):

| altitude | drag mean, 2024 (solar max) | drag max, 2024 | drag mean, 2019 (solar min) |
|---|---|---|---|
| 400 km | 38–42 nN | 119–128 nN | 3.8–4.8 nN |
| 500 km | 8.6–9.8 nN | 34–37 nN | 0.49–0.59 nN |
| 550 km | 4.3–5.0 nN | 18–21 nN | 0.21–0.24 nN |
| 600 km | 2.3–2.6 nN | 10–12 nN | 0.10–0.11 nN |
| 650 km | 1.2–1.4 nN | 6–7 nN | 0.05–0.06 nN |
| 700 km | 0.66–0.77 nN | 4.0–4.4 nN | 0.03–0.04 nN |

Demand swings ~10× over an orbit (diurnal), ~50× across 400–700 km, and
15–25× between solar maximum and minimum; inclination moves it ~10 %. The
squat Ø10 × 5 mm body of the earlier equatorial 2024 sweep has ~29 % less
drag (no long side wall): 32.9 / 7.6 / 3.8 / 2.0 nN mean at 400 / 500 /
550 / 600 km (`model/results/MISSION_SUMMARY.md`).

The throttle principle, the analytical lower bound. The concept argument
uses the ideal law only: at fixed thrust,

```
P [mW] = F [nN] · √(V [V]) / c_eff        c_eff = c_F·√κ = 2.93
```

so the minimum-power throttle uses the largest feasible escaped current
and the lowest acceleration voltage that satisfies the thrust command.
The feasible current is bounded by the emitter, ambient return-current
availability, acceptable spacecraft potential, and successful beam escape.
The concept acknowledges these bounds without optimizing against them. The
law is validated to 4–6 % against the three gated frontier anchors
(`model/mission_model.py --closed-form`, `model/results/CLOSED_FORM.md`); the
residual is the charging tax `V/(V−φ)` = 1.06–1.14, supplied by the §4
collection law when a tighter number is wanted.

Off-design losses are geometry-specific and belong to future work.
Fixed-thrust runs of the can at low voltage measured power up to
~1.5–2× the ideal bound. The excess decomposes into (i) a non-optimal
voltage for the demanded thrust and (ii) real losses: beam interception as
low-voltage optics diverge the plume against the aperture, the 0.81 energy
fraction, emission-type overheads. The interception is a can phenomenon,
not generic gun optics: `emitter.voltage_bracket` C ran the same 92.4 V
command in the isolated-gun geometry and transmitted 0.9999. The full
fixed-thrust slice (pre-registration, three gated stages, and the
controller design built on it) lives in `future_work/` (`UCURVE_PLAN.md`,
`ucurve_pic_stages/`, and the controller distillation in
`future_work/README.md`).

Two slices of the (V, I) plane, not to be confused:

1. Fixed thrust, varying V (the `future_work/ucurve_pic_stages/`
   stages): perveance I/I_CL explodes at low V. This is where the
   geometry-specific taxes live.
2. Fixed I/I_CL = 1.46, varying V (this repo's frontier stages): the
   perveance-preserving path. Beam optics stay self-similar, escape should
   stay high at all three points, and thrust varies as ~V² along it. It
   measures the envelope boundary; the fixed-thrust slice measures the
   cost inside it.

The feasibility floor is the emission ceiling by day (demand-side) and the
collection stiffness by night (supply-side), measured at the frontier's
ends by `capstone.low_power` and `capstone.high_thrust` respectively.

### 7b. Controller design, deferred to future work

Closed-loop throttle control for a selected cathode and geometry (escaped-
current estimation, thrust loop, power minimization, guards) is deliberately
excluded from the concept argument; see the scope decision and the
controller distillation in `future_work/README.md`. The
concept paper carries only the
throttle principle above and its measured 4–7 % closure.

One sentence for the paper: a propellantless thruster whose power budget
is an analytical lower bound with measured 4–7 % closure.

## 8. Plasma scaling: what one plasma row does and does not cover

Every capstone operating-point stage (100 / 200 / 300 V) runs at the same
fixed plasma row, inherited ladder-wide from the collector steps:

```
n0 = 1.627e12 m^-3    Te = 1318.8 K (113.6 meV)    Ti = 936.2 K
```

A dense, dayside-like 400 km value. The 2024 orbit sweep spans
n_e = 3·10¹⁰ – 3.4·10¹² m⁻³ and Te = 845 – 3500 K, a factor ~100 in density
that the PIC evidence does not yet cover. The split for the paper:

Plasma-independent (transfers to any row where φ ≪ V):

- The thrust law `F ∝ I·√(V − φ)` and the emission ceiling `I_CL ∝ V^1.5`
  are gun physics: beam acceleration and space charge inside the can. The
  ambient plasma enters only through φ.
- At the measured row, φ/V = 17/200 ≈ 0.08: the entire voltage frontier of
  §2 (the `P ∝ F·√V` law, the F/P column) carries a ≲ 10 % plasma correction.

Plasma-dependent (does not transfer):

- The plasma enters the operating point through one dimensionless ratio,
  `I_esc/(β·I_the)` with `I_the ∝ A·n_e·√Te`, which sets the float via §4.
  The float stiffness goes as `1/(n_e·√Te)`: at the night minimum
  (n_e ≈ 30× below the measured row) the same beam current pushes φ tens of
  volts higher. That is a tax on the drive, not a limit: no float value is a
  design limit, and the 50 V figure in the early gates was a placeholder
  chosen before the first run. But above ~100 V no committed run has found
  an equilibrium, and the φ-correction to thrust stops being small. The collection-limited night
  corner is a qualitatively different regime, and nothing in the ladder has
  measured it.

Numerical couplings (why night runs are safe but slow):

- Grid: `λ_D ∝ √(Te/n)` = 1.965 mm at the measured row, and dx = 0.15 mm was
  sized for it. Thinner plasma means longer λ_D, which is easier to resolve;
  the committed row is near the densest the grid was designed for.
- Time: the settle time of §5 grows as `1/n_e`. A night-density run needs a
  proportionally longer t_end before its plateau means equilibrium, and the
  settle check must be applied before trusting any gate.

The missing measurement: the three-point frontier of §2 measures the
voltage scaling at fixed dense plasma. A run at a night-row density
(voltage fixed) would measure the plasma scaling, the collection-limited
corner where the concept is most stressed.

Status (2026-08-12): executed and settled. The pre-registered run
(per-α predictions committed 2026-08-06: α = 1 → 53.4 V, 0.893 → 60.9 V,
0.82 → 68.0 V, 0.5 → 160.4 V) was first cut as a gross-breakdown detector
of limited value, then relaunched 2026-08-08 and continued to 2.4 µs, the
campaign's first settled float. Verdict: φ = 42.5 V settled; α = 0.5
refuted independently on the density axis; every fixed α ≤ 1 overshoots
(secant α_eff = 1.26, i.e. the fitted law is conservative along
density); the float is a 21 % tax on the 200 V drive. Full record and plan details:
`pic_sims/characterization/thin_plasma/README.md`.

## 8b. Geometry scaling, measured (2026-08-06)

Drag charges for the ram silhouette; collection and any body-mounted
power supply buy the total skin. The two are different areas, so body shape
is a free design lever, if the collection law survives the shape change.
Theory says it might not: OML gives α = 1 for a sphere and α = 0.5 for a
long cylinder, and the squat can's fitted 0.82–0.89 sits between the limits,
so a slender body should slide toward the cylinder value and pay a hidden
charging tax.

Pre-registered (`pic_sims/characterization/slender_body/README.md`, plan section) and then measured, at
identical drive, commanded current, plasma row, grid and seed:

| hypothesis | predicted φ | measured |
|---|---|---|
| **A — area-only** (fitted α holds; demand drops 3.48×) | 4–5 V | **4.38 V** |
| B — cylinder-limit lateral (α → 0.5 on the wall) | tens of V | refuted ~10× |

The skin grows 3.17 → 11.0 cm², a 3.48× change. (The pre-registration wrote
3.24×, an arithmetic slip; its bracket, 4.14–4.66 V, was computed with it.)
With the correct ratio the area arithmetic gives 4.30 V at α = 0.893 and
3.79 V at α = 0.82: the measurement sits 0.08 V (2 %) above the area-only
point, and still ~10× below hypothesis B. Collection grows slightly slower
than skin area. Fitting the collection prefactor to both slender runs at the
shared α gives an effective area 3.14× the squat can's (3.4× from the 200 V
pair, 3.0× from the 350 V pair), against 3.48× geometric; `model/mission_model.py`
uses that measured value for slender mission cases. The fitted exponent
survives a 3.48× skin-area change and an aspect-ratio change from L/r = 0.6 to 6.

The scaling rule that follows: at fixed demand, φ falls as skin area rises,
as `(1+χ) ∝ A^(−1/α)`. The 3.48× area bought a 3.8× measured drop in
enhancement demand (the law at α = 0.893 gives 4.0×).
And because `KE = κ(V − φ)`, a lower float returns thrust: 13.65 → 14.22 nN
at the same current and the same drag bill. Growing the collector is a thrust
bonus, not a penalty. This is why the concept scales along the rod, not into
the cube.

Confirmed at the 350 V drive (2026-08-17): the slender body at
0.793 mA (`characterization.350V_400km_slender`) floated at 14.00 V
tail-averaged, in the middle of the 11–17 V band the geometry law
predicts when composed with the voltage frontier, against the squat can's
48.29 V at identical drive. Thrust returned as predicted too: 43.33 nN vs
the squat's 40.48 nN (+7 %, the `KE = κ(V−φ)` bonus). With all four
corners of the voltage × geometry factorial measured (200/350 V ×
L/r 1.1/6), the two laws compose into a validated 2D operating map.

Still extrapolation: L/r beyond 6, where the cylinder limit must eventually
bite, and radii approaching λ_D, which converge on bare-tether collection
(Sanmartín 1993).

## 8c. Scale invariance: the corridor carries to CubeSats

The measured bodies are Ø10 mm, and the mission body is the 3.1 g slender
can. Neither is a CubeSat, so what decides whether the result carries to one
is whether the feasibility condition contains a size.

It does not. The argument is two lines of area bookkeeping.

1. Demand is areal. Drag goes as the drag area `S_ref`: the ram face plus
   free-molecular friction on the walls parallel to the flow
   (`S_ref = A_ram + (C_d,side/C_d)·A_parallel`, C_d,side/C_d ≈ 0.031 at
   500 km; the orbit sims' bookkeeping). Holding altitude needs
   `F = F_drag`, so `I = F/(c_F·√KE) ∝ S_ref` and `P = I·V ∝ S_ref`. Power
   per unit drag area is a function of altitude and drive voltage only.
2. Supply is areal. Any body-mounted power source scales with the skin
   `A_skin`; body-mounted solar cells are the worked example here, and power
   available per unit skin area is a property of the source, not the size.

Divide: the closure margin is `(supply/m² · A_skin) / (demand/m² · S_ref)`.
Size cancels, and what remains is the shape ratio `A_skin/S_ref` and the
altitude. Station-keeping thrust equals drag regardless of mass, so vehicle
mass never enters either. The wall term is small on the squat can (+7 %) but
not on long end-on bodies (+37 % at L/r = 6); the ram face alone would
understate a 3U's demand by ~29 %.

Computed from the committed mission CSVs near solar maximum (2024,
`model/scale_analysis.py`, `model/results/SCALE_ANALYSIS.md`):

| power demand per m² of S_ref | 400 km | 500 km | 550 km | 600 km |
|---|---|---|---|---|
| at 100 V | 1367 W | 315 W | 160 W | 83 W |

| body | skin/S_ref | 500 km | 550 km | 600 km |
|---|---|---|---|---|
| Ø10 mm can, squat (measured) | 3.8 | 0.4× | 0.8× | 1.5× |
| 1U cube, face-on | 5.3 | 0.6× | 1.1× | 2.2× |
| **Ø10 mm can, slender (measured)** | **10.2** | **1.1×** | **2.2×** | **4.2×** |
| **3U CubeSat, end-on (10×10×30 cm)** | **10.2** | **1.1×** | **2.2×** | **4.2×** |
| 6U CubeSat, end-on (10×20×30 cm) | 8.6 | 0.9× | 1.8× | 3.5× |
| 12U CubeSat, end-on (20×20×30 cm) | 6.7 | 0.7× | 1.4× | 2.8× |

The slender can and the 3U CubeSat return the same margins (computed against
the example solar supply). The 400 km demand near solar maximum exceeds the
example supply at every size. In absolute terms a 3U end-on needs
11 mA / 1.1 W at 600 km, 22 mA / 2.2 W at 550 km and 43 mA / 4.3 W at
500 km near solar maximum. Near solar minimum (2019) drag is 15–25× lower:
scaled from the slender mission cases (a Ø10 cm × 30 cm cylinder is the
slender can ×10, so ×100 in every area and power), a 3U-size body needs
~0.2 W at 500 km, ~80 mW at 550 km, ~40 mW at 600 km and ~13 mW at 700 km.

Mass is the one quantity that is not scale-free. It never enters the demand;
it sets how fast a craft sinks while thrust falls short of drag
(`da/dt = 2aF/(mv)`). At 3U density (1.33 g/cm³) the ballistic coefficient
grows with size: at 500 km the 3.1 g slender can sinks ~0.5 km/day with the
thruster off, a 4 kg 3U ~50 m/day. The free-fall runs make the same point
(`model/results/ALTITUDE_HOLD.md`): near solar maximum the slender can
re-enters from 500 km in 179–204 days, while a 4 kg 3U-size cylinder loses
36–44 km in five years.

Two things get easier with size:

1. The enhancement demanded over bare thermal collection falls as skin
   grows. A 3U needs 5.6× the thermal flux at 600 km where the Ø10 mm anchor
   needs 15×, and the anchor frontier runs at χ ≈ 150–320. Since bare
   thermal collection is the step validated to ±1 % and the enhancement
   exponent is the fitted quantity, larger bodies depend on less
   extrapolation, not more.
2. Lower χ means a lower float, which by `KE = κ(V−φ)` returns drive energy
   to the beam.

The regime caveat. Every committed run is at `r/λ_D ≈ 2.5`. CubeSat radii
are 25–60 λ_D, where OML does not apply: the sheath is thin and grows with φ,
so enhancement is an area ratio `(r_s/r)²` with `r_s − r ~ λ_D(2χ)^{3/4}`.
That model, an estimate and not a calibration, puts a 3U at ~16 V (600 km),
~32 V (550 km), ~59 V (500 km) near solar maximum: a 16–59 % tax on a 100 V
drive, so the minimum-power voltage moves up at 500 km, and with that tax
the 500 km margin above falls below one (~0.7×). 550–600 km close with it.
The areal power balance above does not depend on this; only the floats do.

## 9. From scaling laws to a model: the plan, and what buys confidence

These sections are algebra applied by hand. Once the two frontier runs land,
the plan is a minimal executable model, one file on the order of a few
hundred lines, that:

1. derives every law constant from all committed `metrics.json` files (by
   then three points, not one), with the fit residuals printed, not hidden;
2. sweeps any orbit CSV to make mission-level statements (duty cycle,
   feasibility fraction, closure vs altitude) and the paper figures;
3. flags every row that falls outside the measured envelope (density,
   χ, or perveance beyond what any committed run has measured) and splits
   every mission claim into "measured-envelope rows" and "extrapolated rows,
   needing a targeted PIC run". This is the guard against the hardcoding
   trap: a new orbit (inclination, local-time coverage, solar cycle, not
   just altitude) changes which rows land in which bucket, never the laws
   themselves, and the flagged bucket says exactly where the next GPU-hours
   go;
4. evaluates optimization rules per row (e.g. the §7 minimum-power
   voltage for the instantaneous demand), never as frozen numbers: fitted
   constants stay home, physics forms travel;
5. never feeds an acceptance gate. PIC stages stay self-contained, and
   the model remains a targeting/analysis tool with no authority over
   evidence.

No promotion machinery, no calibration registry: with this few points the
provenance is the anchor table below.

What buys model confidence is placement, not count:

- Overdetermination tests the law form. One anchor point fits constants
  and can test nothing. Three voltage points overdetermine them for the
  first time: `k` must fit all three at once, and the float must follow the
  `(1+χ)` line at χ ≈ 50 / 150 / 270 simultaneously. Every point past the
  first is a falsification opportunity.
- Points along one axis only test that axis. The three frontier points
  will make the voltage laws solid and say nothing about the plasma laws
  (§8). A fourth voltage point adds almost nothing; the first night-density
  point adds a tested dimension.
- Confidence extends over the measured envelope, not beyond it. Inside
  the span of measured points the model interpolates; outside it
  extrapolates, whatever the point count. The mission spans ~100× in
  density; the measured envelope spans 1×.
- Numerical confidence is a separate budget. Same point, different
  seed/grid/PPC: currently zero measured everywhere in the ladder
  (disclosed caveat). One repeat run bounds it.

Priority order per GPU-hour:

1. voltage frontier (complete 2026-08-05)
2. convergence repeat at the 200 V anchor
3. minimal model
4. night-density point, only if the model predicts a thin night margin

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
