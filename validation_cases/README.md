# validation_cases: the verification ladder to the chipsat

**Reviewer digest: `LADDER_SUMMARY.md`** — every rung's test, measured
numbers, and theory comparison on one page.

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
  1_thermal           collector.thermal          sphere at 0 V, exact    (~16 min CPU)
  2_biased_3v         collector.biased_3v        OML ceiling, chi=26.4   (~65 min CPU)
  3_biased_10v        collector.biased_10v       sheath growth, chi=88   (~80 min CPU)
  4_floating          collector.floating         charge pump -> phi_f    (~35 min CPU)
chipsat_two_node/     capstone.two_node_laplace  two-node EB in vacuum   (seconds)
chipsat/              CAPSTONE (emitter + collector, floating body)
  chipsat             capstone.floating_body     float200 regression     (~6.3 h CPU/GPU)
```

The two 2026-08-01 rungs close the audit's top gaps
(`chipsat/VALIDATION_GAPS.md` G1/G2): `collector.floating` runs the
capstone's floating charge pump on a passive sphere against the analytic
floating-potential bracket (thermal-ion −0.360 V / OML-ion −0.213 V), and
`capstone.two_node_laplace` solves the capstone's two-node piecewise EB in
vacuum where the maximum principle and an independent solver are exact
checks.  Both are required dependencies of the capstone.

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

**Milestone A (structural architecture, Phases 0–4): implemented, and the
entire 8-stage ladder has run and PASSED on this machine** (2026-08-01, CPU
build): both emitter stages reproduce the pre-refactor baseline bit-for-bit;
all three fixed-bias collector stages PASS with striking GPU-baseline parity
(e.g. I_e/I_OML 0.8090 vs 0.8087 at +10 V); the **chipsat capstone**
(`capstone.floating_body`, migrated from the electron_contactor float200
baseline — see `chipsat/MIGRATION_PLAN.md` and `chipsat/VALIDATION_GAPS.md`)
completed its full parity run in 6.34 h and PASSes all 8 gates (escape
98.44 %, F_beam 13.65 nN, φ_body +16.98 V); and the two 2026-08-01 rungs
closing gaps G1/G2 both PASS — `collector.floating` drove the capstone's
charge pump to φ_f = −0.251 V inside the analytic bracket with 0.9 % current
balance, and `capstone.two_node_laplace` verified the two-node EB against
exact Laplace properties and an independent solver. The full-suite verdict
with all seven cross-stage checks green is `suite_results/20260801T234329Z`.
All eight stages carry verified `reference_results/`; the per-stage numbers
are digested in `LADDER_SUMMARY.md`. The suite stays **scientifically
provisional** — Milestone B (Phase 5: stationarity gates, consistent
ensembles, corrected Child-Langmuir narratives, convergence sweeps) is **not
yet done** (zero-bin accounting C7 was fixed 2026-08-01). See
`ARCHITECTURE_REFACTOR_PLAN.md` §13 (C1–C12).
