# emitter.voltage_bracket — the gun along the voltage axis

Third step of the emitter branch. The same holed-anode gun as [`emitter.holed_anode`](../2_electron_gun/README.md), with the accelerating voltage promoted to the study axis: three scenarios bracket, in the clean isolated-emitter geometry, the drive conditions the capstone stages actually command.

## Why this step exists

The emitter branch validated beam formation at **100 V** only, while the capstone stages gun at **200 V** (anchor) and **300 V** (ceiling) — gap G3 in [`VALIDATION_GAPS.md`](../../capstone/2_chipsat_thruster/VALIDATION_GAPS.md). Scenarios A and B close that gap. Scenario C adds the emitter-side companion evidence for the fixed-thrust throttle stages ([`UCURVE_PLAN.md`](../../capstone/UCURVE_PLAN.md)): the 92.4 V ucurve_left_arm command drives this gun **past its planar space-charge ceiling**, demonstrating current limiting in isolation before the capstone deck meets the same condition inside the can.

## Setup

Same diode + holed grounded plate as `emitter.holed_anode` (1.9 mm accel gap, 0.5 mm spot, 1.4 mm restored-transmission hole throughout — the axis under study is V, not the aperture).

| Scenario | V | Current | % of planar I_CL | What it shows |
|---|---|---|---|---|
| A — anchor drive | 200 V | 0.342 mA | 23.9 % | capstone anchor command transmits cleanly |
| B — ceiling drive | 300 V | 0.630 mA | 23.9 % | same perveance fraction, same result at the frontier's top |
| C — over-perveance | 92.4 V | 0.601 mA | **133.5 %** | space-charge current limiting past the ceiling |

A and B sit at the *same* fraction of the gun's planar ceiling because both capstone commands derive from the same measured emission-ceiling ratio — which is exactly the bracket's claim: at fixed perveance fraction, beam formation and transmission are voltage-independent.

## What this step tests

| Check | Target |
|---|---|
| A transmits | ≥ 96 % to collector |
| B transmits | ≥ 96 % to collector |
| Transmission flat across the bracket | \|A − B\| ≤ 2 pp |
| C pays for the over-perveance command | ≥ 3 pp drop vs A (required) |
| Where C's limited current lands | reported (collector fraction, cathode return) |
| Energy conservation (each scenario) | ≤ 1.5 eV error from emission-plane φ |
| Particle budget (each scenario) | ≤ 0.1 % |

The planar Child–Langmuir number is a printed scale only, never a gate (non-planar geometry — the `holed_anode` precedent).

## Commands

```bash
python simulation.py --scenario A_200v_anchor_drive
python simulation.py --scenario B_300v_ceiling_drive
python simulation.py --scenario C_ucurve_overperveance
python analyze.py --runs outputs/<A> outputs/<B> outputs/<C> --policy acceptance.yaml
```

~4 min/scenario on the reference GPU (6 ns, 6000 steps each).

## Limitations

- Prescribed-flux emission (no thermionic model), electrons only
- Planar mid-plate geometry, not the capstone's in-can gap (4.7 mm): I_CL scales differ; what transfers is the *mechanism*, gated as fractions of each geometry's own ceiling
- Electrostatic, no magnetic field, no collisions
