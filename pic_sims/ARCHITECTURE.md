# pic_sims architecture — the stage contract

Distilled from the executed refactor spec (`ARCHITECTURE_REFACTOR_PLAN.md`,
817 lines, preserved in git history — it contains the full rationale, the
C1–C12 critical-bug register the implementation closed, and the migration
phases). This file states what is *load-bearing now*.

## The two decisions

> 1. **Each stage is a self-contained folder** with its own complete PIC
>    simulation script, configuration, physics helpers, analysis, animation,
>    and tests. Physics duplication between stages is deliberate: a reviewer
>    must be able to read one folder and see the whole model.
> 2. **Zero shared physics.** The only shared code is `ladder_contract.py` —
>    run IDs, immutable run/analysis directories, manifests, canonical config
>    hashing, gate evaluation. No physics, no pywarpx, no plotting.

## Layout

```text
pic_sims/
|-- ladder_contract.py         # the one shared module; unit-tested once
|-- stages.py                  # literal stage registry (ids, paths, deps, group)
|-- run_ladder.py              # subprocess orchestration + cross-stage checks
|-- cross_stage.py             # config-consistency checks between stages
|-- tests/                     # contract + registry tests
|-- ladder/                    # validation rungs, ending at the 200 V anchor
|   |-- electron_gun/  current_collection/  capstone/
`-- characterization/ # spokes off the anchor; no spoke depends on a spoke
```

The ladder is a DAG that terminates at `capstone.floating_body` (the anchor).
Characterization spokes each require only the anchor. `run_ladder.py` runs
the ladder group by default; spokes run via `--stages`. Stage ids embedded in
committed manifests are frozen — folders may move, ids never change.

Every stage folder: `README.md`, `config.yaml` (stage root, no inputs/ dir),
`acceptance.yaml`, `simulation.py`, `helpers.py`, `analyze.py`, optional
`animate.py`/`viz/`, `tests/`, generated `outputs/` and `results/` (both
git-ignored at the repo root), committed curated `reference_results/`.
Stages import `ladder_contract` (found by walking up to `pic_sims/`) and
nothing else outside their folder.

## Immutable run lifecycle

- **Run id** `20260801T183045Z_a81d19c2`: UTC stamp + first 8 hex chars of the
  canonical SHA-256 of the effective config (scenario name optional).
- **States** `NEW -> RUNNING -> COMPLETE | FAILED | INVALID`. COMPLETE is
  written atomically only after artifact and final-iteration checks; a
  COMPLETE run is immutable; rerunning always creates a new run id; never
  write into an existing run directory. There is no checkpoint/restart by
  design — an interrupted run is FAILED and rerun.
- **Manifest** (`manifest.json`, strict JSON — never NaN/Inf): run/stage ids,
  status, timestamps, `case_sha256`, `git_commit` + `git_dirty`, versions,
  seed, expected/observed final iteration, artifact paths+sizes.
  `begin_run` copies `simulation.py`/`helpers.py` into `sources_used/` so any
  run is reconstructible regardless of git state. An ignored `LATEST` file is
  interactive convenience only; code must verify the manifest it names.
- **Analyses** are immutable too: each gets its own id and directory
  (`results/<run>/<analysis>/` with `analysis_manifest.json`,
  `acceptance_used.yaml`, `metrics.json`, `verdict.json`, figures);
  re-analysis never overwrites.
- **Retention**: deleting anything under `outputs/` or `results/` is always
  safe — nothing committed points into them; `reference_results/` carries its
  own copies.

## Gates, verdicts, policy discipline

Gates are `PASS`/`FAIL`/`ERROR`/`SKIP`; a stage passes only if every required
gate passes; an empty policy or a missing/duplicated/non-finite required gate
is ERROR, never PASS. Analyzer exit codes: 0 = all required pass, 1 = valid
evidence but gate(s) fail, 2 = analysis error / missing evidence / invalid
policy.

Policy discipline is git plus honesty, not machinery: changing any tolerance
requires a new `policy_id`; every verdict records the policy id and the
SHA-256 of the policy file used; old verdicts are never reinterpreted. A
tolerance tuned by looking at a run makes that run *calibration* — a claim of
independent validation needs a fresh run under the pre-existing policy.
Evidence kinds are explicit in each `acceptance.yaml` (an OML upper-bound
sanity check is not an "analytic validation").

## Status and open items

**Milestone A (structural integrity): done.** All stages self-contained,
immutable lifecycle enforced, fail-open paths closed (plan items C1–C5, C7,
C11 have regression tests in `tests/` and the per-stage suites).

**Milestone B (scientific remediation): open.** Kept visible on purpose:

- **stationarity** (C6): steady means are windowed averages with reported
  slopes, no formal stationarity gate;
- **Child–Langmuir scope** (C8): planar C-L is a rough scale for the holed
  gun, not a located reflection threshold;
- **consistent energy ensembles** (C9) in the electron-gun comparisons;
- **maximum-principle wording** (C10) in the negative-cathode docs;
- **convergence** (C12): quantitative claims rest on one grid / ppc / domain
  / seed unless a stage says otherwise.

Non-goals, restated so nobody "fixes" them: no checkpoint/restart, no shared
simulation framework — the duplication is the review affordance.
