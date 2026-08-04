# capstone.high_thrust — the thruster at the 300 V hardware ceiling

The same physical system as [`capstone.floating_body`](../2_chipsat_thruster/README.md)
— identical can geometry, plasma row, grid, reservoir, and floating-body
charge pump — driven at the **300 V hardware ceiling** with the beam current
scaled to the same emission-ceiling ratio the validated run demonstrated:

```
I_CL(300 V, 4.7 mm gap, 0.5 mm spot) = 0.431 mA
I / I_CL = 1.46 (the measured float200 ratio)   ->   i_beam = 0.63 mA
```

## The question

**How much thrust does the thruster produce at full drive, and does the body
still float benignly?** The `orbit_sims` altitude sweep (2024, real F10.7/Ap,
5 mm chipsat) sets the demand:

| altitude / pose | drag mean | drag max | covered by 13.65 nN (200 V)? |
|---|---|---|---|
| 400 km axial | 32.9 nN | 92.4 nN | no |
| 400 km lateral | 21.7 nN | 60.7 nN | no |
| 500 km axial | 7.6 nN | 28.4 nN | mean only |
| 550 km axial | 3.9 nN | 16.3 nN | mean; max barely missed |
| 600 km axial | 2.0 nN | 9.6 nN | yes, fully |

Scaling the committed float200 measurement (13.65 nN at 200 V / 0.342 mA) by
`I·sqrt(V − φ)` predicts **~30 nN** at this operating point — enough to cover
the 500 km worst-case row (28.4 nN), close 550 km with margin, and lift the
400 km duty cycle substantially.

## What is gated

There is no regression anchor at 300 V, so the **required** gates are only
the theory-anchored invariants that hold at any operating point (see
`acceptance.yaml`): escape ≥ 95 %, benign float (φ ≤ 50 V), steady current
balance ≤ 5 %, momentum sanity, sheath/plume containment, and both
ledger-vs-dump charge cross-checks. The mission-coverage question
(`f_beam_nN ≥ 28.4`) is **reported, not required** — a miss is a finding
about the `I·sqrt(V − φ)` scaling, not an invalid run.

## What is different from the baseline, exactly

| | floating_body (baseline) | high_thrust (this stage) |
|---|---|---|
| `cathode_offset` | −200 V | **−300 V** |
| `i_beam` | 0.342 mA | **0.63 mA** |
| `max_steps` | 160 000 | **200 000** (CFL dt shrinks to ~4.15 ps) |
| everything else | — | identical |

The larger emitted current must be neutralized by roughly twice the ambient
electron collection, so the float should settle higher (~+30 V by the same
`(1+χ)` scaling that put the baseline at +17 V) — still well below the 50 V
design limit. If instead the ionosphere cannot supply it, the choke
watchdog (φ > 100 V sustained) fails the run early, and that too is a
finding: the emission ceiling has outrun the collection ceiling at this
density.

## Usage

```bash
conda activate warpx-cpu-mpich-dev
python simulation.py                                   # ~8 h CPU (193k steps)
python analyze.py --run outputs/<run-id> --policy acceptance.yaml
```

Caveats travel with the ladder: reduced ion mass (400 mₑ, not O⁺),
electrostatic (no B, no ram drift), single grid/PPC/seed, finite-time
equilibrium on the ion clock.
