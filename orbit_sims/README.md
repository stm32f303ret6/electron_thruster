# orbit_sims: where the mission demand comes from

A small satellite is propagated with TudatPy while an idealised thruster
fires continuously to cancel drag exactly. Altitude is therefore held, and the
per-row drag force is the thrust a real station-keeping system would have to
supply. Every exported pose is enriched with IRI-2020 electron density and
electron/ion temperature, so the ionosphere the vehicle flies through comes
out alongside the demand it creates.

The deliverable is the CSV. Nothing here knows about thrusters, voltages or
particles. Picking scenario conditions from this CSV and validating them with
particles is the job of `pic_sims/`.

## Environment

```bash
conda activate tudat-sk        # tudatpy 1.0.0, iricore 1.9.0
```

External data this needs, none of it vendored:

| what | where | refresh |
|---|---|---|
| SPICE kernels | Tudat's bundled standard set | `spice.load_standard_kernels()`, automatic |
| Space weather (F10.7/Ap) | `~/.tudat/resource/space_weather/sw19571001.txt` | shipped with Tudat; NRLMSISE-00 reads it |
| IRI solar indices | `<iricore>/data/index/{apf107.dat, ig_rz.dat}` | `python -c "import iricore; iricore.update()"` (needs internet) |

The run refuses to start if the IRI index does not cover the whole mission
span. A year-long propagation that discovers on day 300 that its index file
stopped in month 9 has wasted the whole run.

## Usage

```bash
cd orbit_sims
python3 run_station_keeping.py --list
python3 run_station_keeping.py 400km_station_keeping_chipsat            # full year, ~13 min CPU
python3 run_station_keeping.py 400km_station_keeping_chipsat --days 1   # smoke test, ~2 s
```

Output lands in `validation_cases/<case>/results/`:

- `station_keeping.csv`, the artifact (gitignored; ~10 MB for a year)
- `config_used.yaml`, the fully merged config that produced it (tracked)

`--days N` overrides the duration in both the live config and the raw dict,
so `config_used.yaml` records what actually ran rather than what the file said.

## Physics summary

1. Drag cancel ⇒ `drag_N` ≡ thruster demand. A custom acceleration of
   magnitude `|a_drag|` is applied along the wind-free airspeed direction
   (`v − ω × r`). The exported drag comes from the independently saved
   aerodynamic acceleration norm, not from the cancelling acceleration, so the
   number does not depend on the cancel direction being perfect.
2. Dynamics: EGM96 spherical harmonics (8×8), NRLMSISE-00 aerodynamics,
   Sun/Moon point-mass, cannonball SRP. Sun/Moon and SRP are kept; this port
   dropped the solar power ledger, not the physics.
3. Near-circular setup: a two-body circular speed inserted into the real J2
   field is ~0.07 % too slow at the equator, which would excite a spurious
   ~10 km once-per-orbit altitude breathing and contaminate the drag
   statistics. The initial tangential speed is boosted by the J2 equatorial
   factor.
4. Arcs: monthly arcs chained state-to-state (bounded memory), 60 s fixed
   RKF7(8), decimated to the 300 s CSV grid, seam rows deduplicated.
5. IRI preset `"default"`: the full switch set, which is what enables Te and
   Ti. (The predecessor used `"default_edens"`, which zeroes `jf[1]` and
   returns electron density only.) iricore maps IRI's internal sentinels to
   NaN, so the validity check is `np.isfinite(x) and x > 0`, and a bad value
   raises with the offending pose rather than writing a silent NaN.
6. 120 km floor: the propagation terminates below `orbit.decay_floor_km`,
   which defaults to 120 km. That is also the bottom of IRI's Te/Ti validity
   range, so one guard covers both.

## CSV schema

| column | units | source |
|---|---|---|
| `timestamp_utc` | ISO-8601 UTC | propagation epoch |
| `altitude_km` | km, ellipsoidal WGS-84 | dependent variable |
| `latitude_deg` | deg, geodetic | dependent variable |
| `longitude_deg` | deg east, wrapped to [−180, 180) | dependent variable |
| `electron_density_m3` | m⁻³ | IRI-2020 |
| `electron_temperature_K` | K | IRI-2020 |
| `ion_temperature_K` | K | IRI-2020 |
| `drag_N` | N | mass × aerodynamic acceleration norm |

The environment columns are spacecraft-independent. Because drag is cancelled
the altitude holds, so ρ(t), n_e(t), Te(t) and Ti(t) do not depend on the
vehicle that flew through them. Only `drag_N` carries the geometry. One
13-minute run per altitude therefore serves a whole design space.

The 300 s cadence gives ~19 samples per orbit, which resolves the diurnal
n_e/Te/Ti swing, so day-vs-night design points can be read straight off the
CSV.

## Config schema

Overrides live in `validation_cases/<case>/inputs/config.yaml` and are merged
strictly over `config.py:DEFAULTS`: an unknown key aborts the run instead of
silently doing nothing.

| key | default | meaning |
|---|---|---|
| `mission.start_utc` | `2024-01-01T12:00:00` | 2024 is fully observed → real historical F10.7/Ap, near solar max |
| `mission.duration_days` | 365.0 | |
| `mission.arc_days` | 30.0 | propagation arc length (memory bound) |
| `mission.output_step_s` | 300.0 | CSV cadence; must be an integer multiple of the integration step |
| `mission.integration_step_s` | 60.0 | fixed RKF7(8) step |
| `orbit.initial_altitude_km` | 400.0 | |
| `orbit.inclination_deg` | 0.5 | near-equatorial |
| `orbit.eccentricity` / `raan_deg` / `argp_deg` / `true_anomaly_deg` | 0.0 | |
| `orbit.decay_floor_km` | 120.0 | terminate below this; also the IRI Te/Ti floor |
| `spacecraft.mass_kg` | 0.1 | |
| `spacecraft.cylinder_radius_m` / `cylinder_height_m` | 0.005 / 0.005 | |
| `spacecraft.cd` / `cr` | 2.2 / 1.2 | broadside drag, radiation-pressure coefficient |
| `spacecraft.rotation` | `axial` | `axial` \| `lateral` \| `tumbling` — see below |
| `spacecraft.sigma_t` | 0.9 | tangential momentum accommodation (held poses only) |
| `spacecraft.exospheric_T_K` | 1000.0 | for the most-probable neutral speed in `Cd_side` |
| `spacecraft.mean_mass_amu` | 16.0 | atomic oxygen dominates at 400–700 km |
| `gravity.sh_degree` / `sh_order` | 8 / 8 | EGM96 |

### Rotation semantics

`rotation` sets the drag reference area and is the biggest single lever in the
config.

| rotation | ram silhouette | parallel surface | S_ref @ r = h = 5 mm |
|---|---|---|---|
| `axial` | end cap, πr² | side wall, 2πrh | **8.34e-5 m²** |
| `lateral` | side rectangle, 2rh | both caps, 2πr² | **5.48e-5 m²** |
| `tumbling` | Cauchy mean A_ext/4 | — | **7.85e-5 m²** |

Both held poses fold two drag coefficients into one effective area, because
TudatPy's constant-coefficient aero interface takes a single scalar:

```
rho v²/2 · (Cd·A_ram + Cd_side·A_parallel) = rho v²/2 · Cd · [A_ram + (Cd_side/Cd)·A_parallel]
```

`Cd_side = sigma_t · (v_mp/v_orbit) / sqrt(pi)` ≈ 0.068 for this body at
400 km. A surface edge-on to a hyperthermal flow sees molecules only through
their thermal spread, so the coefficient collapses from ~2.2 broadside to
~0.07. Dropping that term from `lateral` while keeping it in `axial` would
make the two poses an apples-to-oranges comparison (~10 % on this squat body).

A point that surprises people: at r = h the cap disc πr² is larger than the
side rectangle 2rh, so for the squat anchor body broadside is the low-drag
pose. A slender body (h > 1.571·r) reverses it.

## What was left out of the port

Deliberately dropped from the pre-refactor orbit step: the solar power
ledger, the propulsion/calibration blocks, summary gates, plots, and the
IGRF/B-field columns. Cube and box shapes are gone too; one cylinder, three
poses.
