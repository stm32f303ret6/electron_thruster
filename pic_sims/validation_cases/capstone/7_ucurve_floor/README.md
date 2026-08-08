# capstone.ucurve_floor — no-go boundary at 78 V

maps the no-go wall of the fixed-thrust throttle curve — a **boundary demonstration**, not an operating point. same system as `floating_body` driven at **78 V** with current commanded for 13.65 nN.

## setup

![schematic](viz/schematic_7_ucurve_floor.png)

| | floating_body | this stage |
|---|---|---|
| `cathode_offset` | −200 V | **−78 V** |
| `i_beam` | 0.342 mA | **0.840 mA** |
| everything else | — | identical (CFL dt ~7.75 ps, ~103k steps) |

$I / I_{CL}(78\ \text{V}) = 14.7$ → 10.1× the validated emission ceiling.

### hypotheses (pre-registered in `UCURVE_PLAN.md`)

| | H1 — calibrated laws (implausible) | H2 — beam-optics failure |
|---|---|---|
| escape | ≥ 96% | collapses |
| φ_body | 47.3 V, brushing benign limit | ~0 V |
| delivered F | 13.65 nN | far short |
| steady state | converges | possibly none |

## how the pic works

same engine as `floating_body` — deck, charge pump, reservoir, observer identical. only the drive point differs.

## what is gated

H2 predicts no steady state, so **even current balance is reported**. required gates are accounting-trust only: momentum sanity, containment ≤ 1 V, scrape consistency ≤ 2% (×2). a PASS with collapsed escape/thrust *is the finding*.

## commands

```bash
python simulation.py                    # ~4.4 h
python analyze.py --run outputs/<run-id> --policy acceptance.yaml
```

## limitations

- reduced ion mass (400 mₑ), electrostatic only, single grid/PPC/seed, finite-time equilibrium
- commanded current 10× outside validated envelope **by design**
