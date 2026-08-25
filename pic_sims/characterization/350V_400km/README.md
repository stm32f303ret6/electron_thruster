# characterization.350V_400km: the 400 km-enabling drive

Same system as `floating_body`, driven at 350 V / 0.793 mA. The questions:
does the measured envelope extend past 300 V to the drive the 400 km orbit
demands, and does the body still float benignly there?

Status: run committed 2026-08-17, PASS on all 7 required gates (see results
below; the plan text is preserved unchanged above them).

## Why this stage exists

The model's 400 km axial row demands V_min = 304 V, just above the tested
300 V ceiling (`model/MODEL.md` §4). Every committed run below 350 V leaves
the 400 km row an extrapolation. One voltage step turns it into an
interpolation, or refutes it.

## Setup

| | floating_body | high_thrust | this stage |
|---|---|---|---|
| `cathode_offset` | −200 V | −300 V | **−350 V** |
| `i_beam` | 0.342 mA | 0.63 mA | **0.793 mA** |
| `max_steps` | 160k | 200k | **220k** (CFL dt ~3.86 ps) |
| everything else | — | — | identical |

$$I_{CL}(350\,\text{V}) = 0.543\ \text{mA}, \quad I / I_{CL} = 1.46 \;\Rightarrow\; i_\text{beam} = 0.793\ \text{mA}$$

## Pre-registered predictions (from the committed laws, before the run)

1. Thrust. The frontier scales as F ∝ V² at fixed I/I_CL (measured:
   13.65 nN at 200 V → 30.13 nN at 300 V). Prediction: F ≈ 40.5 nN,
   covering the 400 km axial mean drag (32.9 nN) at ~81 % duty.
2. Float. The fitted collection law `I = βA·j_the·(1+χ)^α`
   (α = 0.8931, βA = 2.51 cm²) extended from the 300 V point
   (φ = 36.3 V at 0.63 mA) predicts φ ≈ 47 V at 0.793 mA escaped, inside
   the 50 V benign design limit but with < 3 V of margin. This is the
   question. A float past 50 V means the 400 km-enabling drive carries a
   charging tax beyond the design limit, and the `body_floats_benign` gate
   records that as a FAIL.
3. Escape. Voltage-independence of transmission is measured to 0.006 pp
   (`emitter.voltage_bracket`); escape should stay ≥ 95 % (anchor: 98.4 %,
   300 V: 99.0 %).

Either outcome of (2) is a result. Benign: the tested envelope covers the
400 km mean demand. Breached: 400 km costs a measured charging tax and the
slender-geometry path (`paper/SCALING_LAWS.md` §8b) becomes the 400 km
route, already pre-registered as `../350V_400km_slender/`.

## What this stage does not claim

- It does not close 400 km as a mission: drag maxima (92.4 nN) exceed any
  single operating point, night-side rows stay extrapolated, ~150–200 mW
  mean demand is mission design, and the lateral-pose thrust-axis question
  is untouched.
- It moves one axis (drive voltage) off the anchor, per the hub contract.
  Slender-body-at-350 V is two axes and lives in its own pre-registered
  spoke, `../350V_400km_slender/`, the fourth corner of the 2×2
  voltage × geometry factorial this run's voltage leg completes. This run
  goes first.

## Results

Reference run `20260817T055536Z_acf6cf7b` (207,280 steps, 800 ns,
~7.7 GPU-h). PASS on all 7 required gates under
`characterization.350V_400km.v1`:

| check | measured | pre-registered | target | status |
|---|---|---|---|---|
| escape fraction | 99.11 % | ≥ 95 (anchor 98.4, 300 V 99.0) | ≥ 95 % | PASS |
| body float φ (tail mean) | **48.29 V** | 47 V | ≤ 50 V | PASS |
| beam thrust | **40.48 nN** | 40.5 nN | ≥ 32.9 nN (reported) | PASS |
| current balance | 3.2 % | — | ≤ 5 % | PASS |
| net-force sanity | 0.011 | — | ≤ 1 | PASS |
| edge potential | 0.15 V | — | ≤ 1 V | PASS |
| ledger vs dumps (both) | ~1.6e-10 | — | ≤ 2 % | PASS |

Both committed laws held one step past the tested ceiling: thrust landed
0.15 % off the two-constant law, the float 1.3 V off the collection-law
prediction. The model's 400 km axial row (V_min = 304 V) is now an
interpolation inside the measured 100–350 V envelope, and the mean-drag
gate passed (40.48 ≥ 32.9 nN, ~81 % duty).

Settle caveat: φ at run end is 51.14 V and still rising at +33.8 mV/ns;
the gated value is the 160 ns tail mean. The settled float extrapolates
past the 50 V design limit, so the squat can sits on the benign limit at
this drive, not inside it. Whether the mission-relevant body has real
margin here is exactly the sibling spoke's question
(`../350V_400km_slender/`, predicted φ ≈ 11–17 V).

Exhaust KE tail 237–239 eV vs 240.7 eV predicted at the injection plane
(the κ energy factor, consistent with the ladder). Evidence snapshot:
`reference_results/20260817T055536Z_acf6cf7b/`.

## How the PIC works

Same engine as `floating_body`: deck, charge pump, reservoir, observer
identical (files copied verbatim from `high_thrust/`, which is itself the
anchor engine at a different drive). Only the drive point differs.

## Commands

```bash
python simulation.py                    # ~8-9 h on the campaign GPU
python analyze.py --run outputs/<run-id> --policy acceptance.yaml
```

## Limitations

- reduced ion mass (400 mₑ), electrostatic only, single grid/PPC/seed,
  finite-time equilibrium: the ladder-wide caveats, unchanged.
