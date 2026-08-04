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
