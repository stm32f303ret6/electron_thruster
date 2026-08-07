# capstone.ucurve_left_arm — fixed-thrust throttle curve at 92.4 V

![Schematic](viz/schematic_6_ucurve_left_arm.png)

Same system as [`capstone.floating_body`](../2_chipsat_thruster/README.md) — identical can, plasma, grid, reservoir, and charge pump — driven at **92.4 V**, *below the 100 V hardware floor on purpose*, with the beam current commanded for the 200 V anchor's measured thrust:

```
F demand = 13.65 nN (the 200 V anchor's measurement)
model/ucurve_targeting.py (H1 branch)  →  i_beam = 0.601 mA
I / I_CL(92.4 V) = 8.2  →  5.6× the validated emission ceiling
```

## The question

**Does the fixed-thrust left arm exist — and which side of 125 V does the valley sit on?**

The calibrated laws (H1) put the specific-power valley near the self-consistent `V = 3.12·φ` point, **≈ 95 V at this demand** — which would make this stage, not `ucurve_valley`, the cheapest place to hold 13.65 nN. The perveance-tax hypothesis (H2) says beam optics collapse here first: the sign of **P/F(92.4) − P/F(125)** is the single sharpest discriminator the pair produces.

Pre-registered hypotheses and predictions: [`../UCURVE_PLAN.md`](../UCURVE_PLAN.md), committed before the run.

| | H1 — calibrated laws, frontier escape | H2 — perveance tax |
|---|---|---|
| escape | ≥ 96 % | collapses (5.6× past the ceiling) |
| φ_body | ~32.5 V | low (beam self-scrapes before charging) |
| delivered F | 13.65 nN (on demand) | short, worse than at 125 V |
| P/F vs 125 V | **below** (4.07 vs 4.25 mW/nN) | **above** — valley is right of here |

## What changed from the baseline

| | floating_body (baseline) | ucurve_left_arm (this stage) |
|---|---|---|
| `cathode_offset` | −200 V | **−92.4 V** (below the hardware floor by design) |
| `i_beam` | 0.342 mA | **0.601 mA** (fixed-thrust command) |
| everything else | — | identical (CFL dt ~7.18 ps; ~111k steps for 800 ns) |

## What is gated

Identical structure to `ucurve_valley`: required gates are the trust set only (current balance, momentum sanity, containment, both ledger cross-checks, frontier tolerances); escape, float, and delivered thrust are reported — they are the measurement.

## Commands

```bash
python simulation.py                                   # ~4.8 h (111k steps)
python analyze.py --run outputs/<run-id> --policy acceptance.yaml
```

## Limitations

- Reduced ion mass (400 mₑ, not O⁺)
- Electrostatic only (no B, no ram drift)
- Single grid/PPC/seed
- Finite-time equilibrium on the ion clock
- Commanded current sits 5.6× outside the validated emission envelope **by design** — that excursion is the object of measurement, not an oversight
