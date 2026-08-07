# Validation ladder — summary of evidence

One page per question a reviewer would ask: **what does each step test, what
did it measure, and how close is that to theory?**  All numbers below come
from the committed, machine-readable `reference_results/` snapshots (each
carries its run ID, config hash, policy ID/hash, git commit, and WarpX
version); this file is a human-readable digest, never the authoritative
record.  Every step ran on the CPU build (WarpX 26.5, RZ electrostatic,
seed 42) and PASSed all of its required gates.

The plasma everywhere is the chipsat capstone's ionospheric row:
n₀ = 1.627·10¹² m⁻³, kTe = 113.6 meV (1318.8 K), Ti = 936.2 K, reduced ion
mass 400 mₑ (a ladder-wide caveat: not real O⁺).

---

## Emitter branch (vacuum, prescribed-current beams)

### 1. `emitter.negative_cathode` — plane diode, no embedded boundary

**The test:** a −100 V cathode plane emits a 10 µA electron beam toward a
grounded collector across a 6 mm vacuum gap.  Before the beam starts, the
potential must be the exact Laplace ramp; after, every emitted electron must
arrive with the full gap energy.

| measured | theory | agreement |
|---|---|---|
| vacuum potential vs Laplace ramp | exact linear ramp | max error **35 µV** on 100 V |
| collected / emitted current | 1 (stiff beam) | **1.0002** |
| arrival kinetic energy error | 0 (energy conservation) | **0.028 eV** on ~100 eV |
| particle budget closure | 0 % | **0.00075 %** |

### 2. `emitter.holed_anode` — beam through a holed anode plate (3 scenarios)

**The test:** the same gun fires through a grounded plate with a hole.  A
stiff low-current beam must pass nearly untouched (A); raising the current
40× makes space charge blow the spot up against the small hole (B); widening
the hole must restore transmission (C).  This is a mechanism check —
transmission responds to space charge and geometry in the right direction
and magnitude.

| scenario | collector fraction | expectation |
|---|---|---|
| A: 10 µA, r_hole 0.7 mm | **0.973** | ≥ 0.95 (only the thermal tail clips) |
| B: 400 µA, r_hole 0.7 mm | **0.900** | space-charge drop vs A (measured −7.3 pts) |
| C: 400 µA, r_hole 1.4 mm | **1.000** | big hole restores transmission (anode hits ~10⁻⁶) |

Arrival-energy error ≤ 0.025 eV in all three.  (Planar Child–Langmuir is
printed as a rough scale only, never gated — plan C8.)

---

## Collector branch (ambient plasma, conducting sphere)

The sphere (a = 0.75 mm, a/λ_De = 0.38, 5 cells) sits in the capstone plasma
maintained by one-sided Maxwellian flux injection; dx = 0.15 mm and
ppc = 16 are the capstone's own numbers, so these gates validate the
capstone's configuration, not just the code.

### 3. `collector.thermal` — sphere at 0 V: the exact answer

**The test:** an absorber at plasma potential creates no field, so the
collected current of each species is the closed-form one-sided thermal flux
I_th = n₀·e·⟨v⟩/4 · 4πa² — exact for any convex probe, no sheath model, no
free parameter.

| measured | theory | agreement |
|---|---|---|
| electron current | I_th_e = 0.10393 µA | **0.9921** of exact (−0.8 %) |
| ion current | I_th_i = 4.379 nA | **1.0096** of exact (+1.0 %) |
| I_e/I_i ratio | √((mi/me)(Te/Ti)) = 23.74 | **0.983** of theory (−1.7 %) |
| far-shell density | n₀ | **0.997** |
| far-shell quasineutrality | 0 | **0.005** |

### 4. `collector.biased_3v` — OML ceiling at χ = eV/kTe = 26.4

**The test:** at +3 V the small-sphere Orbit-Motion-Limited ceiling is
I_OML = I_th·(1+χ) = 2.847 µA.  A finite sphere collects a *fraction* of the
ceiling (an effective-potential barrier forms); the cross-code reference
(a prior OML study at this a/λ_De) measured ~93 %.

| measured | reference | agreement |
|---|---|---|
| I_e/I_OML | ∈ [0.85, 1.05]; pre-refactor GPU baseline 0.852 | **0.8526** |
| sheath radius (\|φ\| = kTe/e) | grows with bias | **4.12 mm** |

### 5. `collector.biased_10v` — sheath growth at χ = 88

**The test:** at +10 V (I_OML = 9.249 µA) the barrier deepens — the
collected fraction must *fall* below the 3 V value — and the sheath must
grow yet stay contained inside the domain.

| measured | reference | agreement |
|---|---|---|
| I_e/I_OML | ∈ [0.80, 1.05]; GPU baseline 0.8087 | **0.8090** |
| sheath radius | > 3 V value (4.12 mm) | **6.89 mm** (GPU baseline 6.88) |
| edge \|φ\| (containment) | ≤ 0.2 V | **0.003 V** |

### 6. `collector.floating` — the capstone's charge pump vs the floating potential  *(new step, closes gap G2)*

**The test:** the same sphere, but nothing prescribes its voltage: the
chipsat capstone's charge-pump mechanism (Gauss-law capacitance calibration,
per-step scraped-charge accounting dQ = e·(w_i − w_e),
`set_potential_on_eb` rewrite every step) must drive it to the **floating
potential** — the bias where electron and ion collection balance.  The
anchor brackets the two limiting ion-collection models:
thermal-ion φ_f = −0.360 V, OML-ion φ_f = −0.213 V (φ_f is independent of C,
so the gate isolates the charge accounting itself).

| measured | theory | agreement |
|---|---|---|
| floating potential (tail mean) | in [−0.40, −0.19] V | **−0.251 V** — between the models, leaning OML as expected at a/λ_De = 0.38 |
| equilibrium current balance \|I_e−I_i\|/I_i | → 0 | **0.9 %** (I_e 16.16 nA vs I_i 16.01 nA) |
| Gauss-law C / 4πε₀a | ~1.07 (grounded-box correction) | **1.068** (89.1 fF vs 83.4 fF) |
| ledger vs openPMD scraped charge | identical | **5·10⁻⁹** |

### 7. `capstone.two_node_laplace` — the capstone's two-node EB in vacuum  *(new step, closes gap G1)*

**The test:** the chipsat's conducting can carries TWO potentials on one
embedded boundary (BODY floats; CATHODE = body − 200 V).  This step solves
that exact geometry in vacuum with both nodes pinned (+16 V / −184 V)
through the same potential string and per-step rewrite the capstone uses.
With zero space charge the solve is Laplace's equation, so exact mathematics
gates it.

| measured | theory | agreement |
|---|---|---|
| cathode surface potential | −184 V assigned | error **0.0 V** |
| body surface potential | +16 V assigned | error **0.22 V** (cut cells) |
| maximum principle (vacuum φ within boundary values) | exact | violation **0.0 V** |
| vs independent sparse-direct stair-step solver | agree away from surfaces | **1.86 V** max at ≥ 20 cells (gate 4 V) |
| per-step rewrite idempotency | bit-exact | **0.0 V** |

---

## Capstone

### 8. `capstone.floating_body` — the full chipsat (emitter + collector + float)

**The test:** the complete system — the can floats via the charge pump, the
cathode rides at body − 200 V, a 0.342 mA beam exits the lid hole into the
ionospheric plasma with an infinite-reservoir recycle — reproducing the
validated float200 baseline (159,160 steps, 800 ns).  **Evidence kind:
system-integration regression** — the escape/thrust/φ anchors were read off
the validated float200 run itself (disclosed calibration, plan §9.3); the
theory-anchored gates are the current balance, the momentum bound,
containment, and the ledger-vs-dump consistency checks.

| measured | anchor / theory | agreement |
|---|---|---|
| beam escape fraction | ~98.5 % (float200) | **98.44 %** |
| thrust F_beam | 13.6 nN ± 15 % (float200) | **13.65 nN** |
| body potential φ_body | +16 ± 4 V (float200) | **+16.98 V** |
| steady current balance | = 0 (floating equilibrium identity) | **3.2 %** |
| \|F_net\|/F_beam | ≤ 1 (momentum bound) | **0.0035** |
| exhaust KE | −φ(injection plane) = 148.1 eV | **147.5 eV** |
| ledger vs dumps (ambient-e / beam-escape) | identical | **3·10⁻⁹ / 5·10⁻⁹** |

### 9. `capstone.high_thrust` — the 300 V ceiling (PASS, promoted)

**The test:** the same deck driven at the 300 V hardware ceiling with
i_beam = 0.63 mA (the same measured I/I_CL = 1.46 emission ratio).  Scaling
the float200 measurement predicted **~30 nN** — enough to cover the 500 km
worst-case drag row (28.4 nN, `orbit_sims` 2024 sweep).

`reference_results/20260804T154756Z_b854dcbe/` — 192,680 steps, **all 7
required gates PASS**.

| measured | prediction | value |
|---|---|---|
| F_beam | ~30 nN | **30.13 nN** (covers the 28.4 nN bar) |
| escape fraction | ≥ 95 % | **98.99 %** |
| φ_body | 36 V (α = 0.82) | **36.30 V** |
| exhaust KE | 211.4 eV | **210.11 eV** |
| current balance / momentum / edge φ | bounds 0.05 / 1 / 1 V | 0.0353 / 0.0100 / 0.108 V |

**This run carries the collection-law discrimination:** the pre-registered
linear (α = 1 → 31 V) and square-root (α = 0.5 → 90 V) laws are refuted;
α = 0.82 survives.  Late slope +26.8 mV/ns at run end, so the settled float
extrapolates to ~42–48 V — see `SCALING_LAWS.md` §4 VERDICT.

### 10. `capstone.low_power` — the 100 V floor (PASS, promoted)

**The test:** the same deck at the 100 V hardware floor, i_beam = 0.121 mA
(same I/I_CL = 1.46).  At fixed thrust, supply power grows as ~√V, so this
is the power-optimal end of the throttle curve.

`reference_results/20260804T230218Z_0adb478f/` — 115,480 steps, **all 7
required gates PASS**: F_beam **3.42 nN**, escape **96.12 %**,
φ_body **5.40 V** (prediction ~6 V), exhaust KE **77.19 eV** (predicted
77.10).  At low χ the candidate collection laws converge, so this point
**confirms the anchor rather than discriminating**.

With steps 8 and 9 it completes the three-point measured P–F frontier and
confirms F/P ∝ 1/√V: **0.283 / 0.200 / 0.159 µN/W** at 100 / 200 / 300 V.

### 11. Slender body — the geometry axis (PASS, promoted)

**The test:** the capstone deck with the can lengthened to Ø10 × 30.5 mm
(L/r = 6, skin 3.24×) at the anchor's identical drive, current, plasma row,
grid and seed — the only change is where the return current is collected.
Required a code change first (`geometry.cathode_standoff`, commit `a7f4106`)
so the can grows without stretching the gun gap.

`2_chipsat_thruster/reference_results/20260806T011847Z_5670e54c/` — 159,160
steps, **all 6 required gates PASS** under `capstone.exploratory_axes.v1`.

Pre-registered hypotheses (`capstone/SLENDER_BODY_PLAN.md`): area-only
scaling predicted φ ≈ 4–5 V, cylinder-limit lateral predicted tens of volts.
**Measured φ = 4.38 V — hypothesis A confirmed, B refuted by ~10×.**  The
fitted exponent survives a 3.24× area change.  Thrust *rose* to 14.22 nN
(from 13.65) because a lower float keeps more of the drive.

---

## Cross-stage checks (all green in the suite verdict)

- **Collector current-fraction trend:** 0.992 (0 V) ≥ 0.853 (3 V) ≥ 0.809
  (10 V) — the barrier deepens with χ.
- **Sheath-radius ordering:** 4.12 mm (3 V) ≤ 6.89 mm (10 V).
- **Shared plasma:** all collector steps hash-match plasma/ppc/probe radius.
- **Emitter transmission consistency:** no-plate 1.000 vs holed-A 0.973.
- **Capstone inherits the validated configuration:** frozen plasma/dx/ppc
  hash-match `collector.thermal`'s.
- **Floating step shares thermal's configuration** (new).
- **Two-node step solves the capstone's exact geometry/dx/offset** (new).

## What this ladder does NOT yet establish

Kept visible on purpose (details: `ARCHITECTURE_REFACTOR_PLAN.md` §13,
`capstone/2_chipsat_thruster/VALIDATION_GAPS.md`):

- **Convergence** (C12): every number above is one grid, one ppc, one domain,
  one seed.
- **Stationarity** (C6): steady means are windowed averages without a formal
  stationarity test; the capstone's 800 ns plateau is a finite-time
  equilibrium on the ion clock (late dφ/dt is reported honestly).
- **Beam + plasma coexistence** (G6) first appears at the capstone; no
  cheaper step can close it.
- The **reduced ion mass** (400 mₑ) is internally consistent everywhere but
  makes every real-O⁺ conclusion an extrapolation.
- The capstone's escape/thrust/φ_body gates are **regression anchors**, not
  independent theory.
