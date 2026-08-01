# Migration plan: electron_contactor capstone → `capstone.floating_body`

This documents how the validated **float200 chipsat capstone** from
`~/Desktop/repos/warpequisd/electron_contactor` is migrated into this repo as
the top rung of the validation ladder, following the stage contract of
`../ARCHITECTURE_REFACTOR_PLAN.md`. Companion document:
`VALIDATION_GAPS.md` — what the lower rungs do and do **not** validate about
this stage.

## The physical system being migrated

A conducting **can** (r = 5 mm, wall/lid/floor 0.4 mm, z ∈ [-5, +0.5] mm)
floats electrically in the capstone ionospheric plasma (the same PLASMA_MAX row
the collector rungs gate: n0 = 1.627e12 m⁻³, Te = 1318.8 K, Ti = 936.2 K,
mi = 400 mₑ). An electron gun is fully enclosed: the **cathode disk**
(r < 1.5 mm) sits on the floor, held at `phi_body − 200 V` once the supply
switches on (t ≥ 100 ns); the beam (0.342 mA, spot r < 0.5 mm, on at 150 ns)
accelerates through the 4.7 mm cathode→lid gap and exits through the **lid
hole** (r < 2.0 mm). The **body potential floats** via a charge pump:

1. self-capacitance C measured once from the uniform-1 V init solve (Gauss's
   law on the domain faces);
2. every step, the net scraped charge `dQ = e·(dW_beam + beam_escape)
   − e·amb_e_coll + e·amb_i_coll` integrates into Q, and
   `phi_body = phi0 + Q/C`;
3. the piecewise EB potential (BODY = phi_body, CATHODE = phi_body + offset)
   is rewritten via `set_potential_on_eb`.

A **reservoir** re-injects every EB-collected ambient particle as a fresh
Maxwellian in the outer radial shell (r > 22.5 mm) every 25 steps — the
floating equilibrium is a current balance, and without refill the run would
measure reservoir depletion, not physics.

Validated float200 result (the regression anchor): escape ≈ 98.5 %,
F_beam ≈ 13.6 nN, phi_body → ≈ +16 V, exhaust ≈ 146 eV, supply ≈ 0.068 W.

## Source → stage mapping

| electron_contactor | chipsat/ stage file | Notes |
|---|---|---|
| `config.yaml` + `config.py` DEFAULTS | `config.yaml` | baseline values only, `stage_id` added; dropped groups below |
| `config.py` derivations (`_derive_plasma`, `finalize`, `_validate_basics/_grid`) | `helpers.py` | fluxes n·vth/√2π, λ_D, ωpe, V_GAP, I_CL, CFL dt = 0.3·dx/(v_beam+4vth_e), grid snap to ×8, R_res, asserts (dx<λ_D, CFL<0.5, ωpe·dt<0.2, lid hole ≥5 dx, gap ≥7 dx) |
| `geometry.py` (whole `Geometry` class) | `helpers.py` | verbatim physics: EB implicit function, piecewise potential strings, region masks, geometric asserts; numpy-only ✓ |
| `run.py` `build_species`/`build_simulation` | `simulation.py` | grid/solver/EB/species/diagnostics |
| `floating_body.py` `FloatingBody` + `self_capacitance` | `simulation.py` | the charge pump IS this stage's physics; dQ accounting transcribed verbatim |
| `diagnostics.py` `Diagnostics` | `simulation.py` | per-step scrape reader, beam-fate classification, F_beam/F_net, exhaust-KE, CSV every 100 steps |
| `reservoir.py` `Reservoir` | `simulation.py` | bank + Maxwellian re-injection |
| `run.py` `Coordinator` + `main` + `edge_phi_max` | `simulation.py` | callbacks; chunked loop with choke + edge watchdogs; **ladder_contract lifecycle** (begin_run → COMPLETE/FAILED/INVALID) replaces `DONE` files |
| `analysis.py` | `analyze.py` | steady metrics, energy ledger, plots; gates evaluated through `ladder_contract` (fail-closed, exit 0/1/2) |
| `analysis.py` `GATE` dict (spec 8) | `acceptance.yaml` | policy `capstone.floating_body.v1`, `evidence_kind: system_integration_regression` |
| `make_clips.py` | `animate.py` | presentation only |

## Deliberately NOT migrated

Per the refactor plan's non-goals and the baseline-only scope:

- **Checkpoint/restart + sidecars** (`checkpoint.py`, restart paths in
  Coordinator/Diagnostics): the plan defers restart — an interrupted run is
  FAILED and rerun from scratch. This costs up to a few GPU-hours per
  interruption; stated trade-off.
- **Probe/pinned mode** (`PinnedBody`, `plasma_check.py`, `analysis_oml.py`):
  that physics is exactly what `collector.*` rungs validate.
- **Shroud, `plasma.drift_z`, `fields.Bz_T`** (gap-LX/D experiments): baseline
  has them off; config validation rejects non-defaults with a pointer to the
  contactor repo. Research sweeps stay in `electron_contactor`.
- **`auto_stop`**: the validated capstone ran to t_end; the stage always runs
  the full step count (required for the immutable-run final-iteration check).
- **GPU lock file**: `run_ladder.py` is sequential; the stage README repeats
  the one-run-at-a-time rule.
- Sweep/collation/paper tooling (`sweep.py`, `collate.py`, `fit_iphi.py`,
  `plot_ucurve.py`, memos).

## Behavior-preserving deviations (all observer-side)

1. `max_steps` is **floored to a multiple of `diag_period`** so the final
   field dump lands exactly on the last iteration (the immutable-run
   completion check needs it). Baseline: 159 171 → 159 160 steps
   (−0.06 ns of 800 ns; tail averages unaffected).
2. A `ParticleNumber` reduced diagnostic is added at the CSV cadence (pure
   observer; gives in-domain weights for budget cross-checks).
3. The per-run directory layout, manifest, and strict-JSON outputs follow the
   ladder contract (immutable `outputs/<run-id>/`, `results/<run-id>/<aid>/`).
4. `analyze.py` adds one **new cross-check metric**: cumulative charge from
   the CSV ledger vs. the openPMD scrape dumps (`scrape_charge_consistency`),
   closing the per-step-buffer accounting gap (G8 in VALIDATION_GAPS.md).
5. CHOKED (phi_body > ceiling sustained) and a non-finite phi divergence
   mark the run **FAILED** (early abort); EDGE-warn remains a live warning,
   and containment is *gated* in analysis from the field dumps.

## Acceptance policy (float200 regression, disclosed)

`acceptance.yaml`, policy `capstone.floating_body.v1`,
`evidence_kind: system_integration_regression` — the gate numbers come from
the validated float200 run itself (regression + internal consistency, not
analytic verification; the analytic anchors live in the lower rungs):

| gate | bound | provenance |
|---|---|---|
| `escape_fraction_pct` | ≥ 95 % | float200 spec 8 |
| `f_beam_nN` | 13.6 ± 15 % | float200 |
| `phi_body_V` | +16 ± 4 V | float200 |
| `current_balance` | ≤ 5 % | steady-state identity I_escape ≈ I_amb_e − I_amb_i |
| `f_net_over_f_beam` | ≤ 1.0 | momentum sanity bound |
| `edge_phi_max_V` | ≤ 1.0 V | sheath/plume containment (collector-rung style) |
| `scrape_charge_consistency` | ≤ 2 % | NEW: CSV ledger vs openPMD dumps |

Reported, not gated: mean exhaust KE + energy ledger (injection-plane φ
reconciliation), far-field density (confounded by the recycle shell),
late dφ/dt (finite-time-equilibrium honesty line). Stationarity gating is a
Phase 5 item (plan C6).

## Ladder integration

- `ladder.py`: `Stage("capstone.floating_body", Path("chipsat"),
  requires=("emitter.holed_anode", "collector.biased_10v"))` — the branch tips,
  per the plan's DAG.
- `cross_stage.py`: new check — the capstone's frozen plasma row, dx, and
  ambient ppc must hash-match `collector.thermal`'s (the "the ladder validated
  this exact configuration" claim, made executable).

## Verification plan

1. Stage unit tests (no WarpX): config parsing/rejection, geometry invariants
   (spot < hole < wall, insulation gaps ≥ 2 dx, region-mask disjointness),
   derived quantities vs the contactor's own `run_meta.json` values
   (I_CL, dt = 5.026e-12 s, grid 200×440, R_res = 22.5 mm, V_GAP = 200 V),
   steady/balance math and fail-closed policy wiring on synthetic CSV rows.
2. `run_ladder.py --check` passes with the stage registered.
3. CPU smoke run with a **reduced, uncommitted scratch config** (small domain,
   ~ns horizon) to exercise the full lifecycle: C calibration → pump →
   EB rewrite → reservoir injection → CSV → COMPLETE → analyze (gates will
   correctly FAIL on a non-equilibrated smoke — that is the fail-closed
   machinery working, not a defect).
4. **Full parity run — DONE** (2026-08-01, run `20260801T142601Z_2f822a95`):
   the baseline completed in 6.34 h on the **CPU build** (14 threads,
   0.14 s/step — the deck is callback-bound, so CPU ≈ RTX 3060) and PASSed
   all 7 acceptance gates, reproducing the float200 anchors (escape 98.44 %,
   F_beam 13.65 nN, φ_body +16.98 V, exhaust 147.5 eV). `reference_results/`
   is populated; the 6-stage suite verdict incl. the capstone cross-check is
   `suite_results/20260801T204741Z`.
