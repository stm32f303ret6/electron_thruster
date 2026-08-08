# capstone.low_power — 100 V floor

same system as `floating_body` driven at **100 V** / 0.121 mA. measures what thrust costs at the power-optimal low-voltage point.

[![dashboard](viz/20260804T230218Z_0adb478f_dashboard.gif)](viz/20260804T230218Z_0adb478f_dashboard.mp4)

*animated dashboard — click for the full video.*

## setup

![schematic](viz/schematic_4_low_power.png)

| | floating_body | this stage |
|---|---|---|
| `cathode_offset` | −200 V | **−100 V** |
| `i_beam` | 0.342 mA | **0.121 mA** |
| everything else | — | identical (CFL dt ~6.93 ps, ~115k steps) |

$$I / I_{CL} = 1.46 \;\Rightarrow\; i_\text{beam} = 0.121\ \text{mA}$$

### three-point P–F frontier

| stage | V | I | F (nN) | P (mW) | F/P (µN/W) |
|---|---|---|---|---|---|
| low_power | 100 | 0.121 mA | **3.42** | 12.1 | **0.283** |
| floating_body | 200 | 0.342 mA | **13.65** | 68.4 | **0.200** |
| high_thrust | 300 | 0.63 mA | **30.13** | 189 | **0.159** |

$F/P \propto 1/\sqrt{V}$ confirmed. measured float: **5.40 V**, exhaust KE **77.19 eV**.

## results

reference run `20260804T230218Z_0adb478f`, all gates PASS:

| metric | measured |
|---|---|
| escape | 96.1% |
| thrust | 3.42 nN |
| φ_body | +5.40 V |
| exhaust KE | 77.19 eV |
| current balance | 1.5% |
| edge |φ| | 5.8 mV |

## how the pic works

same engine as `floating_body` — deck, charge pump, reservoir, observer identical. only the drive point differs.

## what is gated

same structure as `high_thrust`: required gates are theory-anchored invariants (escape ≥ 95%, float ≤ 50 V, current balance, momentum, containment, ledger checks).

## commands

```bash
python simulation.py                    # ~5 h
python analyze.py --run outputs/<run-id> --policy acceptance.yaml
```

## limitations

- reduced ion mass (400 mₑ), electrostatic only, single grid/PPC/seed, finite-time equilibrium
