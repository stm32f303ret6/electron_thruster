# Three-stage ChipSat validation suite

## Summary

Build a consistent validation ladder under `electron_thruster_xd/validation_cases`:

1. `negative_cathode`: electron-gun validation.
2. `current_collection`: generic spherical collector benchmark with 0 V, +3 V, and +10 V cases.
3. `chipsat`: integrated 5 mm ChipSat capstone port.

Abandon the cylindrical OML case: its lateral-only theoretical current would not validate the
caps-only hardware, and finite-cylinder ends introduce a different problem. The sphere will
instead be an intentionally generic numerical/theory benchmark. This follows the small-probe
spherical OML regime described in the
[NASA Langmuir-probe review](https://ntrs.nasa.gov/citations/20090025959); the finite-cylinder
mismatch is documented by
[Marholm and Marchand](https://journals.aps.org/prresearch/abstract/10.1103/PhysRevResearch.2.023016).

The implementation task is coding-only. Do not run WarpX, initialize a GPU context, or launch
any simulation while carrying out this plan.

## Common structure and interfaces

- Give every project the same user-facing shell:
  - `README.md`
  - `inputs/*.yaml`
  - `run_<case>.py`
  - `analyze_<case>.py`
  - `animate_<case>.py`
  - runtime-only `outputs/` and `results/`
- Keep all editable physics, numerical, path, visualization, and acceptance values in YAML.
- Resolve paths from each script's location and write `config_used.yaml` only after a successful
  run.
- Keep helpers local to their project; do not introduce a shared framework.
- Add a short `validation_cases/README.md` explaining the three-stage validation ladder.
- Analysis scripts must write human-readable plots/CSVs plus a JSON verdict and exit nonzero on
  failed gates.
- Replace the two legacy `current_collection` scripts rather than retaining two competing
  interfaces.

Public commands:

```bash
python run_negative_cathode.py
python analyze_negative_cathode.py
python animate_negative_cathode.py

python run_current_collection.py thermal_flux
python run_current_collection.py oml_3v
python run_current_collection.py oml_10v
python analyze_current_collection.py
python animate_current_collection.py

python run_chipsat.py
python analyze_chipsat.py
python animate_chipsat.py
```

Each command is run from its project directory. Generated diagnostics and results remain
untracked.

## Implementation changes

### 1. Negative cathode

- Preserve the existing simulation and plots.
- Add YAML-backed executable gates matching its documented reference:
  - collector current within 0.1% of 10 µA;
  - arrival energy `99.3 ± 0.5 eV`;
  - zero cathode and radial-wall hits;
  - midplane potential `-50.7 ± 1 V`;
  - particle-budget closure below 0.1%.
- Store the thresholds in a `validation` section of the input YAML, copy them into the completed
  run snapshot, include individual checks in the summary JSON, and return exit status 1 if any
  gate fails.

### 2. Three-case spherical current collection

Replace the old probe scripts with:

- `inputs/thermal_flux.yaml`
- `inputs/oml_3v.yaml`
- `inputs/oml_10v.yaml`
- `run_current_collection.py`
- `analyze_current_collection.py`
- `animate_current_collection.py`
- a README and only the small local helpers needed to keep those entry points readable.

All three YAML files use the same collisionless, unmagnetized, zero-drift Maxwellian plasma and
numerics:

- `n0 = 1.627e12 m^-3`, `Te = 1318.8 K`, `Ti = 936.2 K`, `mi = 400 me`;
- sphere radius `a = 0.360 mm`;
- `lambda_De = 1.96472 mm`, hence `a/lambda_De = 0.1832 < 0.2`;
- the full spherical embedded-boundary surface is the only collection surface;
- initialize a bulk Maxwellian and inject the analytic one-sided Maxwellian flux at `r_hi`,
  `z_lo`, and `z_hi`;
- do not use the ChipSat scrape/recycle callback in this analytic benchmark;
- `dr = dz = 30 micrometers`, grid `512 x 1024`;
- domain `r = [0, 15.36] mm`, `z = [-15.36, 15.36] mm`;
- `dt = 6.0e-12 s`, 600,000 steps, `t_end = 3.6 microseconds`;
- 8 bulk macroparticles per cell per species and random seed 42;
- field and scrape diagnostics every 5,000 steps;
- reduced diagnostics every 500 steps;
- far-field particle moments every 50,000 steps;
- no checkpoint/restart support.

Only `case_name`, final bias, and output/result paths may differ between the three configurations.
The loader must reject unknown keys and verify that the common configuration fingerprint is
identical across all three files.

#### Bias protocol

- Every run starts with the sphere pinned at 0 V relative to the grounded far-field plasma.
- At step 100,000 (`t_bias = 0.6 microseconds`), use the native time-dependent embedded-boundary
  expression to step to 0, +3, or +10 V.
- Generate the expression with numeric literals, equivalent to
  `if(t < 6.0e-7, 0.0, final_bias)`, avoiding a per-step Python potential callback.
- Use the same expression shape for the 0 V case so all three pre-bias execution paths remain
  identical.

#### Analytic targets

For `A = 4*pi*a^2 = 1.6286016316e-6 m^2`, compute targets from the configuration rather than
hard-coding them in the analyzer:

```text
I_e,thermal = n0 * e * A * sqrt(k*Te / (2*pi*me))
I_e,OML(V)  = I_e,thermal * (1 + e*V/(k*Te))
```

Expected values for the committed defaults:

| Case | Bias after the step | Electron-current target |
|---|---:|---:|
| `thermal_flux` | 0 V | `0.023944705 microampere` |
| `oml_3v` | +3 V | `0.656034702 microampere` |
| `oml_10v` | +10 V | `2.130911363 microampere` |

The corresponding attracted-current multipliers are `1`, `27.3979029`, and `88.9930097`.
The biased ion currents predicted by the repelled-species exponential are effectively zero; do
not use relative-error gates against those tiny values.

#### Current and plasma acceptance

- Bin only particles scraped at the spherical embedded boundary, using their actual scrape
  times. Do not count particles lost at outer domain boundaries.
- Discard startup data before `t = 0.6 microseconds` in the all-zero-bias run.
- For `thermal_flux`, average electron collection over `0.6-3.6 microseconds`, require agreement
  with thermal theory within 5%, and require the two equal-duration halves to differ by less than
  5%.
- Report the 0 V ion thermal current and block uncertainty but do not fail the run on its noisy
  approximately 1.01 nA signal.
- For the biased cases, use `tau = t - t_bias` and:
  - retain `tau = 0-1.8 microseconds` as the sheath transient;
  - compare current stability over `tau = 1.8-2.4` and `2.4-3.0 microseconds`;
  - use `tau = 2.4-3.0 microseconds` for the final OML current;
  - require stability and absolute OML agreement within 5%;
  - require `I_bias/I_thermal` to match `1 + eV/(kTe)` within 5%, using the dedicated
    `thermal_flux` result;
  - require late biased ion current to be less than 1% of electron current.
- Estimate uncertainty from independent time-block means rather than treating adjacent scrape
  bins as independent samples.
- In every case require:
  - far-field electron and ion densities within 5% of nominal;
  - electron and ion temperatures within 3% of nominal;
  - electron-temperature anisotropy below 3%;
  - far-field quasineutrality error below 2%;
  - far-field plasma potential within `0.05*kTe/e = 5.68 mV` of zero.

#### Sheath diagnostics

- Build volume-weighted spherical profiles using the RZ cell-volume factor
  `2*pi*r*dr*dz`.
- Use radial bins `2*dx = 60 micrometers` wide, exclude the embedded boundary and first two
  exterior cells, and smooth density profiles over approximately `0.25*lambda_De`.
- Track two definitions at every field snapshot:
  - potential edge `r_phi`: the first bin outside the outermost location satisfying
    `e*abs(phi-phi_inf)/(k*Te) > 1`;
  - quasineutral edge `r_qn`: the first bin outside the outermost location satisfying
    `abs(ni-ne)/n_inf > 0.05`.
- If neither threshold is exceeded, record `r_edge = a`, meaning zero sheath thickness.
- Average final profiles over `tau = 2.7-3.0 microseconds`.
- Compare edge averages over `tau = 2.4-2.7` and `2.7-3.0 microseconds`; require changes no
  larger than `max(0.1*lambda_De, 0.1*(r_edge-a))`.
- Require both final edges to remain at least `2*lambda_De` inside the nearest domain wall.
- In a shell one Debye length inside each open boundary, require
  `e*abs(phi)/(k*Te) < 0.1` and charge imbalance below 5%.
- Treat sheath size as a measured result, not as an OML theory pass/fail quantity.

Produce:

- per-case current histories with theory and analysis windows;
- final potential, electron-density, ion-density, and charge-imbalance maps;
- a combined measured/theory current-ratio plot at 0, 3, and 10 V;
- overlaid final radial profiles of normalized potential, `ne/n0`, and `ni/n0`;
- histories of `(r_phi-a)/lambda_De` and `(r_qn-a)/lambda_De` against `tau`;
- one synchronized `2 x 3` animation:
  - columns: 0 V, +3 V, +10 V;
  - top row: normalized positive potential;
  - bottom row: `(ni-ne)/n0` with common clipped limits;
  - sphere and both sheath-edge circles overlaid;
  - approximately 0.3 microseconds of prelude and all 3 microseconds after the step.

Write individual results under `results/<case>/`, cross-case artifacts under
`results/comparison/`, and a consolidated JSON verdict. The analyzer and animator require all
three successful `config_used.yaml` snapshots and must report missing cases explicitly.

### 3. Integrated ChipSat

Create `validation_cases/chipsat` from the validated 5 mm capstone in `electron_contactor`, not
from the newer 25 mm femtosat campaign.

Retain:

- the RZ can, wall, perforated lid, floor annulus, aperture, and cathode geometry;
- body/cathode embedded-boundary potentials;
- 200 V cathode offset and 0.342 mA emitted beam;
- capstone plasma `n0 = 1.627e12 m^-3`, `Te = 1318.8 K`, `Ti = 936.2 K`, and
  `mi = 400 me`;
- initial self-capacitance calibration;
- floating-body charge pump and dynamic cathode potential;
- beam and ambient electron/ion scrape accounting;
- the ambient scrape/recycle reservoir required to avoid domain depletion;
- the validated `200 x 440`, `0.15 mm` grid and 800 ns/159,168-step run;
- beam fate, current balance, exhaust energy, body potential, and thrust diagnostics.

Remove:

- passive-probe/OML mode from the integrated case;
- magnetic field, ram drift, and shroud campaigns;
- parameter sweeps, collation, paper-generation, mission/orbit tools, and old result data;
- checkpoint/restart and automatic checkpoint pruning;
- unused configuration branches and experiment tags.

Keep the implementation explicit through small local helpers for configuration, geometry,
floating-body state, diagnostics, and ambient refill. The public shell remains the same five-part
structure as the other cases.

#### Lateral-wall proxy

- Preserve the source project's behavior: all ambient particles scraped by any ChipSat embedded
  boundary contribute to the floating charge pump, including hits on the cylindrical wall.
- State prominently in the README that this is an optimistic source-model proxy and not a
  caps-only hardware collection model.
- Extend diagnostics without changing physics to report ambient electron and ion collection
  separately for:
  - lateral wall;
  - lid;
  - body floor annulus;
  - cathode.
- Assert that the classified regional sums reproduce the all-EB charge-pump totals within
  numerical precision.

#### Integrated acceptance

Preserve the capstone's existing steady-state gates:

- beam escape fraction at least 95%;
- `F_beam = 13.6 nN ±15%`;
- floating body potential `16 ± 4 V`;
- current-balance error at most 5%;
- `abs(F_net) <= F_beam`.

Report, but do not add unsupported gates for, the reference exhaust energy of approximately
147 eV and the new per-surface ambient collection fractions.

## Coding-only verification

Do not execute any simulation as part of implementation. In particular, do not call
`sim.step()`, initialize WarpX for a deck check, or run GPU/CPU PIC tests.

Safe verification is limited to:

- Python syntax compilation and import checks that keep `pywarpx` lazy;
- loading every YAML and exercising configuration validation;
- checking the three current-collection configurations differ only in allowed fields;
- pure-Python assertions for the thermal and OML target values;
- checks for `a/lambda_De`, worst-case particle displacement per timestep, grid snapping, and
  timing/cadence alignment;
- unit tests of current binning, block statistics, spherical averaging, sheath-edge detection,
  and verdict exit logic using synthetic arrays;
- synthetic-point tests that ChipSat geometry masks are disjoint and exhaustive;
- pure-Python tests of charge-pump signs, reservoir bookkeeping, regional-current summation,
  and analysis gates;
- confirmation that generated output directories remain untracked.

Simulation-based acceptance is intentionally deferred until the user later has an available GPU.

## Fixed assumptions

- All stated sphere biases are relative to the far-field plasma potential, fixed at 0 V.
- The spherical case validates ambient injection, embedded-boundary collection, spherical OML
  response, and qualitative sheath evolution; it is not a geometric model of the ChipSat caps.
- The reduced ion mass of `400 me` is retained for consistency with the validated capstone and
  must be documented as a limitation for ion-timescale conclusions.
- The integrated ChipSat intentionally preserves the existing all-surface collection proxy; no
  caps-only boundary behavior is introduced in this work.
- No WarpX source files, generated checksum files, or unrelated project files are modified.
