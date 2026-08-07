# capstone.ucurve_floor — the throttle curve's no-go boundary at 78 V

![Schematic](viz/schematic_7_ucurve_floor.png)

Same system as [`capstone.floating_body`](../2_chipsat_thruster/README.md) — identical can, plasma, grid, reservoir, and charge pump — driven at **78 V**, far below the 100 V hardware floor, with the beam current commanded for the 200 V anchor's measured thrust:

```
F demand = 13.65 nN (the 200 V anchor's measurement)
model/ucurve_targeting.py (H1 branch)  →  i_beam = 0.840 mA
I / I_CL(78 V) = 14.7  →  10.1× the validated emission ceiling
```

## The question

**Does this thrust demand have *any* operating point at 78 V?**

This is a **boundary demonstration**, not an operating-point extension. Even the optimistic H1 branch is self-underming here: it needs χ = 416 (the measured envelope tops out at 319) and floats at 47.3 V, brushing the 50 V benign limit. H2 says the run fails by beam optics long before the float binds — the in-repo precedent is the killed slender attempt (`../SLENDER_BODY_PLAN.md` amendment), where a commanded current far over the gap's ceiling self-scraped 91 % of the beam and the float stuck at 0.3 V. Either outcome maps the no-go wall that justifies (or corrects) the flight rule's voltage floor.

Pre-registered hypotheses and predictions: [`../UCURVE_PLAN.md`](../UCURVE_PLAN.md), committed before the run.

| | H1 — calibrated laws (implausible here) | H2 — beam-optics failure |
|---|---|---|
| escape | ≥ 96 % | collapses (10× past the ceiling) |
| φ_body | 47.3 V, brushing the benign limit | never binds (~0 V) |
| delivered F | 13.65 nN (on demand) | far short |
| steady state | converged current balance | possibly none at this demand |

## What changed from the baseline

| | floating_body (baseline) | ucurve_floor (this stage) |
|---|---|---|
| `cathode_offset` | −200 V | **−78 V** (maps the no-go wall) |
| `i_beam` | 0.342 mA | **0.840 mA** (fixed-thrust command) |
| everything else | — | identical (CFL dt ~7.75 ps; ~103k steps for 800 ns) |

## What is gated

H2 predicts this run may never reach a steady state, so **even the current-balance gate joins the reported set** — a policy must not gate away its own hypothesis. Required gates are the accounting-trust set only: momentum sanity, sheath/plume containment, and both ledger-vs-dump cross-checks (frontier tolerances). A FAIL on those is a bad run to be rerun; a PASS with collapsed escape/thrust *is the finding*.

## Commands

```bash
python simulation.py                                   # ~4.4 h (103k steps)
python analyze.py --run outputs/<run-id> --policy acceptance.yaml
```

## Limitations

- Reduced ion mass (400 mₑ, not O⁺)
- Electrostatic only (no B, no ram drift)
- Single grid/PPC/seed
- Finite-time equilibrium on the ion clock
- Commanded current sits 10× outside the validated emission envelope **by design** — the excursion is the demonstration
