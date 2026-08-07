# capstone.ucurve_valley — fixed-thrust throttle curve at 125 V

![Schematic](viz/schematic_5_ucurve_valley.png)

Same system as [`capstone.floating_body`](../2_chipsat_thruster/README.md) — identical can, plasma, grid, reservoir, and charge pump — driven at **125 V** with the beam current commanded for the 200 V anchor's measured thrust:

```
F demand = 13.65 nN (the 200 V anchor's measurement)
model/ucurve_targeting.py (H1 branch)  →  i_beam = 0.464 mA
I / I_CL(125 V) = 4.0  →  2.7× the validated emission ceiling
```

## The question

**Where is the specific-power valley of the fixed-thrust throttle curve?**

The committed frontier (100/200/300 V) holds perveance at the validated I/I_CL = 1.46 and measures the *envelope boundary* — thrust varies ~V² along it. It never measures what a **fixed demand** costs as V drops, which is exactly the slice the §7b flight rule (`SCALING_LAWS.md`) lives on. This stage opens that slice; with `ucurve_left_arm` (92.4 V), `ucurve_floor` (78 V), and the committed 200 V anchor as the fourth point, the repo measures the curve the flight rule optimizes over.

Pre-registered hypotheses and predictions: [`../UCURVE_PLAN.md`](../UCURVE_PLAN.md), committed before the run.

| | H1 — calibrated laws, frontier escape | H2 — perveance tax |
|---|---|---|
| escape | ≥ 96 % | degraded (beam optics past the ceiling) |
| φ_body | ~24.5 V | lower (less escaped current) |
| delivered F | 13.65 nN (on demand) | short of demand |
| P/F | 4.25 mW/nN | above H1; valley at/right of 125 V |

## What changed from the baseline

| | floating_body (baseline) | ucurve_valley (this stage) |
|---|---|---|
| `cathode_offset` | −200 V | **−125 V** |
| `i_beam` | 0.342 mA | **0.464 mA** (fixed-thrust command) |
| everything else | — | identical (CFL dt ~6.25 ps; ~128k steps for 800 ns) |

## What is gated

Escape, float, and delivered thrust are **the measurement**, so (per the `capstone.exploratory_axes.v1` precedent) they are reported, not required. Required gates are the trust set only — steady current balance, momentum sanity, sheath/plume containment, and both ledger-vs-dump cross-checks — tolerances byte-identical to the frontier policies.

## Commands

```bash
python simulation.py                                   # ~5.5 h (128k steps)
python analyze.py --run outputs/<run-id> --policy acceptance.yaml
```

## Limitations

- Reduced ion mass (400 mₑ, not O⁺)
- Electrostatic only (no B, no ram drift)
- Single grid/PPC/seed
- Finite-time equilibrium on the ion clock
- Commanded current sits 2.7× outside the validated emission envelope **by design** — that excursion is the object of measurement, not an oversight
