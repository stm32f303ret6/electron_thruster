# capstone.two_node_laplace: the can geometry in vacuum

The chipsat's two-node EB geometry solved in vacuum (no particles). BODY at +16 V, CATHODE at −184 V, using the same `set_potential_on_eb` per-step rewrite the capstone uses. This shows the vacuum Laplace field is correct before any plasma is added.

## Setup

![schematic](viz/schematic_1_two_node_laplace.png)

- grid: the capstone's exact grid (200 × 440, dx = 0.15 mm)
- particles: none
- solver: every solve is Laplace's equation ($\nabla^2 \varphi = 0$)

## How the PIC works

1. No particles: grid, EB and electrostatic solver only.
2. EB init: the boundary starts at uniform 1 V (mirrors the capstone's capacitance calibration).
3. Two-node imposition: an after-init callback rewrites BODY = +16 V, CATHODE = −184 V via `set_potential_on_eb`.
4. Per step: 5 multigrid solves. Re-imposing the unchanged potential tests idempotency.
5. Output: φ dumped every step. The analysis gates surface values, the maximum principle, the independent solver match, and rewrite drift.

## Results

Reference run `20260806T142600Z_f44044c6`, all gates PASS:

| check | measured | target |
|---|---|---|
| body surface potential vs assigned | 0.220 V error | ≤ 1 V |
| cathode surface potential vs assigned | 0 V error | ≤ 1 V |
| maximum principle | 0 V violation | ≤ 0.1 V |
| independent RZ solver | 1.864 V diff | ≤ 4 V |
| per-step rewrite idempotency | 0 V drift | ≤ 1 mV |

The independent solver is a scipy sparse direct factorization with a stair-step EB, a different representation and solver than WarpX. The comparison excludes the 3-cell skin near surfaces.

## Dependencies

None (leaf step). The capstone requires this stage.

## Cost

Seconds. Five Laplace solves, no particles.

## Commands

```bash
python simulation.py
python analyze.py --run outputs/<run-id> --policy acceptance.yaml
```

## Reference figures

| | |
|---|---|
| ![fields](reference_results/20260806T142600Z_f44044c6/figures/fields.png) | ![phi axis](reference_results/20260806T142600Z_f44044c6/figures/phi_axis.png) |

## Validates for capstone

The capstone's exact two-node EB geometry and piecewise `set_potential_on_eb` rewrite, checked in vacuum before plasma is added.

## Limitations

- the independent solver uses a stair-step EB; the comparison is only meaningful a few cells from surfaces
- the EB potential is static here (the capstone changes it dynamically via the charge pump)
