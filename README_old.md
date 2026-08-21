# electron_thruster

**A propellantless electric thruster for small spacecraft, built from a cold
cathode, an HV supply, and the spacecraft's own skin.**

The device emits an electron beam and lets the ionosphere close the circuit.
The escaping beam carries momentum away; the ambient plasma returns the same
current to the vehicle's outer surface, so the net mass flux is zero and there
is nothing to run out of. What that removes from the spacecraft is the point:

> no tank · no propellant · no valves · no feed system · no pressurant · no
> neutralizer

The whole propulsion system is two electrodes and a high-voltage supply.

---

## Why this exists

Most student and small-research satellites fly with **no propulsion at all**,
and the reason is usually not performance. It is that a propellant system
brings a pressure vessel, propellant qualification, loading procedures, and a
launch-safety review that can cost more than the spacecraft and can get a
rideshare slot revoked. Commercial CubeSat electric propulsion starts around
tens of thousands of dollars and tens of watts.

A thruster with no stored propellant and no pressure vessel does not carry that
burden. That is the argument this repository is trying to make good on: not the
highest performance, but the **lowest barrier to actually flying one**.

The trade is real and stated plainly: thrust-per-watt is roughly 0.2 µN/W,
about 200× below a gridded ion engine. That penalty is invisible at nanonewtons
and disqualifying at millinewtons, which is exactly why this device owns the
low end and nothing else does. Energy conversion efficiency is a separate
number and it is good — around 73 %, ion-thruster-class.

## What it does, and what it does not

Measured thrust at the validated operating point is **13.65 nN** (200 V,
0.342 mA, ~68 mW), rising to **30.13 nN** at 300 V and **40.48 nN** at the
350 V top of the measured envelope (43.33 nN on the slender body). Against real
2024 drag (NRLMSISE-00, real F10.7/Ap, solar-cycle-25 maximum) for the
Ø10 mm anchor body:

| case | drag mean | drag max | 13.65 nN covers |
|---|---|---|---|
| 400 km axial | 32.9 nN | 92.4 nN | — |
| 400 km lateral | 21.7 nN | 60.7 nN | — |
| 500 km axial | 7.6 nN | 28.4 nN | mean |
| 550 km axial | 3.9 nN | 16.3 nN | mean (max barely missed) |
| 600 km axial | 2.0 nN | 9.6 nN | mean and max |

**600 km closes at the validated operating point. 550 km is the crossover.
400 km mean demand is covered at the 350 V top of the envelope** — 40.48 nN
(squat, ~81 % duty, float on the 50 V charging limit) and 43.33 nN (slender,
~76 % duty, 14 V float) against the 32.9 nN axial mean; drag maxima
(92.4 nN) and night-side rows keep 400 km a design target, not a closed
case (`model/MODEL.md` §4).

**Larger vehicles.** The feasibility condition is close to scale-free — drag
buys the ram silhouette and collection buys the skin, and both grow as area —
so bigger bodies are not disqualified; they simply need proportionally more
current and power. `SCALING_LAWS.md` §8 works this through and estimates a 3U
CubeSat at ~0.9 W (600 km), ~1.7 W (550 km), ~3.4 W (500 km). **Those are
estimates from an extrapolated collection law, not measurements** — see
"Open risks" below, because the extrapolation crosses a regime boundary.

## Status — read this before believing anything above

| | |
|---|---|
| Simulation | **Nine-stage WarpX PIC validation ladder**, every stage gated against a pre-registered, hash-frozen acceptance policy |
| Hardware | **One bench experiment.** Rough vacuum (4–5 Pa), collector current measured. Qualitative, not calibrated |
| Flight cathode | **Not selected.** Beam current is *prescribed* in every simulation |
| Magnetic field | **Field-aligned axis only** (tier M1, 2026-08-10): axial Bz at 1× LEO leaves the anchor unchanged; 10× costs ~11 % thrust through the float. Transverse B — the actual flight geometry — is still untested |
| Flight heritage | **None** |

This is a research repository with a working physics model, not a product. No
part of it has flown.

## How it works

A cathode sits inside a conducting body, held a fixed supply offset below it,
and fires electrons out through a hole in the lid. The body is not grounded to
anything — it floats, charging positive as the beam leaves, until the ambient
plasma returns exactly as much current as the gun emits. That equilibrium is
the whole device: **the spacecraft's own float potential is the operating
point.**

Thrust is the beam's momentum flux, and it obeys a two-constant law measured
across the full 3× voltage range to ~1 %:

```
F [nN] = c_F · I [mA] · √KE [eV]        c_F  = 3.2675
KE     = κ_KE · (V − φ)                 κ_KE = 0.8063
```

**The device measures its own thrust.** Both `I` (emitted current) and `φ`
(body float potential) are ordinary electrical measurements a cheap
microcontroller can take in flight and continuously. There is no need for a
thrust stand in orbit — thrust is inferred from two numbers the vehicle
already has. The flight control law exploits the same fact: it is a two-line
servo on the measured float, with no ionosphere model and no lookup table,
because density, temperature, day/night, and the vehicle's own draw all
collapse into where the body floats (`model/MODEL.md` §2).

## Open risks

Ordered by how much they could change the answer.

1. **The transverse magnetic field has never been simulated.** The
   field-aligned (axial-Bz) half of the question is now measured — tier M1
   (2026-08-10): at 1× LEO the operating point is unchanged (Δφ +1.2 V,
   ΔF +0.3 %), and at 10× a real collection tax appears (φ +33 V, thrust
   −11 %), entirely through the float. But in LEO the geomagnetic field is
   ~perpendicular to the thrust axis, the beam's gyroradius is ~1.4 m and
   the gyroperiod ~1.2 µs, against a 30 mm simulation domain and an 800 ns
   run — the committed decks are structurally unable to see where the
   emitted momentum ends up once the exhaust gyrates. That far-field
   coupling remains the largest unexamined question in the project and can
   move the thrust in either direction. See `OPTIMISTIC_HYPOTHESES.md` H1
   and `future_work/M2_TRANSVERSE_B.md` (tier M2).
2. **No flight cathode has been chosen.** The bench emitter is a thermionic
   filament, which is a bench convenience only: its heater alone would consume
   an order of magnitude more power than the entire thruster. A cold cathode
   (field emission) is the only class that closes the power budget, and its
   cost, lifetime, and atomic-oxygen tolerance are unaddressed.
3. **Only one plasma density has ever been measured.** Every committed run
   uses the same dayside row. The density axis of the collection law is
   theory-only, which is why most rows that *close* are flagged as
   extrapolation in `model/MODEL.md` §5.
4. **CubeSat-scale collection is a regime change, not an extrapolation.**
   Every committed run sits at `r/λ_D ≈ 2.5`, where orbital-motion-limited
   collection applies. A CubeSat is tens of Debye lengths across, where it
   does not. `SCALING_LAWS.md` §8 states this and labels the CubeSat floats an
   estimate rather than a calibration.
5. **Attitude control does not exist in this repository** — no actuator,
   sensor, mass, or power budget — yet the mission cases assume a held pose.

`pic_sims/ladder/capstone/2_chipsat_thruster/VALIDATION_GAPS.md`
audits the simulation's own gaps (G1–G11) in the same spirit.

---

## The evidence

Two trees, one direction of flow. Nothing points backwards.

```
orbit_sims/    what the mission demands   →   pic_sims/    does it actually do that?
   TudatPy + NRLMSISE-00 + IRI-2020              WarpX PIC validation ladder
   env: tudat-sk                                  env: warpx-cpu-mpich-dev
   deliverable: station_keeping.csv               deliverable: a suite verdict
```

**`orbit_sims/` — the demand side.** Propagates the vehicle with drag cancelled
exactly, so altitude is held and the per-row drag force **is** the thrust
demand. Every exported pose carries IRI-2020 `(n_e, Te, Ti)`. Reads nothing
from the other tree.

```bash
conda activate tudat-sk
cd orbit_sims && python3 run_station_keeping.py 400km_station_keeping_chipsat
# → orbit_sims/validation_cases/<case>/results/station_keeping.csv
```

**`pic_sims/` — the evidence.** The WarpX ladder builds from a vacuum electron
gun up to the full floating thruster, each stage with its own committed
acceptance policy. **Self-contained by design:** a stage never imports
`orbit_sims`. Scenario conditions are read off the orbit CSV by inspection and
frozen into the stage's own `config.yaml` before the run.

```bash
conda activate warpx-cpu-mpich-dev
cd pic_sims/ladder && python run_ladder.py --check
```

**Why the dependency is one-way.** The ladder is the evidence, so it must not
be able to move when the demand changes. The provenance chain runs orbit CSV
row (sha + timestamp) → frozen `(V, I)` and plasma conditions → PIC verdict
(policy sha), and never the other way.

## Where to read next

| document | what it is |
|---|---|
| `CAMPAIGN.md` | the 2026-08 campaign end to end: what was measured, the pre-registered hypotheses and how each resolved |
| `SCALING_LAWS.md` | the physics laws, their measured constants, and the scaling to larger vehicles (§8) |
| `model/MODEL.md` | the executable model, the flight control law, and the honest mission table |
| `THESIS.md` | the claim stated for a physics reviewer, with the objections and measured answers |
| `SETUP.md` | reproducing everything: environments, WarpX build flags, how to run |
| `OPTIMISTIC_HYPOTHESES.md` | the upside cases, pre-registered and falsifiable (external review) |
| `pic_sims/ladder/LADDER_SUMMARY.md` | stage-by-stage verdict |
| `lab_experiments/electron_gun/` | the bench experiment, with its caveats |

## Environments

| tree | conda env | why |
|---|---|---|
| `orbit_sims/` | `tudat-sk` | tudatpy 1.0.0, iricore 1.9.0 |
| `pic_sims/` | `warpx-cpu-mpich-dev` | WarpX + pyAMReX |

Tests in the warpx env need `PYTHONNOUSERSITE=1` (a broken user-site `dash`
pytest plugin otherwise gets picked up).
