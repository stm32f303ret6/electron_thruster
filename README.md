# electron_thruster — chipsat station keeping, end to end

Two trees, one direction of flow. Nothing points backwards.

```
orbit_sims/    what the mission demands   →   pic_sims/    does it actually do that?
   TudatPy + NRLMSISE-00 + IRI-2020              WarpX PIC validation ladder
   env: tudat-sk                                  env: warpx-cpu-mpich-dev
   deliverable: station_keeping.csv               deliverable: a suite verdict
```

## The two trees

### `orbit_sims/` — the demand side

Propagates a chipsat at 400 km with drag cancelled exactly, so altitude is held
and the per-row drag force **is** the thrust demand. Enriches every exported
pose with IRI-2020 `(n_e, Te, Ti)`. Reads nothing from the other tree.

```bash
conda activate tudat-sk
cd orbit_sims && python3 run_station_keeping.py 400km_station_keeping_chipsat
```

→ `orbit_sims/validation_cases/<case>/results/station_keeping.csv`

#### The altitude sweep (2024, real F10.7/Ap, 5 mm chipsat)

Five committed cases bracket the feasibility envelope against the PIC-measured
thrust of **13.65 nN** (200 V, 0.342 mA, `capstone.floating_body`):

| case | drag mean | drag max | 13.65 nN covers |
|---|---|---|---|
| 400 km axial | 32.9 nN | 92.4 nN | — |
| 400 km lateral | 21.7 nN | 60.7 nN | — |
| 500 km axial | 7.6 nN | 28.4 nN | mean |
| 550 km axial | 3.9 nN | 16.3 nN | mean (max barely missed) |
| 600 km axial | 2.0 nN | 9.6 nN | mean and max |

**600 km closes at the validated operating point; 550 km is the crossover.**
`capstone.high_thrust` (the 300 V ceiling, ~30 nN predicted) probes whether
the 500 km worst case and the lower altitudes come into reach.

### `pic_sims/` — the evidence

The WarpX validation ladder: eight (now nine) stages, each with a committed
acceptance policy, that build from a vacuum electron gun up to the full floating
chipsat thruster. **Self-contained by design** — a stage never imports
`orbit_sims`; PIC scenario conditions (plasma, voltage, current) are chosen by
inspecting the orbit CSV and frozen in the stage's own committed `config.yaml`.

```bash
conda activate warpx-cpu-mpich-dev
cd pic_sims/validation_cases && python run_ladder.py --check
```

**Start here:**

- **`CAMPAIGN.md`** — the 2026-08 simulation campaign end to end: what was
  measured, the three pre-registered hypotheses and how each resolved, the
  code and contract changes, and what it all implies.
- **`SETUP.md`** — reproducing it: conda environments, the WarpX version and
  build flags, how to run the ladder and the variant runs.

See `pic_sims/validation_cases/README.md` for the ladder contract and
`LADDER_SUMMARY.md` for the current stage-by-stage verdict.

## Why the dependency direction is one-way

The ladder is the *evidence*, so it must not be able to move when the demand
changes. Scenario conditions are picked from the orbit CSV by inspection
(best/worst case corners: high-drag dense plasma, low-density thin plasma) and
frozen into the stage's `config.yaml` before the run. The PIC stage runs against
that frozen block and gates its own measurements.

The provenance chain is: orbit CSV row (sha + timestamp) → frozen `(V, I)` +
plasma conditions → PIC verdict (policy sha).

## Environments

| tree | conda env | why |
|---|---|---|
| `orbit_sims/` | `tudat-sk` | tudatpy 1.0.0, iricore 1.9.0 |
| `pic_sims/` | `warpx-cpu-mpich-dev` | WarpX + pyAMReX |

Tests in the warpx env need `PYTHONNOUSERSITE=1` (a broken user-site `dash`
pytest plugin otherwise gets picked up).
