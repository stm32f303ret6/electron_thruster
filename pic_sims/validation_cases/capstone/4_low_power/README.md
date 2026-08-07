# capstone.low_power — thruster at the 100 V hardware floor

![Schematic](viz/schematic_4_low_power.png)

Same system as [`capstone.floating_body`](../2_chipsat_thruster/README.md) — identical can, plasma, grid, reservoir, and charge pump — driven at **100 V** with the beam current scaled to the same emission-ceiling ratio:

```
I_CL(100 V, 4.7 mm gap, 0.5 mm spot) = 0.083 mA
I / I_CL = 1.46 (measured float200 ratio)  →  i_beam = 0.121 mA
```

## The question

**What does thrust cost at the cheap end of the throttle curve?**

Supply power scales roughly as √V at fixed thrust, so the lowest feasible voltage is always the power-optimal operating point. What caps how low you can go is the space-charge emission ceiling I_CL ∝ V^1.5: at 100 V the spot can only source ~0.12 mA. This point trades thrust for thrust-per-watt.

### Three-point P–F frontier (complete)

| Stage | V | I | F (nN) | P (mW) | F/P (µN/W) |
|---|---|---|---|---|---|
| `capstone.low_power` | 100 | 0.121 mA | **3.42** | 12.1 | **0.283** |
| `capstone.floating_body` | 200 | 0.342 mA | **13.65** | 68.4 | **0.200** |
| `capstone.high_thrust` | 300 | 0.63 mA | **30.13** | 189 | **0.159** |

F/P ∝ 1/√V confirmed across the range: 0.283 / 0.200 / 0.159 µN/W. At this low χ the candidate collection laws converge, so this point confirms the anchor rather than discriminating between them (the 300 V run carries the discrimination).

The predicted float was lower than the 200 V case (~+6 V vs +17 V) because the smaller current needs less ambient return collection. Measured: **5.40 V**, exhaust KE **77.19 eV** (prediction: 77.10 eV).

## What changed from the baseline

| | floating_body (baseline) | low_power (this stage) |
|---|---|---|
| `cathode_offset` | −200 V | **−100 V** |
| `i_beam` | 0.342 mA | **0.121 mA** |
| everything else | — | identical (CFL dt grows to ~6.93 ps; ~115k steps for 800 ns) |

## What is gated

Same structure as `capstone.high_thrust`: required gates are only the theory-anchored invariants (escape ≥ 95%, float ≤ 50 V, current balance, momentum sanity, containment, ledger cross-checks). The mission bar (holding 600 km mean station keeping, 2.01 nN) is reported, not required.

## Dashboard

[![Dashboard](viz/20260804T230218Z_0adb478f_dashboard.gif)](viz/20260804T230218Z_0adb478f_dashboard.mp4)

*Animated dashboard — click for the full video.*

## Commands

```bash
python simulation.py                                   # ~5 h (115k steps)
python analyze.py --run outputs/<run-id> --policy acceptance.yaml
```

## Limitations

- Reduced ion mass (400 mₑ, not O⁺)
- Electrostatic only (no B, no ram drift)
- Single grid/PPC/seed
- Finite-time equilibrium on the ion clock
