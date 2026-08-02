# Validation Ladder Architecture Refactor

## Status

This document is the implementation specification for refactoring the
validation cases. It is intentionally explicit so that a future developer or AI
agent can implement the refactor without redesigning the architecture.

The two central decisions are:

> 1. Each validation stage is a self-contained folder with its own complete
>    PIC simulation script, configuration, physics helpers, analysis,
>    animation, and tests. Physics duplication between stages is deliberate:
>    a reviewer must be able to read one folder and see the whole model.
>
> 2. The non-physics plumbing — run IDs, manifests, state transitions, strict
>    JSON, gate evaluation — lives in ONE small shared module,
>    `validation_cases/ladder_contract.py`. It contains no physics, no
>    `pywarpx`, and no plotting. Duplicating physics aids inspection;
>    duplicating infrastructure just means fixing every lifecycle bug five
>    times.

The repository-wide ladder remains small orchestration around the stage
folders. It launches stages as subprocesses and never imports their WarpX
simulation modules (libwarpx cannot be initialized twice in one process).

Guiding rule throughout: **prefer the simplest mechanism that closes a real,
observed bug.** Do not add provenance or policy machinery speculatively.

---

## 1. Goals

1. Preserve the existing staged validation ladder.
2. Make every simulation understandable by reading one folder.
3. Keep every stage independently executable and archivable.
4. Put all PICMI/WarpX construction for a stage in one `simulation.py`.
5. Make validation fail closed: missing evidence can never produce PASS.
6. Prevent stale or partial outputs from being mixed or reused.
7. Separate physical/numerical configuration from acceptance policy.
8. Record enough provenance to reproduce any published result: config hash,
   git commit, seed, versions, frozen config copy.
9. Turn the cross-stage expectations into executable ladder checks.

## 2. Non-goals

This refactor must **not**:

- create a shared simulation framework — `ladder_contract.py` is the only
  shared code, and it must stay free of physics, PICMI, and I/O of scientific
  data;
- create a plugin or dynamic-import system for cases;
- make one stage import Python code from another stage;
- change physical parameters or analytical references during the structural
  migration (Phases 0-4);
- treat committed reference files as completion markers for local runs;
- hide simulation choices behind inheritance or metaprogramming.

Explicitly **deferred, not planned** (add later only if a concrete need
appears, e.g. publishing validation claims to third parties):

- preregistered suite plans and policy-hash enforcement before runs;
- separate cohort manifests and cohort IDs;
- a separate `execution.yaml` (observed runtime settings go in the run
  manifest instead);
- checksumming large raw HDF5/BP artifacts;
- checkpoint/restart of interrupted runs — an interrupted run is FAILED and is
  rerun from scratch. This is a stated trade-off, not an omission.

Phases 0-4 preserve physical calculations, statistical definitions, and
numeric tolerances. They may change only integrity semantics needed to stop a
false PASS (missing-evidence handling, immutable run directories, strict
JSON). Corrections that alter a scientific metric, reference, or tolerance
belong to Phase 5.

---

## 3. Terminology

- **Stage**: one rung of the validation ladder; one self-contained directory.
- **Run**: one immutable execution of one stage (and, when applicable, one
  named scenario). Identified by a **run ID**.
- **Analysis**: one immutable interpretation of one run (or an explicit list
  of runs) under one acceptance policy. Identified by an **analysis ID**.
  Re-analysis never overwrites an earlier analysis.
- **Acceptance policy**: metrics and tolerances used to judge a completed run.
  Never affects the PIC evolution.
- **Reference result**: a curated, committed result for comparison. Never
  causes a runner to skip execution.

---

## 4. Ladder topology

The ladder is a directed acyclic graph:

```text
emitter.negative_cathode        collector.thermal
          |                              |
          v                              v
emitter.holed_anode             collector.biased_3v
          |                              |
          |                              v
          |                     collector.biased_10v
          |                              |
          +---------> capstone.floating_body <--+
```

| Stage ID | Directory | Depends on | Evidence kind |
|---|---|---|---|
| `emitter.negative_cathode` | `electron_gun/1_negative_cathode` | none | analytic verification + regression |
| `emitter.holed_anode` | `electron_gun/2_electron_gun` | `emitter.negative_cathode` | mechanism regression |
| `collector.thermal` | `current_collection/1_thermal` | none | analytic verification |
| `collector.biased_3v` | `current_collection/2_biased_3v` | `collector.thermal` | numerical sanity |
| `collector.biased_10v` | `current_collection/3_biased_10v` | `collector.biased_3v` | numerical sanity / sheath containment |
| `capstone.floating_body` | `capstone/2_floating_body` (was `chipsat`) | branch tips | system integration |

Evidence kinds must be explicit in each `acceptance.yaml`. An OML upper-bound
sanity check must not be described as an exact analytic validation.

---

## 5. Directory contract

### 5.1 Repository root

```text
validation_cases/
|-- ladder_contract.py         # shared plumbing (section 7); unit-tested once
|-- ladder.py                  # literal stage list (section 11)
|-- run_ladder.py              # subprocess orchestration + cross-stage checks
|-- tests/                     # contract + ladder tests
|-- suite_results/             # generated, ignored by Git
`-- <stage directories>
```

### 5.2 Every stage

```text
<stage>/
|-- README.md
|-- config.yaml                # physics/numerics; root level, no inputs/ dir
|-- acceptance.yaml            # gates and tolerances
|-- simulation.py
|-- helpers.py                 # stage-local physics/config code only
|-- analyze.py
|-- animate.py                 # optional
|-- tests/
|   |-- test_helpers.py
|   `-- test_analysis.py       # small synthetic fixtures only
|-- outputs/                   # generated, ignored by Git
|   `-- <run-id>/
|       |-- manifest.json
|       |-- config_used.yaml   # frozen effective config
|       |-- sources_used/      # copies of simulation.py, helpers.py
|       |-- run.log
|       `-- diags/
|-- results/                   # generated, ignored by Git
|   `-- <run-id>/
|       `-- <analysis-id>/
|           |-- analysis_manifest.json
|           |-- acceptance_used.yaml
|           |-- metrics.json
|           |-- verdict.json
|           |-- current.csv
|           `-- figures/
`-- reference_results/         # curated small artifacts, committed
```

The `inputs/` subdirectories are removed during migration; `config.yaml`
lives at the stage root.

Stages may import `ladder_contract` (and nothing else outside their folder):

```python
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from ladder_contract import begin_run, complete_run, ...
```

Two lines of `sys.path` at the top of `simulation.py` and `analyze.py` are the
whole import mechanism. No packaging, no plugins.

---

## 6. File responsibilities

### 6.1 `simulation.py`

The complete PIC simulation definition. A physicist opens this file and sees
the entire WarpX model: grid, boundaries, solver, embedded boundaries,
species, injection, diagnostics, stepping.

```python
def build_grid(cfg): ...
def build_solver(cfg, grid): ...
def build_embedded_boundary(cfg): ...
def build_species(cfg, grid): ...
def add_diagnostics(sim, cfg, run): ...
def build_simulation(cfg, run): ...


def main() -> int:
    args = parse_args()                      # --config, --scenario
    cfg = load_config(args.config, scenario=args.scenario)   # helpers.py
    run = begin_run(cfg)                     # ladder_contract
    print(f"RUN_ID={run.run_id}", flush=True)
    try:
        sim = build_simulation(cfg, run)
        sim.step(cfg.numerics.max_steps)
        complete_run(run, cfg)               # verifies artifacts, then COMPLETE
    except BaseException as exc:
        fail_run(run, exc)
        raise
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

Functions may be merged when a stage is small; the constraint is that the PIC
code stays in this one file. CLI: `simulation.py [--config PATH]
[--scenario NAME]`. Defaults resolve relative to the stage directory, not the
caller's CWD.

For the multi-scenario electron gun, `--scenario NAME` runs exactly one
scenario per process. Each scenario execution is a separate immutable run
whose `config_used.yaml` contains only the effective physics of that
scenario; the manifest also records the hash of the full source study YAML so
scenario runs can later be checked for compatibility.

### 6.2 `helpers.py`

Stage-local physics and configuration code, small and unit-testable:

- typed configuration dataclasses; YAML loading and validation
  (`yaml.safe_load`, reject unknown keys, missing keys, non-finite numbers,
  invalid geometry, incompatible cadences);
- dimensional and geometric invariants (CFL, plasma frequency, emission
  radius inside domain, source plane in a regular cell, `dr` vs `dz` faces);
- analytical formulas used by that stage.

It must NOT contain: `pywarpx` imports, PICMI objects, matplotlib, run/state
lifecycle code (that is `ladder_contract`), or imports from another stage.

### 6.3 `analyze.py`

Scientific interpretation of completed evidence:

- verify the run is COMPLETE before reading anything;
- read openPMD and reduced diagnostics;
- build the complete expected diagnostic time grid (section 10);
- compute currents, energies, fields, densities, sheath sizes;
- evaluate every gate; write `metrics.json`, `verdict.json`, CSVs, plots.

```python
def main() -> int:
    args = parse_args()          # (--run ID | --runs ID...) --policy PATH
    evidence = load_complete_runs(args)      # ladder_contract; ERROR if not COMPLETE
    configs = load_frozen_configs(evidence)  # config_used.yaml, never live config.yaml
    policy = load_policy(args.policy)
    analysis = begin_analysis(evidence, policy)
    print(f"ANALYSIS_ID={analysis.analysis_id}", flush=True)
    try:
        data = read_diagnostics(evidence, configs)
        metrics = compute_metrics(data, configs)
        gates = evaluate_gates(metrics, policy)   # ladder_contract
        verdict = write_results(analysis, metrics, gates)
        complete_analysis(analysis, verdict)
        return verdict.exit_code
    except SystemExit:
        raise
    except BaseException as exc:
        fail_analysis(analysis, exc)
        return 2                 # analysis error — never exit 1 via traceback,
                                 # exit 1 is reserved for "gates failed"
```

Analysis always loads the frozen `config_used.yaml` from the selected runs,
never the stage's current `config.yaml`. The policy path is explicit; there
is no implicit "latest". Metrics are computed before plotting; a figure is
never the only record of a gate measurement.

For a multi-run stage, `--runs A B C` verifies before analyzing that all
members are COMPLETE, share the stage ID and source-study hash, and that each
required scenario appears exactly once. The analysis manifest records the
member run IDs and their manifest hashes — that IS the cohort record; no
separate cohort directory or lifecycle exists.

### 6.4 `animate.py`

Presentation only. Reads explicitly selected COMPLETE evidence, never writes
into a run or analysis directory, never contains gate logic.

### 6.5 `README.md`

Each stage README states: the physical system; included and excluded physics;
boundary conditions; references; what the stage proves and does not prove;
upstream dependencies; run cost; commands; gate definitions with tolerance
rationale; known numerical limitations. Observed values must be clearly
separated from pre-run predictions.

---

## 7. `ladder_contract.py`

One file, roughly 200-400 lines, unit-tested once at the root. It owns:

- canonical serialization and SHA-256 hashing of config dicts;
- run ID and analysis ID generation;
- exclusive directory creation (`exist_ok=False`; on collision, new
  timestamp);
- run and analysis manifest reading/writing with state transitions;
- atomic JSON publication (write temp file, flush, `os.replace`);
- strict JSON (`allow_nan=False`; reject NaN/Inf on read);
- `Metric`, `Gate`, `Verdict` dataclasses and `evaluate_gates()` with the
  fail-closed rules of section 9;
- artifact presence/size verification for `complete_run`.

It must never import `pywarpx`, PICMI, matplotlib, or openPMD readers, and it
must never contain a physical formula. If someone proposes adding physics to
it, the answer is no — that code belongs in a stage's `helpers.py`.

---

## 8. Immutable run lifecycle

### 8.1 Run ID

```text
20260801T183045Z_a81d19c2
```

UTC timestamp plus the first eight hex characters of the canonical SHA-256 of
the effective config. A scenario name may be inserted before the hash.

### 8.2 State transitions

```text
NEW -> RUNNING -> COMPLETE | FAILED | INVALID
```

- `RUNNING` is written before WarpX initializes.
- `FAILED`: the process raised or exited unsuccessfully.
- `INVALID`: WarpX returned but required artifacts or the final iteration are
  missing or inconsistent.
- `COMPLETE` is written atomically only after artifact and final-iteration
  checks pass. A COMPLETE run is immutable; rerunning always creates a new
  run ID. Never write into an existing run directory.

### 8.3 Manifest

`manifest.json`, strict JSON, minimal — every field here is one the code
actually checks or a reader actually needs:

```json
{
  "schema_version": 1,
  "run_id": "20260801T183045Z_a81d19c2",
  "stage_id": "collector.biased_10v",
  "scenario": null,
  "status": "COMPLETE",
  "created_at_utc": "2026-08-01T18:30:45Z",
  "completed_at_utc": "2026-08-01T20:02:11Z",
  "case_sha256": "...",
  "study_sha256": null,
  "git_commit": "...",
  "git_dirty": false,
  "python_version": "...",
  "warpx_version": "...",
  "mpi_ranks": 1,
  "omp_threads": 8,
  "random_seed": 42,
  "expected_final_iteration": 150000,
  "observed_final_iteration": 150000,
  "artifacts": [{"path": "diags/...", "bytes": 12345}]
}
```

`study_sha256` is set for scenario runs (hash of the full source study YAML)
and null otherwise. Because research worktrees are often dirty, `begin_run`
also copies the stage's `simulation.py` and `helpers.py` into
`sources_used/` — a few small files that make any run reconstructible
regardless of git state. Large raw artifacts are recorded by path and size
only; no checksumming of multi-GB files.

An optional ignored `LATEST` file may name the most recent COMPLETE run for
interactive convenience; code must still open and verify the manifest it
points to.

### 8.4 Retention

Immutable run directories accumulate. Cleanup is manual and legitimate:
deleting any `outputs/<run-id>/` or `results/` subtree is always safe because
nothing committed points into them except `reference_results/`, which carries
its own copies. `run_ladder.py` may print total `outputs/` disk usage as a
reminder. No automatic garbage collection is implemented.

---

## 9. Metrics, gates, verdicts

### 9.1 Metric representation

```json
{
  "id": "collector_current_A",
  "status": "OK",
  "value": 7.479e-6,
  "unit": "A",
  "uncertainty": 4.71e-8,
  "sample_count": 40,
  "window": {"start_iteration": 91500, "end_iteration": 150000},
  "source": "scrape/particles_at_eb"
}
```

A missing measurement is `value: null, status: "ERROR"`. Never serialize NaN
or Inf.

### 9.2 Gate statuses and verdict rules

Each gate is `PASS`, `FAIL`, `ERROR` (evidence missing, non-finite,
malformed, or unevaluable), or `SKIP` (allowed only for gates the policy
marks optional). Stage verdict:

1. At least one required gate must exist; an empty policy is ERROR, not PASS.
2. Every expected required gate ID must be present exactly once.
3. Stage PASS requires every required gate to be PASS.
4. Any required FAIL, ERROR, or SKIP makes the stage non-passing.

Process exit codes — and the analyzer's exception handler must honor them
(section 6.3): `0` all required gates pass; `1` valid evidence, gate(s) fail;
`2` analysis error, missing evidence, incompatible runs, or invalid policy.

### 9.3 `acceptance.yaml`

```yaml
schema_version: 1
policy_id: collector.biased_10v.v1
stage_id: collector.biased_10v
evidence_kind: numerical_sanity

gates:
  - id: electron_current_vs_oml
    required: true
    metric: electron_current_over_oml
    comparison: within_range
    minimum: 0.80
    maximum: 1.05
```

Policy discipline is git plus honesty, not machinery: changing any tolerance
requires a new `policy_id`; every verdict records the policy ID and the
SHA-256 of the policy file used; old verdicts are never reinterpreted. If a
tolerance was tuned by looking at a run, the stage README must say so — that
run is calibration, and a claim of independent validation needs a fresh run
judged under the pre-existing policy. No preregistration enforcement is
built.

### 9.4 Immutable analysis lifecycle

```text
results/<run-id>/<analysis-id>/      # single-run stage
results/<joint-id>/<analysis-id>/    # multi-run: joint-id from membership hash
```

Analysis ID: `20260801T210412Z_p42e91a7` (timestamp + short policy hash).
`analysis_manifest.json` records member run IDs and manifest hashes, policy
ID and hash, analyzer git commit and dirty flag, status, and exit code, with
the same `RUNNING -> COMPLETE | FAILED | INVALID` atomic lifecycle. A changed
policy or analyzer produces a new analysis directory; nothing is overwritten.
`acceptance_used.yaml` and a copy of `analyze.py` are stored alongside.

---

## 10. Diagnostic and statistical rules

These bind every stage's `analyze.py`.

1. **Complete time grid.** Expected scrape iterations come from
   configuration, not from iterations that happened to contain particles:
   `expected = np.arange(scrape_period, max_steps + 1, scrape_period)`.
   Validation configs make `max_steps` divisible by `scrape_period`.
2. **Heartbeat.** `simulation.py` registers WarpX's `ParticleNumber` reduced
   diagnostic at the scrape cadence. A scrape interval with no scraped
   particles counts as a valid zero only when its heartbeat record exists; a
   missing expected heartbeat is ERROR. Current CSVs contain the complete
   expected grid, zeros included.
3. **Steady state** (Phase 5): before reporting a steady mean, check minimum
   sample count, slope across the window, block-mean consistency, and finite
   uncertainty. A failed stationarity check makes dependent gates ERROR/FAIL
   per policy.
4. **Consistent ensembles** (Phase 5): quantities compared in one gate must
   share time window, spatial region, and particle ensemble.
5. **Containment** (Phase 5): sheath containment uses the connected sheath
   radius and clearance to boundaries, not potential a few cells inside a
   forced-zero Dirichlet boundary.

---

## 11. Root ladder

`ladder.py` is a literal list — visible membership, drift becomes an error:

```python
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Stage:
    id: str
    directory: Path
    requires: tuple[str, ...] = ()
    scenarios: tuple[str, ...] = ()   # empty means single-run stage


STAGES = (
    Stage("emitter.negative_cathode", Path("electron_gun/1_negative_cathode")),
    Stage("emitter.holed_anode", Path("electron_gun/2_electron_gun"),
          requires=("emitter.negative_cathode",),
          scenarios=("A_low_current_small_hole",
                     "B_high_current_small_hole",
                     "C_high_current_big_hole")),
    Stage("collector.thermal", Path("current_collection/1_thermal")),
    Stage("collector.biased_3v", Path("current_collection/2_biased_3v"),
          requires=("collector.thermal",)),
    Stage("collector.biased_10v", Path("current_collection/3_biased_10v"),
          requires=("collector.biased_3v",)),
)
```

`run_ladder.py`:

1. checks every stage directory satisfies the folder contract;
2. topologically orders requested stages;
3. launches `simulation.py` as a subprocess with the stage as working
   directory, once per scenario for multi-run stages;
4. reads the emitted `RUN_ID=` line, then opens and verifies the COMPLETE
   manifest (never trusts the exit code or the line alone);
5. launches `analyze.py --run ID --policy acceptance.yaml` (or `--runs ...`)
   as a subprocess and verifies the emitted analysis manifest and strict
   verdict JSON;
6. advances only when dependencies passed;
7. writes `suite_results/<suite-id>/` containing `suite.log` and
   `suite_verdict.json` (selected run/analysis IDs, their hashes, per-stage
   and cross-stage results), published atomically.

Cross-stage checks (in `run_ladder.py` or a small `analyze_ladder.py`): all
dependencies PASS; compared runs share required physical parameters; expected
current-fraction trends; expected sheath-radius ordering; aperture
transmission comparisons.

Any remaining marker-file completion logic (e.g. `CHAIN_DONE`-style flags or
treating committed snapshots as finished runs) is removed; a suite is
complete only when its verdict file says so.

---

## 12. Generated versus reference artifacts

`.gitignore`:

```gitignore
**/outputs/
**/results/
suite_results/
**/__pycache__/
*.log
```

Small curated summaries, CSVs, and figures may be committed under a stage's
`reference_results/`. Each must include the original run ID, case hash,
policy ID/hash, git commit, WarpX version, and complete metrics and gate
details — enough to know exactly what produced it. A reference result is
read only for comparison; its presence never makes `simulation.py` skip a
run.

---

## 13. Critical bugs the implementation must close

Milestone A closes the integrity failures while preserving numerical
behavior; Milestone B makes the scientific claims trustworthy. The suite
stays labeled scientifically provisional until every item has a regression
test.

### C1. Fail-open NaN and missing gates
Current: non-finite measurements are marked SKIP but leave `ok=True`
(`cc_common.py` gate loop), printing PASS and exiting 0; empty policies pass.
Fix: missing, non-finite, duplicate, or skipped required gates produce ERROR
and exit 2; zero required gates is ERROR.

### C2. False completion from tracked snapshots
Current: committed `config_used.yaml` files act as completion markers; a
clean checkout claims scenarios finished, then analysis finds no raw fields.
Fix: only a verified COMPLETE run manifest in a generated run directory means
complete.

### C3. Stale and partial output mixing
Current: runners reuse non-empty output directories; failed reruns mix old
and new iterations.
Fix: every execution gets a fresh immutable run directory; analysis verifies
expected final iteration.

### C4. Mixed configuration generations
Current: electron-gun scenario A comes from an older configuration generation
than B/C and the analyzer combines them unchecked.
Fix: `analyze.py --runs` verifies stage ID and source-study hash across
members; incompatible sets are ERROR.

### C5. Post-hoc acceptance tuning presented as validation
Current: thresholds can be revised after seeing a run and applied to that
same run as independent validation.
Fix: policy changes require a new `policy_id`; verdicts record the policy
hash; calibration runs are disclosed in the README and validation claims
require a fresh run under the pre-existing policy (section 9.3).

### C6. No stationarity gate
Current: the +10 V current drifts ~4% through its declared steady window yet
the point mean passes near its lower bound.
Fix (Phase 5): stationarity is a required metric; dependent gates cannot pass
when their window fails it.

### C7. Missing zero-current bins
Current: time axes are built only from iterations containing scraped
particles; empty intervals disappear.
Fix: full configured grid plus heartbeat (section 10).

### C8. Incorrect holed-gun Child-Langmuir interpretation
Current: planar Child-Langmuir is presented as the virtual-cathode threshold
for a non-planar geometry.
Fix (Phase 5): label it a rough scale, or add a true planar-anode sweep that
locates reflection onset.

### C9. Inconsistent energy ensembles
Current: all-time arrival energies are compared with final-step, near-axis
potential and unconditional launch energy.
Fix (Phase 5): filter impacts to the validated steady window; average
references over the matching source area, times, and transmitted ensemble.

### C10. Invalid maximum-principle explanation
Current: negative-cathode docs invoke Laplace's minimum principle despite
simulating space charge with Poisson's equation.
Fix (Phase 5): remove the argument; use measured cathode returns and an
appropriate space-charge comparison.

### C11. Non-standard JSON and incomplete summaries
Current: summaries contain literal `NaN` and omit gate values, policies, and
skip/error states.
Fix: strict JSON with null/ERROR statuses and the complete verdict schema.

### C12. No numerical convergence evidence
Current: quantitative claims rest on one grid, one PPC, one domain, one seed.
Fix (Phase 5): add grid/domain/PPC/seed sweeps before promoting sensitive
quantities to quantitative validation.

---

## 14. Tests required

### 14.1 `ladder_contract` tests (written once, at the root)

- canonical hash stability;
- run and analysis state transitions; no-overwrite behavior;
- atomic publication; exclusive directory creation;
- strict JSON rejection of NaN/Inf;
- gate evaluation: required PASS/FAIL/ERROR/SKIP behavior, duplicate gate
  IDs, empty policy rejection;
- missing-artifact and wrong-final-iteration detection.

### 14.2 Per-stage tests (physics and analysis only)

- config parsing and rejection of invalid inputs;
- analytical formula values and units; geometry invariants;
- complete expected scrape grid; zero-hit intervals backed by heartbeat;
  missing-heartbeat rejection;
- stage-specific checks, e.g.: negative cathode — vacuum Laplace ramp, energy
  formula, particle budget; holed gun — EB sign/solid-region, aperture
  geometry, scenario-hash compatibility; current collection — Debye length,
  thermal currents, OML scale, cylindrical volume weighting, `dr` vs `dz`
  face normalization, connected sheath edge;
- animations: smoke test only.

### 14.3 Repository-level tests

- every declared stage satisfies the folder contract;
- the ladder is acyclic and dependencies exist;
- the root runner never imports stage simulation modules;
- a clean checkout with only reference results reports no completed local
  runs;
- incompatible `--runs` sets are rejected;
- editing the live `config.yaml` cannot change analysis of a frozen run;
- re-analysis with a new policy creates a new directory and preserves the
  old one.

---

## 15. Migration plan

### Phase 0: Freeze the baseline

Record the current git commit; copy current committed summaries and figures
into a labeled temporary baseline folder; note which raw artifacts are
unavailable. No physics or gate changes.

### Phase 1: Contract module + one template stage

1. Write `ladder_contract.py` and its tests.
2. Migrate `electron_gun/1_negative_cathode` (small, strong analytic checks):
   rename the deck to `simulation.py`, create `helpers.py`, move analysis
   into `analyze.py`, adopt run/analysis lifecycles and fail-closed gates.
3. Add regression tests for missing, non-finite, skipped, duplicate, and
   empty required gates now — fail-closed semantics are a Phase 1 safety fix,
   not a Phase 5 science fix.
4. Confirm unchanged calculations reproduce the existing baseline within
   numerical/reporting precision.

### Phase 2: Migrate the holed electron gun

One scenario per run/process; effective-scenario `config_used.yaml` plus
source-study hash per run; `analyze.py --runs` with compatibility checks.
Preserve numerical behavior.

### Phase 3: Migrate current collection

For `1_thermal`, `2_biased_3v`, `3_biased_10v`: copy the needed PIC
construction from `cc_common.py` into each stage's `simulation.py`; copy only
the relevant analytical helpers into each `helpers.py`; move diagnostics into
each `analyze.py`; remove the wrapper scripts. When all three work
independently, delete `cc_common.py`. The deliberate physics duplication
should make differing domains, time steps, and gates obvious per folder.

### Phase 4: Root ladder and reference results

Literal stage list, subprocess orchestration, suite verdicts; move curated
outputs into `reference_results/`; ignore all generated directories; remove
every snapshot-as-completion path.

### Phase 5: Scientific corrections

Only after structural parity: zero-bin accounting in gates; stationarity and
uncertainty-aware checks; consistent ensembles; corrected Child-Langmuir,
Poisson/Laplace, thermal-tail, and OML narratives; convergence sweeps; fresh
validation runs under pre-existing policies. Each correction that changes a
metric or verdict gets a new `policy_id`, a new reference result, and a README
explanation.

---

## 16. Implementation conventions

- Explicit functions and dataclasses over generic dictionaries.
- `pathlib.Path`; all generated paths resolve from the stage directory.
- YAML never selects output paths; `yaml.safe_load`; reject unknown keys.
- Units in configuration and metric names.
- Explicit exceptions, not `assert`, for runtime input validation.
- Never catch broad exceptions into NaN measurements.
- Never infer success from file existence alone.
- Never silently pick the latest run when several are valid; require an
  explicit run ID.
- READMEs may quote measured values, but the machine-readable reference
  result is authoritative.
- Every WarpX invocation is a subprocess.

---

## 17. Milestones

### Milestone A: structural architecture (Phases 0-4)

Done when:

1. Every stage has local `simulation.py`, `helpers.py`, `analyze.py`,
   `config.yaml`, `acceptance.yaml`, README, and tests; no cross-stage
   imports; `cc_common.py` and wrapper scripts are gone.
2. Every execution creates a new immutable run directory; COMPLETE means
   artifacts and final iteration were verified.
3. Every analysis creates a new immutable directory; nothing overwrites.
4. A clean checkout never mistakes reference artifacts for completed runs.
5. Missing, NaN, skipped, duplicate, or zero required gates cannot exit 0.
6. JSON output is strict with complete metric/gate provenance.
7. Multi-run analysis rejects incompatible or incomplete member sets.
8. The root ladder runs every stage through subprocesses and emits one
   auditable suite verdict.
9. Existing baseline numbers are reproduced before scientific corrections.
10. Regression tests cover C1-C5 and C11.

Milestone A is not permission to make corrected scientific claims; the suite
stays visibly provisional.

### Milestone B: scientific remediation (Phase 5)

Done when: complete diagnostic grids with explicit zeros; stationarity
required for steady metrics; uncertainty-aware gates where the evidence kind
requires them; consistent ensembles; corrected and properly scoped
Child-Langmuir/Poisson/thermal-tail/OML/sheath claims; convergence evidence
for every promoted quantitative claim; fresh validation runs under
pre-existing policies; regression tests covering C1-C12.

The intended result is not a framework. It is a set of explicit,
self-contained scientific simulations plus one small shared contract file, so
they can form an auditable validation ladder without the plumbing being
written five times.
