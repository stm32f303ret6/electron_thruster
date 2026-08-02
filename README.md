# electron_thruster — chipsat station keeping, end to end

Three trees, one direction of flow. Nothing points backwards.

```
orbit_sims/    what the mission demands   →   design_sims/   what to run it at   →   pic_sims/    does it actually do that?
   TudatPy + NRLMSISE-00 + IRI-2020            0-D laws + operating-point solver        WarpX PIC validation ladder
   env: tudat-sk                               env: either                              env: warpx-cpu-mpich-dev
   deliverable: station_keeping.csv            deliverable: scenario blocks + laws.yaml  deliverable: a suite verdict
```

## The three trees

### `orbit_sims/` — the demand side

Propagates a chipsat at 400 km with drag cancelled exactly, so altitude is held
and the per-row drag force **is** the thrust demand. Enriches every exported
pose with IRI-2020 `(n_e, Te, Ti)`. Reads nothing from the other two trees.

```bash
conda activate tudat-sk
cd orbit_sims && python3 run_station_keeping.py 400km_station_keeping_chipsat
```

→ `orbit_sims/validation_cases/<case>/results/station_keeping.csv`

### `design_sims/` — the operating point

Turns a mission row `(n_e, Te, Ti, drag_N)` into a cathode voltage and a beam
current, using 0-D laws whose constants are anchored to **committed PIC
measurements** in this repo. Reads the orbit CSV and `pic_sims/`'s committed
`reference_results/*/metrics.json`. It is the only writer of
`design_sims/calibration/`.

```bash
cd design_sims && python3 operating_point.py --csv ../orbit_sims/.../station_keeping.csv
```

### `pic_sims/` — the evidence

The WarpX validation ladder: eight (now nine) stages, each with a committed
acceptance policy, that build from a vacuum electron gun up to the full floating
chipsat thruster. **Self-contained by design** — a stage never imports
`design_sims` or `orbit_sims`; design constants arrive frozen in the stage's own
committed `config.yaml`.

```bash
conda activate warpx-cpu-mpich-dev
cd pic_sims/validation_cases && python run_ladder.py --check
```

See `pic_sims/validation_cases/README.md` for the ladder contract and
`LADDER_SUMMARY.md` for the current stage-by-stage verdict.

## Why the dependency direction is one-way

The ladder is the *evidence*, so it must not be able to move when the design
model moves. A stage that imported the live `laws.yaml` would silently
re-validate itself against whatever the model currently believes. Instead:

1. `design_sims` picks an operating point and **freezes** it — constants,
   predictions and row provenance — into the stage's `config.yaml`, committed
   *before* the run (pre-registration).
2. The stage runs the PIC deck against that frozen block and gates the
   prediction against the measurement.
3. Only after a PASS does the measurement flow *back* into
   `design_sims/calibration/runs/`, and any refit of `laws.yaml` invalidates the
   stage policy — which then needs a new version and fresh runs.

The provenance chain is machine-checkable end to end: orbit CSV row (sha +
timestamp) → `laws.yaml` constant (anchored to an in-tree `metrics.json` + sha)
→ frozen `(V, I)` + predictions → PIC verdict (policy sha) → promotion.

## Environments

| tree | conda env | why |
|---|---|---|
| `orbit_sims/` | `tudat-sk` | tudatpy 1.0.0, iricore 1.9.0 |
| `design_sims/` | either | numpy + PyYAML + matplotlib only |
| `pic_sims/` | `warpx-cpu-mpich-dev` | WarpX + pyAMReX |

Tests in the warpx env need `PYTHONNOUSERSITE=1` (a broken user-site `dash`
pytest plugin otherwise gets picked up).
