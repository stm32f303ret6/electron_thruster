# capstone.high_thrust — thruster at the 300 V hardware ceiling

![Schematic](viz/schematic_3_high_thrust.png)

Same system as [`capstone.floating_body`](../2_chipsat_thruster/README.md) — identical can, plasma, grid, reservoir, and charge pump — driven at **300 V** with the beam current scaled to the same emission-ceiling ratio:

```
I_CL(300 V, 4.7 mm gap, 0.5 mm spot) = 0.431 mA
I / I_CL = 1.46 (measured float200 ratio)  →  i_beam = 0.63 mA
```

## The question

**How much thrust at full drive, and does the body still float safely?**

### Drag budget from orbit_sims (2024, real F10.7/Ap, 5 mm chipsat)

| Altitude / pose | Drag mean | Drag max | Covered by 13.65 nN (200 V)? |
|---|---|---|---|
| 400 km axial | 32.9 nN | 92.4 nN | no |
| 400 km lateral | 21.7 nN | 60.7 nN | no |
| 500 km axial | 7.6 nN | 28.4 nN | mean only |
| 550 km axial | 3.9 nN | 16.3 nN | mean; max barely missed |
| 600 km axial | 2.0 nN | 9.6 nN | yes |

Scaling the 200 V measurement (13.65 nN at 0.342 mA) by I·√(V − φ) predicts ~30 nN — enough to cover the 500 km worst case (28.4 nN).

## What changed from the baseline

| | floating_body (baseline) | high_thrust (this stage) |
|---|---|---|
| `cathode_offset` | −200 V | **−300 V** |
| `i_beam` | 0.342 mA | **0.63 mA** |
| `max_steps` | 160 000 | **200 000** (CFL dt shrinks to ~4.15 ps) |
| everything else | — | identical |

The larger current needs roughly twice the ambient electron collection, so the float should settle higher (~+30 V) — still below the 50 V design limit. If the ionosphere can't supply it, the choke watchdog (φ > 100 V sustained) fails the run early.

## What is gated

No regression anchor at 300 V, so the required gates are only the theory-anchored invariants that hold at any operating point: escape ≥ 95%, float ≤ 50 V, current balance ≤ 5%, momentum sanity, containment, and both ledger cross-checks.

The mission-coverage question (f_beam_nN ≥ 28.4) is reported, not required — a miss is a finding about the scaling, not an invalid run.

## Dashboard

[![Dashboard](viz/20260804T154756Z_b854dcbe_dashboard.gif)](viz/20260804T154756Z_b854dcbe_dashboard.mp4)

*Animated dashboard — click for the full video.*

## Commands

```bash
python simulation.py                                   # ~8 h (193k steps)
python analyze.py --run outputs/<run-id> --policy acceptance.yaml
```

## Limitations

- Reduced ion mass (400 mₑ, not O⁺)
- Electrostatic only (no B, no ram drift)
- Single grid/PPC/seed
- Finite-time equilibrium on the ion clock
