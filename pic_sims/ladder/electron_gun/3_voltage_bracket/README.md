# emitter.voltage_bracket — the gun along the voltage axis

same holed-anode gun as `emitter.holed_anode`, with accelerating voltage as the study axis. three scenarios bracket the capstone's drive conditions: 200 V and 300 V both transmit at the same perveance fraction, while 92.4 V hits the space-charge ceiling. closes validation gap G3 between the emitter branch (100 V) and the capstone commands (200 V, 300 V).

## setup

same geometry as `holed_anode` (1.9 mm gap, 0.5 mm spot, 1.4 mm hole). the axis under study is V, not the aperture.

| scenario | V | current | % of planar $I_{CL}$ | what it shows |
|---|---|---|---|---|
| A — anchor drive | 200 V | 0.342 mA | 23.9% | capstone anchor transmits cleanly |
| B — ceiling drive | 300 V | 0.630 mA | 23.9% | same perveance fraction, same result |
| C — over-perveance | 92.4 V | 0.601 mA | **133.5%** | space-charge current limiting |

## how the pic works

- **emission**: prescribed flux-maxwellian from 0.5 mm disc, scenario sets the current, 128 macroparticles/cell/step
- **voltage axis**: cathode dirichlet overridden per scenario (−200 V, −300 V, −92.4 V); anode and collector grounded
- **anode plate**: same implicit-function EB as `holed_anode`, 0 V
- **field solve**: electrostatic poisson (multigrid) every step, self-consistent space charge
- **push**: shape-1, dt = 1.0 ps ($v_{max}\,dt \approx 0.22\,dz$ at 300 V), 6000 steps = 6 ns

## what this step tests

| check | target |
|---|---|
| A transmits | ≥ 96% |
| B transmits | ≥ 96% |
| transmission flat across bracket | $\lvert A - B \rvert$ ≤ 2 pp |
| C pays for over-perveance | ≥ 3 pp drop vs A |
| energy conservation (each) | ≤ 1.5 eV error |
| particle budget (each) | ≤ 0.1% |

## commands

```bash
python simulation.py --scenario A_200v_anchor_drive
python simulation.py --scenario B_300v_ceiling_drive
python simulation.py --scenario C_ucurve_overperveance
python analyze.py --runs outputs/<A> outputs/<B> outputs/<C> --policy acceptance.yaml
```

~4 min/scenario.

## validates for capstone

beam formation at the capstone's actual drive voltages (200 V, 300 V) and space-charge limiting at 92.4 V — closes gap G3.

## limitations

- prescribed-flux emission, electrons only
- planar geometry, not the capstone's in-can gap (4.7 mm)
- electrostatic, no B, no collisions
