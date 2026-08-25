# capstone.high_thrust: 300 V (the tested ceiling until 2026-08-17; since extended by `../350V_400km/`)

Same system as `floating_body`, driven at 300 V / 0.63 mA. The questions:
how much thrust at full drive, and does the body still float safely?

[![dashboard](viz/20260804T154756Z_b854dcbe_dashboard.gif)](viz/20260804T154756Z_b854dcbe_dashboard.mp4)

*Animated dashboard. Click for the full video.*

## Setup

![schematic](viz/schematic_3_high_thrust.png)

| | floating_body | this stage |
|---|---|---|
| `cathode_offset` | −200 V | **−300 V** |
| `i_beam` | 0.342 mA | **0.63 mA** |
| `max_steps` | 160k | **200k** (CFL dt ~4.15 ps) |
| everything else | — | identical |

$$I / I_{CL} = 1.46 \;\Rightarrow\; i_\text{beam} = 0.63\ \text{mA}$$

The larger current needs ~2× ambient collection, so the float settles higher
(~+30 V). The choke watchdog (φ > 100 V sustained) fails the run if the
ionosphere cannot supply it.

## How the PIC works

Same engine as `floating_body`: deck, charge pump, reservoir, observer
identical. Only the drive point differs.

## Results

Reference run `20260804T154756Z_b854dcbe`, all gates PASS. No regression
anchor; gates are theory-anchored invariants only.

| check | measured | target |
|---|---|---|
| escape | 99.0% | ≥ 95% |
| thrust | 30.13 nN | reported |
| φ_body | +36.3 V | ≤ 50 V |
| exhaust KE | 210.1 eV | reported |
| current balance | 3.5% | ≤ 5% |
| edge |φ| | 108 mV | ≤ 1 V |

Mission coverage (f_beam ≥ 28.4 nN for 500 km): PASS.

## Commands

```bash
python simulation.py                    # ~8 h
python analyze.py --run outputs/<run-id> --policy acceptance.yaml
```

## Limitations

- reduced ion mass (400 mₑ), electrostatic only, single grid/PPC/seed, finite-time equilibrium
