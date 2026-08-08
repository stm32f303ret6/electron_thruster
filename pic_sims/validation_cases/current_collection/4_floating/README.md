# collector.floating — sphere on the charge pump

same sphere and plasma, but the EB potential **floats** using the capstone's charge-pump mechanism. with no beam, the pump drives the sphere to the **floating potential** — where electron and ion collection balance.

[![dashboard](viz/20260806T162656Z_40e77ecd_dashboard.gif)](viz/20260806T162656Z_40e77ecd_dashboard.mp4)

*animated dashboard — click for the full video.*

## setup

![schematic](viz/schematic_4_floating.png)

the charge pump:

1. EB starts at 1 V → init solve calibrates self-capacitance C (gauss' law on domain faces)
2. every step, scraped weights → $dQ = e\,(w_i - w_e)$
3. `set_potential_on_eb` rewrites $\phi = \phi_{init} + Q/C$

### analytic references

let $R = I_{th,e}/I_{th,i} = 23.74$.

| ion model | balance equation | φ_f |
|---|---|---|
| thermal-ion | $\exp(e\phi/kT_e)\cdot R = 1$ | **−0.360 V** |
| OML-ion | $\exp(e\phi/kT_e)\cdot R = 1 - e\phi/kT_i$ | **−0.213 V** |

truth lies between the two. φ_f is independent of C (C only sets the timescale).

## how the pic works

same deck as `thermal` (bulk fill + flux injection), plus the charge pump:

- **field solve**: electrostatic poisson every step, EB sphere + grounded walls
- **C calibration**: init solve at uniform 1 V → gauss-law surface integral → C
- **charge pump**: per step, $dQ = e\,(w_i - w_e)$ from EB scrape buffers → $\phi = \phi_{init} + Q/C$ via `set_potential_on_eb`
- **measurement**: CSV ledger records φ, Q, I_e, I_i every 500 steps; gates check last-40% steady window

## what this step tests

| check | target |
|---|---|
| floating potential φ_f | [−0.40, −0.19] V |
| current balance at equilibrium | ≤ 15% |
| capacitance vs $4\pi\varepsilon_0 a$ | [0.8, 1.4] |
| ledger vs openpmd dumps | ≤ 2% |
| far-field density | ≤ 5% off n0 |
| quasineutrality | ≤ 2% |
| edge potential | ≤ 0.2 V |

## results

reference run `20260806T162656Z_40e77ecd`, all gates PASS:

| metric | measured | gate |
|---|---|---|
| φ_f | −0.251 V | [−0.40, −0.19] V |
| current balance | 0.89% | ≤ 15% |
| C / C_analytic | 1.068 | [0.8, 1.4] |
| scrape consistency | 2.7e-9 | ≤ 0.02 |
| far density vs n0 | 0.02% off | ≤ 5% |
| quasineutrality | 0.13% | ≤ 2% |
| edge potential | 5.8 mV | ≤ 0.2 V |

## dependencies

requires `collector.thermal` (hash-verified config match). the capstone requires this stage.

## cost

~35 min. 100k steps × 60 ps = 6.0 µs. pump RC clock: $\tau \approx 1.7\ \mu$s near equilibrium.

## commands

```bash
python simulation.py
python analyze.py --run outputs/<run-id> --policy acceptance.yaml
```

## validates for capstone

the charge-pump mechanism (C calibration, per-step dQ, `set_potential_on_eb`) — the capstone uses the same code verbatim.

## limitations

- φ_f gate is a two-model bracket, not a single-model identity
- reduced ion mass (400 mₑ), not real O⁺
- single grid/PPC/seed (phase 5)
