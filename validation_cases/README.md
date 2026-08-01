# validation_cases: the verification ladder to the chipsat

Theory-anchored pre-simulations, in order of increasing physics, each gated
against closed-form references. The ladder validates the CODE (WarpX RZ
electrostatics, EB, flux emission, scraping) and, deliberately, the
CONFIGURATION the final chipsat case will use — grid resolution, plasma row,
ppc, emitted current, aperture geometry — so that by the top rung every numerical
choice has already passed a gate somewhere cheaper.

```
electron_gun/                    EMITTER side (prescribed-current beams)
  1_negative_cathode  emitter.negative_cathode   plane diode, no EB      (~3 min GPU)
  2_electron_gun      emitter.holed_anode        + holed-anode plate     (~10 min GPU)
current_collection/              COLLECTOR side (ambient plasma)
  1_thermal           collector.thermal          sphere at 0 V, exact    (~25-50 min GPU)
  2_biased_3v         collector.biased_3v        OML ceiling, chi=26.4   (~1-2 h GPU)
  3_biased_10v        collector.biased_10v       sheath growth, chi=88   (~2-4.5 h GPU)
(future) chipsat      capstone.floating_body     emitter + collector
```

## Architecture (see `ARCHITECTURE_REFACTOR_PLAN.md`)

Two central decisions:

1. **Each stage is a self-contained folder** with its own complete PIC
   simulation, config, physics helpers, analysis, animation, and tests. Physics
   duplication between stages is deliberate: a reviewer reads one folder and
   sees the whole model.
2. **The non-physics plumbing** — run IDs, manifests, immutable directories,
   strict JSON, gate evaluation — lives in ONE small shared module,
   `ladder_contract.py`. It contains no physics, no `pywarpx`, no plotting.

### Every stage folder

```
<stage>/
  config.yaml        # physics/numerics (frozen + hashed per run)
  acceptance.yaml    # gates + tolerances (analysis-time policy)
  simulation.py      # the complete PIC deck + run lifecycle
  helpers.py         # stage-local typed config + analytic references
  analyze.py         # reads COMPLETE evidence -> metrics.json + verdict.json
  animate.py         # presentation only (optional)
  README.md          # what it proves / does not prove, gates, limitations
  tests/             # config + analysis unit tests (no WarpX)
  outputs/<run-id>/  # generated: immutable runs (git-ignored)
  results/<run-id>/<analysis-id>/   # generated: immutable analyses (git-ignored)
  reference_results/ # curated, committed artifacts (provenance + metrics)
```

### Root

```
ladder_contract.py   # shared plumbing; unit-tested once in tests/
ladder.py            # the literal stage list (visible membership)
run_ladder.py        # subprocess orchestration + suite verdict
cross_stage.py       # cross-stage checks (trends, orderings, shared params)
tests/               # contract + repository-level tests
suite_results/       # generated suite verdicts (git-ignored)
```

## The run / analysis lifecycle (fail closed)

- Every `simulation.py` execution creates a **fresh immutable** `outputs/<run-id>/`
  and is marked **COMPLETE only after** its artifacts and final iteration are
  verified. Reruns never mix with old output; there is no marker file.
- Every `analyze.py` run creates a **fresh immutable**
  `results/<run-id>/<analysis-id>/`; re-analysis never overwrites. Analysis reads
  the **frozen** `config_used.yaml`, never the live `config.yaml`.
- Gates are **fail-closed**: a missing, non-finite, duplicate, or skipped
  *required* gate is ERROR (exit 2), never a silent PASS; an empty policy is
  ERROR. Exit codes: `0` all required pass, `1` a gate failed, `2` analysis
  error / missing evidence / incompatible cohort / invalid policy.
- JSON is strict (`allow_nan=False`; NaN/Inf rejected on read).

## Commands

```bash
conda activate warpx-cpu-mpich-dev

# one stage, by hand
cd electron_gun/1_negative_cathode
python simulation.py                                       # -> outputs/<run-id>/
python analyze.py --run outputs/<run-id> --policy acceptance.yaml

# the whole ladder (subprocess per stage; verdict-driven)
python run_ladder.py --check                               # contract + topology only
python run_ladder.py                                       # run + analyze every stage
python run_ladder.py --stages emitter.negative_cathode emitter.holed_anode
python run_ladder.py --analyze-only --stages collector.thermal  # re-analyze newest runs

# tests (no WarpX). ~/.local has a broken 'dash' pytest plugin, so isolate it:
PYTHONNOUSERSITE=1 python -m pytest tests/ -q               # root: contract + ladder
cd electron_gun/1_negative_cathode && PYTHONNOUSERSITE=1 python -m pytest tests/ -q
```

Run ONE WarpX case at a time; each deck caps its AMReX arena so it coexists with
other GPU users. Deleting any `outputs/<run-id>/` or `results/` subtree is always
safe (nothing committed points into them except `reference_results/`, which
carries its own copies). No automatic garbage collection.

## Status

**Milestone A (structural architecture, Phases 0–4): implemented.** The two
emitter stages run and pass end-to-end on CPU, reproducing the pre-refactor
baseline numbers bit-for-bit. The three collector stages are fully migrated and
unit-tested but need a GPU to run (25 min – 4.5 h each). The suite stays
**scientifically provisional** — Milestone B (Phase 5: stationarity gates,
zero-bin accounting, consistent ensembles, corrected Child-Langmuir / Poisson /
OML / sheath narratives, convergence sweeps) is **not yet done**. See
`ARCHITECTURE_REFACTOR_PLAN.md` §13 (C1–C12) for the open scientific items.
