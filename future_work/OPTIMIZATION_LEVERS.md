# Optimization levers: the measured gap to the ideal bound, and what each recovery costs

The committed frontier runs at 1.19–1.22× the parameter-free bound
`P = F·√V / √(2·m_e/e)` (paper §5). This file is the ledger of that gap and
of the envelope levers beyond it. For each lever: the mechanism, the measured
tax, the maximum recovery, how to optimize it, what a PIC measurement costs,
and whether the recovery is even measurable against the ±4–7 %
grid-resolution error band.

Reference point (200 V anchor, 13.65 nN): ideal bound 57 mW, measured
68.4 mW.

## Summary

| # | lever | measured tax | max recovery | measurable vs ±4–7 % grid band? | campaign cost | priority |
|---|---|---|---|---|---|---|
| 1 | emission ceiling `I_max ∝ V^1.5/d²` | envelope, not a tax | **~40 % power** (V_min ↓), reopens 400–500 km | yes (order-1 effect) | 3–5 runs × ~8 GPU-h | **highest — moves mission verdicts** |
| 2 | energy fraction κ = 0.81 (launch artifact) | ~10 % | ~10 % | correction, not a lever — matched A/B | 2 runs (`CATHODE_LAUNCH_PLAN.md`) | medium |
| 3 | float tax V/(V−φ) = 1.06–1.14 | 6–14 % | 6–14 % | already measured (slender run) | 0 (done) | design trade, no new runs |
| 4 | plume divergence c_F = 0.97·c_ideal | ~3 % | ~3 % | **no — below the noise band** | — | lowest as power lever |
| 5 | off-design escape (low-V interception) | 1.5–2× off-optimum only | avoids, not recovers | yes | baseline exists (`ucurve_pic_stages/`) | folded into #1/#2 |

## 1. Emission ceiling: the conclusion-moving lever

1. Mechanism. The gun's space-charge ceiling `I_max = 1.46·I_CL(V) ∝
   V^1.5/d²` decides which (V, F) points are reachable. The anchor body
   fails at 400 km because demand exceeds this ceiling 63 % of the time. That
   is an envelope failure, not an efficiency failure.
2. Optimization. More emitting area at the same short gap (multiple emission
   tips / a field-emitter array) raises `I` at fixed V, so `V_min` for a
   given thrust drops, and `P ∝ F·√V` falls with it. Halving the feasible
   voltage cuts fixed-thrust power ~30–40 %, double the entire
   ideal-constant recovery (#2+#4), and reopens 400–500 km.
3. Campaign. Capstone variant with N× emission area at the pinned gap (the
   `cathode_standoff` mechanism from the slender run). Pre-register the
   predicted `V_min` shift and power from the ideal model; gates: escape
   ≥ 95 %, float ≤ 50 V, current balance. 3–5 runs at ~8 GPU-h each
   (RTX 3060 scale, from the thin-plasma run's wall time).
4. Caveat. Field-emitter arrays pay gate power outside the beam ledger
   `V·I`. The campaign objective must be system power, not beam power. A run
   that halves `V·I` while adding comparable gate overhead optimized the
   wrong ledger. See the cathode-selection item in [`README.md`](README.md).

## 2. Energy fraction κ = 0.81: a launch-plane artifact, not a gun lever

1. Mechanism (corrected 2026-09-23; this entry first read it as
   space-charge depression). The simulated beam is launched 2 cells (0.3 mm)
   above the cathode (`capstone/2_chipsat_thruster/helpers.py`, `z_emit`),
   where a vacuum field solve puts the potential 19 % of V above the
   cathode; electrons miss that part of the drop and exit with 81 % of
   `e(V−φ)`. The deficit is 17–18 % of V in every committed run at
   I/I_CL = 1.46, independent of φ, density and field, and it shrinks at
   higher loading (11.6 % in the U-curve floor run), the opposite of a
   space-charge depression. Thrust ∝ √KE, so the power tax is `1/√κ ≈ 1.10`.
2. Optimization. None needed at the gun: a real cathode emits at cathode
   potential and gives κ ≈ 1. The ~10 % power (~13 % in the mission model)
   is a simulation correction, not a design change.
3. Campaign. The matched pair in [`CATHODE_LAUNCH_PLAN.md`](CATHODE_LAUNCH_PLAN.md):
   the capstone deck with today's launch vs an energy-corrected launch,
   same grid, seed, dt and window, so systematics cancel.

## 3. Float tax V/(V−φ): not a gun property

1. Mechanism. The body floats at +φ; the beam gains `e(V−φ)` while the
   supply pays `eV`. φ is set by the collection side (skin area, ambient
   density), not by emitter design.
2. Optimization. More collecting skin. Already measured: the slender run
   (3.48× skin) dropped φ from 16.98 to 4.38 V at identical drive and raised
   thrust to 14.22 nN. No new campaign needed. This is a design-level trade
   of bare collector vs solar-cell area (clad dielectric does not collect).

## 4. Plume divergence c_F = 0.97·c_ideal: real but unmeasurable

1. Mechanism. Off-axis momentum produces no thrust; the measured thrust
   slope is 97 % of `√(2·m_e/e)`.
2. Optimization. Collimation: multi-tip emitters spreading the current so
   the plume leaves nearly parallel, aperture shaping.
3. Why it is last as a power lever. The full recovery is ~3 %, below the
   ±4–7 % grid-resolution uncertainty, so a PIC campaign cannot distinguish
   "fixed it" from numerical noise at committed resolutions. Its real value
   is indirect: better collimation improves escape at low voltage (lever
   #5), which is measurable.

## 5. Off-design escape collapse: avoid rather than recover

1. Mechanism. At low V / high perveance the beam self-scrapes inside the can
   (escape 93.8/80.0/57.4 % at 125/92.4/78 V, the
   [`ucurve_pic_stages/`](ucurve_pic_stages/) baseline). Off-optimum
   operation costs 1.5–2× the bound.
2. Optimization. The throttle principle already avoids these points (they
   all command 2.7–10× over the emission ceiling). Raising the ceiling (#1)
   and improving optics (#2, #4) widen the safe envelope; the moved stages
   are the before-data any such claim gets compared against.

## Campaign rules (all levers)

1. Same evidence contract as the main campaign: frozen configs, hashes,
   pre-registered predictions, versioned gates.
2. The ideal model is the pre-registration engine: every design change gets
   a predicted recovery from `model/mission_model.py --closed-form` before the run;
   the PIC result gates it.
3. Few-percent effects only via matched A/B pairs (same grid/seed/window).
4. The objective function is system power (beam + gate + converter), never
   beam power alone.
5. Success is moving a mission verdict (400 km reopens, 500 km closes on
   power), not shaving percent off a point that already closes. The concept
   paper's conclusions hold to ±20 %, so only envelope changes are worth
   GPU-hours.
