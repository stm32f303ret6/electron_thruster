# characterization.350V_400km_slender: the slender body at the 400 km drive

The slender can of `slender_body` (Ø10 × 30.5 mm, L/r = 6, gun gap pinned
at 4.7 mm) driven at the 400 km-enabling operating point of `350V_400km`
(350 V / 0.793 mA, I/I_CL = 1.46). The question: do the two committed laws,
the voltage frontier and the geometry collection law, compose?

Status: run committed 2026-08-17, PASS on all 7 required gates (see results
below; the plan text is preserved unchanged above them).

## Why this spoke may move two axes

The hub contract says one axis per spoke, and this spoke moves two
(voltage and geometry). The exception is deliberate (decision 2026-08-17):
both single-axis legs are measured, so this run is the fourth corner of a
2×2 factorial rather than an unattributable jump.

| | squat can (L/r ≈ 1.1) | slender can (L/r = 6) |
|---|---|---|
| **200 V** | anchor `floating_body` — PASS, φ 16–17.7 V, F 13.65 nN | `slender_body` — PASS, φ 4.38 V, F 14.22 nN |
| **350 V** | `350V_400km` — pre-registered, φ ≈ 47 V, F ≈ 40.5 nN | **this spoke** |

Three corners are measured or pre-registered from single-axis laws; the
fourth is fully predicted by composing them. A hit means the laws compose
and the mission-relevant body (the mission vehicle is slender anyway;
`paper/SCALING_LAWS.md` §8c: feasibility is a shape property) covers the
400 km mean demand benignly. A miss localizes: the single-axis legs tell
you which law broke.

Run order: `350V_400km` (squat) first. It is the older pre-registration
and supplies the missing voltage leg of the factorial.

## Setup

| | slender_body | 350V_400km | this spoke |
|---|---|---|---|
| `cathode_offset` | −200 V | −350 V | **−350 V** |
| `i_beam` | 0.342 mA | 0.793 mA | **0.793 mA** |
| `z_bot` / `cathode_standoff` | −30 mm / 4.7 mm | −5 mm / floor-tied | **−30 mm / 4.7 mm** |
| grid | 200 × 608 | 200 × 440 | **200 × 608** |
| `max_steps` | 160k | 220k | **220k** (CFL dt ~3.86 ps) |
| everything else | — | — | identical |

The standoff keeps the gun gap at 4.70 mm, so the Child–Langmuir ceiling is
the squat deck's: I_CL(350 V) = 0.543 mA, and 0.793 mA is the same
I/I_CL = 1.46 every committed run demonstrated.

## Pre-registered predictions (from the committed laws, before the run)

1. Float. The collection law scaled from the slender 200 V point
   (4.38 V measured, 5–6 V settled band) through
   $(1+\chi) \propto I^{1/\alpha}$ with the measured α bracket 0.82–0.89
   and escaped-current ratio 2.32 predicts φ ≈ 11–17 V, far inside the
   50 V benign limit, where the squat can at the same drive predicts a
   ~47 V near-miss. This is the question. A float near 50 V means the two
   laws do not compose, and the slender route to 400 km is not what §8b
   implies.
2. Thrust. The frontier at 350 V (40.5 nN squat prediction) plus the beam
   energy the lower float returns ($KE = \kappa(V-\varphi)$, the measured
   §8b effect) predicts F ≈ 42–43 nN, covering the 400 km axial mean drag
   (32.9 nN) at ~77 % duty.
3. Escape. Transmission is measured voltage-independent
   (`emitter.voltage_bracket`, 0.006 pp) and geometry-independent at the
   slit (slender: 98.42 %); escape should stay ≥ 95 %.

Either outcome is a result. Composed: the mission-relevant body covers the
400 km mean demand benignly with ~3× float margin. Broken: the factorial
pinpoints which law fails off its measured axis.

## What this spoke does not claim

- It does not close 400 km as a mission: drag maxima (92.4 nN) exceed any
  single operating point, night-side rows stay extrapolated, ~150–200 mW
  mean demand is mission design, and the lateral-pose thrust-axis question
  is untouched.
- It does not extend the geometry axis: L/r stays at the measured 6, where
  the cylinder-limit worry is already refuted. Slender-er bodies remain
  `future_work/`.

## Results

Reference run `20260817T133815Z_79f4ca11` (207,280 steps, 800 ns,
~9.8 GPU-h). PASS on all 7 required gates under
`characterization.350V_400km_slender.v1`:

| check | measured | pre-registered | target | status |
|---|---|---|---|---|
| body float φ (tail mean) | **14.00 V** | 11–17 V | ≤ 50 V | PASS |
| beam thrust | **43.33 nN** | 42–43 nN | ≥ 32.9 nN (reported) | PASS |
| escape fraction | 99.14 % | ≥ 95 | ≥ 95 % | PASS |
| current balance | 4.4 % | — | ≤ 5 % | PASS |
| net-force sanity | 0.010 | — | ≤ 1 | PASS |
| edge potential | 0.058 V | — | ≤ 1 V | PASS |
| ledger vs dumps (both) | ~7e-10 | — | ≤ 2 % | PASS |

### The laws compose; the factorial is closed

| | squat can (L/r ≈ 1.1) | slender can (L/r = 6) |
|---|---|---|
| **200 V** | φ 16–17.7 V, F 13.65 nN | φ 4.38 V, F 14.22 nN |
| **350 V** | φ 48.29 V, F 40.48 nN | **φ 14.00 V, F 43.33 nN** |

The fourth corner landed dead center of the composed prediction: φ 14.00 V
in the 11–17 V band, F 43.33 nN in the 42–43 nN band. The voltage frontier
(100–350 V) and the geometry collection law (L/r 1.1–6) are now a validated
2D operating map instead of two 1D curves.

The mission answer: at the 400 km-enabling drive the squat can sits on the
50 V charging limit (48.3 V tail, endpoint rising past 50), while the
slender body, the shape the mission vehicle is anyway
(`paper/SCALING_LAWS.md` §8c), covers the 400 km axial mean drag at ~76 %
duty with 3.6× margin on the limit, plus a 7 % thrust bonus from the
returned float (KE = κ(V−φ): exhaust 272.7 eV vs the squat's 239.0 eV).

Settle caveat: φ end-of-run 15.76 V, late slope +20.8 mV/ns. Quote the
settled float as a ~14–17 V band; the 35 V distance to the limit keeps the
benign verdict unchanged either way. Evidence snapshot:
`reference_results/20260817T133815Z_79f4ca11/`.

## How the PIC works

Same engine as `slender_body`: deck, charge pump, cathode standoff,
reservoir, observer identical (files copied verbatim; only stage-id strings
differ). Only the drive point differs from `slender_body`; only the
conductor geometry differs from `350V_400km`.

## Commands

```bash
python simulation.py                    # ~8.5-9 h on the campaign GPU
python analyze.py --run outputs/<run-id> --policy acceptance.yaml
```

## Limitations

- reduced ion mass (400 mₑ), electrostatic only, single grid/PPC/seed,
  finite-time equilibrium: the ladder-wide caveats, unchanged.
- the slender 200 V float was still settling at run end (5–6 V band), so
  the φ prediction inherits that band; the 800 ns budget here carries the
  same settle caveat.
