# reference results — capstone.mission_envelope

`20260803T091155Z_4fc9fd22/` is the curated snapshot of the **first cohort** of
this rung: the two mission operating points selected from the 2024 400 km orbit
CSV, run at 300 V and analysed together under policy
`capstone.mission_envelope.v1`.

**The verdict is FAIL, and it is committed as such.** 20 of 22 gates pass; the
two that fail (`B_float_matches_prediction`, `collection_law_form_holds_across_chi`)
are the same failure seen twice — the collection law's `(1+χ)` form does not
carry the density dependence it needs. The stage README has the full diagnosis.

A failing reference bundle is kept deliberately. This rung's job is to test a
model, and the informative outcome is the one that moved the model; discarding
it would leave only the runs that agreed with what we already believed.

| file | what it is |
|---|---|
| `metrics.json` | every measured metric, machine-readable |
| `verdict.json` | the gate-by-gate FAIL |
| `acceptance_used.yaml` | the policy as it stood when judged (its SHA is in the verdict) |
| `config_used/*.yaml` | each run's frozen physics, design constants and pre-registered predictions |
| `run_manifests.json` | both run IDs, config hashes, git commit, WarpX version |
| `figures/` | φ vs prediction, thrust and beam fate, β vs χ |

The runs themselves (`outputs/20260802T124722Z_A_day_p95_f715efee`,
`outputs/20260802T202221Z_B_night_worst_dd0f0e08`) are 14 GB of dumps and are
gitignored; everything needed to audit the verdict is here.
