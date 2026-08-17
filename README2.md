# Electron Thruster

**A propellantless thruster for small spacecraft: a cathode, a high-voltage
supply, and the spacecraft's own skin.**

The device fires an electron beam into space. The escaping beam carries
momentum away — that is the thrust. The ionosphere returns the same current
to the spacecraft's outer surface, so the net mass flow is zero: the thruster
needs no propellant.

## Motivation

Most LEO CubeSats fly with no propulsion at all. The reason is usually not
performance — it is what a propellant system brings with it:

- a tank and a pressure vessel
- valves, feed lines, propellant loading
- a launch-safety review that can cost more than the spacecraft
- tens of thousands of dollars and tens of watts, for commercial CubeSat EP

This project proposes a thruster with none of that:

- **no tank, no propellant, no valves, no neutralizer**
- thrust in the nN range — enough to cancel drag at 500–600 km, with the
  400 km mean demand covered at 350 V (mission-level questions still open)
- power in the mW range
- hardware: two electrodes and an HV supply

The goal is not the highest performance. It is the **lowest barrier to
actually flying a thruster**.

## How it works

### Components

1. **A negative cathode** — emits and accelerates electrons out of the
   spacecraft. The escaping beam produces the thrust.
2. **The spacecraft's own structure** — collects electrons back from the
   ionosphere. The skin is the second electrode.
3. **An HV supply** — holds the cathode at a fixed voltage below the body, so
   collected electrons are re-emitted as the beam.

### Operation

1. The spacecraft floats in the ionospheric plasma.
2. The supply connects the body to the cathode; the cathode starts emitting.
3. The escaping beam charges the body positive.
4. The positive body attracts electrons from the ambient plasma.
5. Collection grows until it exactly balances emission.

The process settles into a steady state: the body floats at the potential
**φ** where collected current equals emitted current. That float **is** the
operating point — there is no cycle, just a continuous equilibrium.

![Concept, step by step](paper/new/imgs/concept_steps.png)

### Thrust law

Thrust is the beam's momentum flux. Two measured constants describe it across
the full 100–350 V range to ~1 %:

```
F [nN] = 3.2675 · I [mA] · √KE [eV]
KE     = 0.8063 · (V − φ)
```

Two useful consequences:

- **The device measures its own thrust.** `I` and `φ` are plain electrical
  measurements any microcontroller can take in flight. No thrust stand needed.
- **The control law is trivial.** A two-line servo on the measured float — no
  ionosphere model, no lookup table. Density, temperature, day/night all
  collapse into where the body floats (`model/MODEL.md` §2).

## Comparison with ion thrusters

| | gridded ion thruster | electron thruster |
|---|---|---|
| thrust per watt | ~40 µN/W | ~0.2 µN/W (~200× worse) |
| power at nN thrust | ~1 mW | ~10–100 mW — at this scale the gap is negligible |
| energy conversion efficiency | ~70 % | **~73 %** — same class |
| tank / propellant / valves / neutralizer | yes | **no** |
| launch-safety review for stored propellant | yes | **no** |
| cost | tens of k$ | two electrodes + HV supply |
| works at mN scale | yes | no |
| works at nN scale | no (cannot throttle that low) | **yes** |
| depends on altitude / ambient plasma | no | yes |

The 200x thrust-per-watt penalty is irrelevant at nanonewtons and
disqualifying at millinewtons. That is why this device targets the low end,
where nothing else operates.

## Does it cancel drag?

Measured thrust with full PIC simulations show that this thruster produces **13.65 nN** at 200V consuming **~68 mW**, produces **30.13 nN** using 300V, and **40.48 nN** at 350 V. Against real 2024 drag (NRLMSISE-00, real F10.7/Ap, solar-cycle-25 maximum) for the anchor body:

- **Test body**: a cylinder, Ø10 mm × 5 mm height, 100 g, Cd = 2.2 — the
  same geometry the PIC simulations use.
- **axial**: drag hits the cap side of the cylinder.
- **lateral**: drag hits the skin side of the cylinder.

| altitude | drag mean | drag max | 13.65 nN (200 V) covers | 30.13 nN (300 V) covers |
|---|---|---|---|---|
| 400 km axial | 32.9 nN | 92.4 nN | — | — |
| 400 km lateral | 21.7 nN | 60.7 nN | — | mean |
| 500 km axial | 7.6 nN | 28.4 nN | mean | **mean and max** |
| 550 km axial | 3.9 nN | 16.3 nN | mean (max barely missed) | **mean and max** |
| 600 km axial | 2.0 nN | 9.6 nN | **mean and max** | **mean and max** |

The table above runs the thruster at one fixed voltage all year. In flight
the voltage can follow the drag instead: for every point along the orbit, the
model (`model/MODEL.md` §4) finds the lowest voltage that cancels that
point's drag and computes what it costs:

| altitude | minimum voltage | mean power | inside the tested envelope (≤ 350 V)? |
|---|---|---|---|
| 600 km | 100 V | 6.8 mW | yes |
| 550 km | 104 V | 13.4 mW | yes |
| 500 km | 146 V | 31.3 mW | yes |
| 400 km lateral | 247 V | 116 mW | yes — see the note below |
| 400 km axial | 304 V | 196 mW | yes — inside the extended 350 V envelope |

**Power is the thruster's interface to the spacecraft**: tens of mW at
500–600 km, ~100–200 mW at 400 km. Where that power comes from is mission
design, not part of the thruster — same as the cathode technology. For
context, typical small-spacecraft power:

- this geometry (femtosat class): ~10–30 mW from body-mounted solar cells,
  depending on coverage
- 1U CubeSat: ~1–2 W
- 3U CubeSat: ~5–10 W with body-mounted panels, more with deployables

Demand and supply both grow with area, so the ratio stays workable at
CubeSat size: a 3U needs ~0.9 W at 600 km against a typical 5–10 W budget.

**Note on 400 km.** The axial-pose demand is now inside the measured
envelope, at both tested geometries. The compact body delivered 40.48 nN
against the 32.9 nN mean demand (~81 % duty) but floats *on* the 50 V
charging limit (48.3 V gated, still rising at run end). The slender body —
the shape a real mission vehicle takes anyway — delivered **43.33 nN at a
14.0 V float**: the same demand covered at ~76 % duty with 3.6× margin on
the charging limit. What stays open at 400 km: drag maxima (92.4 nN) above
any single operating point, night-side plasma rows still extrapolated,
~150–200 mW mean power as mission design, and the lateral-pose thrust-axis
question.

## Status

What is validated and what is not:

| | |
|---|---|
| Simulation | nine-stage WarpX PIC validation ladder, every stage gated against a pre-registered, hash-frozen acceptance policy |
| Hardware | one bench experiment, rough vacuum (4–5 Pa), qualitative only |
| Flight cathode | not selected — beam current is *prescribed* in every simulation |
| Magnetic field | field-aligned axis measured (tier M1); transverse B — the actual flight geometry — untested |
| Flight heritage | none |

This is a research repository with a working physics model, not a product.

## Validation

Two simulation trees, one direction of flow:

- `orbit_sims/` computes **what the mission demands** (drag, plasma
  conditions).
- `pic_sims/` answers **whether the device delivers it** (full PIC, WarpX).

Conditions flow one way only: orbit CSV row → frozen `config.yaml` → PIC
verdict. The evidence can never move when the demand changes.

![Ladder and characterization](paper/new/imgs/ladder_characterization.png)

### PIC simulations — the ladder

The ladder builds from a vacuum electron gun up to the full floating
thruster. Each stage isolates one piece of physics and gates it against
theory or a disclosed anchor. All nine stages **PASS**.

| # | stage | what it proves | headline result |
|---|---|---|---|
| 1 | `emitter.negative_cathode` | gun physics vs exact Laplace ramp | potential error 35 µV on 100 V |
| 2 | `emitter.holed_anode` | space charge + geometry control transmission | 0.97 → 0.90 → 1.00 across the three scenarios, as predicted |
| 3 | `emitter.voltage_bracket` | transmission is voltage-independent 200→300 V | spread 0.006 pp |
| 4 | `collector.thermal` | collection vs exact thermal flux | within 1 % of closed form |
| 5 | `collector.biased_3v` | OML collection at +3 V | 0.85 of ceiling, matching Laframboise |
| 6 | `collector.biased_10v` | sheath grows, collected fraction falls | 0.81 of ceiling, sheath 4.1 → 6.9 mm |
| 7 | `collector.floating` | body floats to theoretical potential | −0.251 V, inside the two-model bracket |
| 8 | `capstone.two_node_laplace` | two potentials on one conducting body | exact Laplace, 0.0 V violation |
| 9 | `capstone.floating_body` | **the full device** | φ +16.98 V, escape 98.4 %, **F = 13.65 nN** |

Full digest with every gate: `pic_sims/ladder/LADDER_SUMMARY.md`.

### PIC simulations — characterization

Eight spokes off the 200 V anchor. Each moves **one** physics axis and keeps
everything else verbatim — except the last, which deliberately combines the
two measured axes (voltage × geometry) to test that the laws compose. All
eight **PASS** their gates.

| spoke | axis | result |
|---|---|---|
| `high_thrust` | 300 V | φ 36.3 V, **F 30.13 nN** |
| `350V_400km` | 350 V (the 400 km-enabling drive) | φ 48.3 V — on the 50 V limit, **F 40.48 nN** |
| `350V_400km_slender` | 350 V × slender — the factorial corner | φ 14.0 V (predicted 11–17), **F 43.33 nN**: the laws compose |
| `low_power` | 100 V | φ 5.4 V, F 3.42 nN |
| `slender_body` | elongated body, L/r = 6 | φ 4.4 V, F 14.22 nN |
| `thin_plasma` | density n₀/3 | float unsettled, > 31.6 V bound |
| `magnetized_1x` | axial B = 30 µT (1× LEO) | null — anchor unchanged |
| `magnetized_10x` | axial B = 300 µT | collection tax: φ +33 V, F −11 % |

Details: `pic_sims/characterization/README.md`.

### Orbit simulations

- TudatPy propagation with NRLMSISE-00 drag (real 2024 F10.7/Ap) and
  IRI-2020 plasma along the orbit.
- Drag is cancelled exactly, so the per-row drag force **is** the thrust
  demand.
- Cases: 400 (axial + lateral), 500, 550, 600 km.
- Deliverable: `station_keeping.csv` per case — every row carries pose, drag,
  and `(n_e, Te, Ti)`.

## Scaling to CubeSats

The feasibility condition is close to scale-free: drag grows with the ram
area, collection grows with the skin area, and they cancel. Bigger bodies
just need proportionally more current and power. `SCALING_LAWS.md` §8
estimates a 3U CubeSat at:

| altitude | power |
|---|---|
| 600 km | ~0.9 W |
| 550 km | ~1.7 W |
| 500 km | ~3.4 W |

These are **estimates from an extrapolated collection law, not
measurements** — the extrapolation crosses a regime boundary (risk 4 below).

## Open risks

Ordered by how much they could change the answer.

1. **Transverse magnetic field never simulated.** In LEO the geomagnetic
   field is roughly perpendicular to the thrust axis. The beam gyroradius
   (~1.4 m) is ~50× larger than the simulation domain (30 mm), so the
   committed runs cannot see where the exhaust momentum ends up once the
   beam gyrates. This could move the thrust in either direction.
   See `future_work/M2_TRANSVERSE_B.md`.
2. **No flight cathode chosen.** The bench emitter is a thermionic filament,
   and its heater alone uses ~10× more power than the entire thruster. Only
   a cold cathode (field emission) closes the power budget; its cost,
   lifetime, and atomic-oxygen tolerance are unaddressed.
3. **Only one plasma density measured.** Every committed run uses the same
   dayside row; the density axis of the collection law is theory-only.
4. **CubeSat collection is a regime change.** Committed runs sit at
   r/λ_D ≈ 2.5 (orbit-motion-limited); a CubeSat is tens of Debye lengths
   across, where OML does not apply.
5. **No attitude control in this repository**, yet the mission cases assume
   a held pose.

## Repository map

| document | what it is |
|---|---|
| `CAMPAIGN.md` | the 2026-08 campaign: what was measured, hypotheses and outcomes |
| `SCALING_LAWS.md` | the physics laws, measured constants, scaling to larger vehicles |
| `model/MODEL.md` | the executable model, control law, honest mission table |
| `THESIS.md` | the claim stated for a physics reviewer |
| `OPTIMISTIC_HYPOTHESES.md` | the upside cases, pre-registered and falsifiable |
| `pic_sims/ladder/LADDER_SUMMARY.md` | stage-by-stage verdicts |
| `lab_experiments/electron_gun/` | the bench experiment, with caveats |
| `SETUP.md` | reproducing everything |

## How to run

| tree | conda env |
|---|---|
| `orbit_sims/` | `tudat-sk` |
| `pic_sims/` | `warpx-cpu-mpich-dev` |

```bash
# orbit demand
conda activate tudat-sk
cd orbit_sims && python3 run_station_keeping.py 600km_station_keeping_chipsat

# PIC evidence
conda activate warpx-cpu-mpich-dev
cd pic_sims/ladder && python run_ladder.py --check
```

Note: tests in the warpx env need `PYTHONNOUSERSITE=1`.
