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

Demand swings ~10× over an orbit (diurnal) and ~15× across 400–600 km. The
power-optimal flight rule follows from §2 + §3:

> **Throttle V to the lowest feasible value for the instantaneous demand.**
> Energy per unit impulse goes as √V, so continuous low-V thrust strictly
> beats duty-cycled high-V thrust for the same station-keeping impulse.
> High V is reserved for the demand peaks that need its `V²` thrust ceiling.

The feasibility floor that stops the throttle going lower is the emission
ceiling by day (demand-side) and the collection stiffness by night
(supply-side) — measured at the frontier's ends by `capstone.low_power` and
`capstone.high_thrust` respectively.

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
*voltage* scaling at fixed dense plasma; a fourth run at a night-row density
(~2·10¹¹ m⁻³ from the sweep, voltage fixed) would measure the *plasma*
scaling — the collection-limited corner where the concept is most stressed,
and the first run a reviewer will ask for. It is the natural next stage
after the two pending frontier runs.

## 9. From scaling laws to a model — the plan, and what buys confidence

These sections are algebra applied by hand. Once the two frontier runs land,
the plan is a **minimal executable model** — one file, on the order of a few
hundred lines — that:

- derives every law constant from **all committed** `metrics.json` files (by
  then three points, not one), with the fit residuals printed, not hidden;
- sweeps any orbit CSV to make mission-level statements (duty cycle,
  feasibility fraction, closure vs altitude) and the paper figures;
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

Priority order per GPU-hour: voltage frontier (running) → night-density
point → one seed/grid repeat.

---

## Anchor bookkeeping

| quantity | value | provenance |
|---|---|---|
| F, φ, escape, KE at 200 V | 13.65 nN, +16.98 V, 98.44 %, 147.5 eV | **measured** — `capstone/2_chipsat_thruster/reference_results/20260801T142601Z_2f822a95/metrics.json` |
| I/I_CL emission ratio | 1.46 | **measured** — same run vs planar CL scale |
| thermal collection | ±1 % of exact | **measured** — `collector.thermal` reference |
| 300 V row (30 nN, φ≈31 V) | pre-registered prediction | `capstone.high_thrust` (runs pending) |
| 100 V row (3.4 nN, φ≈6 V) | pre-registered prediction | `capstone.low_power` (runs pending) |

Ladder-wide caveats travel with every number: reduced ion mass (400 mₑ),
electrostatic (no B, no ram drift), single grid/PPC/seed, finite-time
equilibrium on the ion clock.
