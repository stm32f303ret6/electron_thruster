# 1U CubeSat at 400–500 km: station keeping, free fall, and power-limited lifetime

> **Status (2026-09-23): plan only, nothing run.** The author is weighing
> further considerations before execution; those go in "Author's
> considerations" at the end, and the stages below are revised against them
> before anything runs. The numbers in "Preview" are estimates scaled from
> committed runs, not results of this plan.

## Why

400–450 km is where most CubeSats start: the ISS deployment band. The 1U
(10 × 10 × 10 cm) is the smallest standard CubeSat and the one with the least
power. The committed mission analysis covers the 3.1 g slender can (the
measured PIC shape) and a 3U-size scale-up; it says nothing yet about the
standard bus most people would fly this on, at the altitudes where drag
actually ends missions. For an electric-propulsion audience this is the
first case they will ask about.

## Preview: what the committed runs already imply

The environment along an orbit is body-independent (altitude is held), so
drag and power scale with the drag area S_ref. A 1U flown face-on has ~103×
the slender can's S_ref. Scaling the committed slender station-keeping cases
(`model/results/mission_summary.json`; ranges span the three orbit families;
450 km is interpolated as the geometric mean of 400 and 500 km, since it has
not been run):

| altitude | power to hold, 2024 (solar max) | power to hold, 2019 (solar min) | 1U body-mounted supply (~2.0 W) covers, 2024 / 2019 | sink rate with no thruster, 2024 / 2019 |
|---|---|---|---|---|
| 400 km | 28–30 W | ~2.2 W | 7 % / 0.9× | 450–500 m/day / 45–55 m/day |
| 450 km (interpolated) | 11–12 W | ~0.7 W | 17 % / 3× | 215–245 m/day / 16–20 m/day |
| 500 km | 4.7–4.9 W | ~0.2 W | 42 % / 10× | 105–120 m/day / 6–7 m/day |

(Supply: `model/scale_analysis.py` assumptions — 30 % cells on a third of
the 600 cm² skin, 25 % illumination. Power: slender mission-model means ×
the S_ref ratio, so it carries the chip-scale float tax, not the 1U's.)

Reading: near solar minimum a 1U holds 450–500 km on its own cells and
400 km nearly; near solar maximum it cannot hold 400–500 km, and the useful
question becomes lifetime extension under a fixed power budget.

## Body

`orbit_sims` flies cylinders only. The 1U is modelled as the cylinder with
the same ram face: r = 5.64 cm (100 cm²), h = 10 cm, axial (face-on).

| | 1U cube, face-on | cylinder equivalent |
|---|---|---|
| ram face | 100 cm² | 100 cm² |
| walls parallel to the flow | 400 cm² | 354 cm² |
| S_ref at 500 km (C_d,side/C_d ≈ 0.031) | 112 cm² | 111 cm² (−1 %) |
| skin (collection, supply) | 600 cm² | 554 cm² (supply is taken from the cube's 600 cm²) |
| L/r | — | 1.8 |

Mass: 1.33 kg (classic 1U) or 2 kg (current CDS limit), **open** — it does
not change drag or power, only the free-fall and capped lifetimes
(ballistic coefficient 54 vs 82 kg/m²).

## Stages

### Stage 1: fill 450 km (station keeping, slender body)

`450km_station_keeping_slender{,_iss,_sso}{,_2019}`: 6 year-long runs, same
settings as the committed slender cases (SSO inclination 97.21° from J2 at
450 km, node at 10:30 local time). Gives the 450 km demand directly instead
of interpolated, for every body (drag scales by S_ref). ~15 min in parallel.

### Stage 2: 1U free fall

`{400,450,500}km_free_fall_1u{,_iss,_sso}{,_2019}`: 18 runs, the cylinder
equivalent above, thruster off, 5-year cap, 120 s step, hourly output (the
committed free-fall settings). ~30–60 min in parallel (the long ones are
2019 starts that survive).

### Stage 3: power-limited thruster (new orbit_sims mode)

Neither the ideal cancel mode nor the post-process replay fits a 1U near
solar maximum: the thruster cannot keep up, the craft sinks kilometres, and
the denser air it meets must feed back into the drag. That needs the
thruster in the propagation loop.

Proposed code change (orbit_sims stays thruster-agnostic):

- `mission.thruster: capped` with `mission.thrust_cap_N`: thrust =
  min(|drag|, cap) along the airspeed direction, every step.
- The cap is set by the model, not by orbit_sims: the closed-form law
  `F/P = c_eff/√V` (`model/mission_model.py --closed-form`) at the 100 V
  floor gives 0.293 µN/W, so 1 W → 0.29 µN and 2 W → 0.59 µN. This neglects
  the float tax, so it is optimistic; the thin-sheath float estimate for a
  1U (`SCALE_ANALYSIS.md` Step 5: 13–40 V at 500–600 km) would lower the cap
  by 7–23 % at 100 V and should be carried as a sensitivity.
- Output: the free-fall CSV schema (no IRI), re-entry or 5-year cap.

Runs: 1U on the ISS orbit (where 400–450 km 1Us fly; **open**: add the other
two families?), 400/450/500 km × 2024/2019 × budgets {1 W, 2 W}: 12 runs.

Control law, **open**: plain min(drag, cap) cannot climb back after a peak,
so where the cap covers the mean but not the peaks (400 km, 2019, 2 W) the
orbit decays slowly anyway. An altitude-target law (fire at the cap while
below the target semi-major axis) would hold it, at the cost of a
deadband choice on an osculating element that breathes a few km with J2.

### Stage 4: analysis

Extend `model/altitude_hold.py` (or a sibling) to tabulate, per altitude ×
year: free-fall lifetime, capped lifetime at 1 W and 2 W, the extension
factor, and the full-hold power from Stage 1. A figure in the style of
`paper/figs/make_missions.py` panel (a): 1U altitude vs time, thruster off
vs 1 W vs 2 W, from 400 km near solar maximum.

## Predictions (recorded before any run)

A fixed cap C below the drag F everywhere turns the decay rate into
(F − C)/F of free fall, so lifetime stretches by roughly F/(F − C) at the
start altitude, less as the craft sinks and F grows:

| case | cap vs mean drag at start | expected outcome |
|---|---|---|
| 400 km, 2024, 2 W | 0.59 vs ~4.1 µN | lifetime +10–20 % |
| 450 km, 2024, 2 W | 0.59 vs ~2.0 µN | +30–50 % |
| 500 km, 2024, 2 W | 0.59 vs ~0.95 µN | ×2 or more |
| 400 km, 2019, 2 W | 0.59 vs ~0.44 µN | holds on average; peaks decay it slowly without a recovery law |
| 450–500 km, 2019, 1–2 W | ≥ 0.29 vs ≤ 0.17 µN | held for the full 5 years |

Free fall (Stage 2), from the sink rates above: 400 km near solar maximum
re-enters within months; 500 km near solar minimum survives the 5-year cap.

## Caveats that travel with every number

- Sheath regime. A 1U is ~25 Debye lengths across; no committed PIC run
  sits there, and the collection law is extrapolated (same caveat as the
  3U). The cap mapping neglects the float entirely.
- Shape. L/r = 1.8 sits between the measured bodies (1.1 and 6), so
  `mission_model.py` refuses it; 1U power numbers are area-scaled from the
  slender body, not a model sweep.
- Attitude. Face-on is assumed held; a tumbling 1U has a larger mean drag
  area (Cauchy A_ext/4 = 150 cm² vs 112).
- Power. Budgets are orbit averages with battery buffering; eclipse
  scheduling is not modelled.
- Forecasts. 2024 starts run on forecast solar indices after mid-2025.

## Cost

Stages 1–2: ~24 year-to-5-year runs, about 1 hour on 15 cores. Stage 3: a
small orbit_sims change (tested byte-identical in the other modes, as the
free-fall change was) plus 12 runs, ~30–60 min. Stage 4: ~20 min.

## Open questions

1. 1U mass: 1.33 kg or 2 kg?
2. Capped runs on the ISS orbit only, or all three families?
3. Budgets: 1 W and 2 W, or a sweep (0.5 / 1 / 2 / 4 W) for a
   lifetime-vs-power curve?
4. Control law: plain min(drag, cap), or altitude-target with recovery?
5. Include the 3U in the capped mode too?

## Author's considerations (to add before running)

_Reserved for the author's notes; the stages above are revised against them
before execution._
