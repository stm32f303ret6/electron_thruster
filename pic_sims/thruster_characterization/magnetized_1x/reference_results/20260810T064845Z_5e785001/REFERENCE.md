# reference results — characterization.magnetized_1x (tier M1a, Bz = 30 µT)

`20260810T064845Z_5e785001/` is the curated snapshot of the **1× LEO
field-aligned magnetized run**: the 200 V anchor deck with exactly one change,
`plasma.Bz_T: 3.0e-5` — full production run (159,160 steps, 800 ns), GPU
build, **PASS — all 6 required gates** under policy
`capstone.exploratory_axes.v1`.

## The pre-registered hypothesis, and the answer

The magnetized-axis plan (now the plan section of `../../README.md`; the
pre-run `MAGNETIZED_PLAN.md` is preserved in git history) recorded H-M1-null
before the run: at 1× LEO field
strength the anchor's operating point does not move outside its own bands.

| metric | this run | unmagnetized anchor |
|---|---|---|
| φ_body (tail mean) | 17.22 V | 16.98 V |
| F_beam | 13.64 nN | 13.65 nN |
| escape fraction | 98.44 % | 98.44 % |
| exhaust KE (mean) | 147.3 eV | 147.5 eV |

**H-M1-null holds** — a genuine null at flight field strength: gun optics,
containment, collection, and the operating point are the anchor's. Together
with the 10× companion (`../../magnetized_10x/`, which shows where the axis
starts to bite) this closes the near-field, field-aligned half of the
magnetized question. The far-field **transverse** geometry (tier M2, beam
gyroradius ~1.4 m vs the 30 mm domain) remains open and is the project's
largest unexamined question (`/OPTIMISTIC_HYPOTHESES.md` H1).

## Provenance

Executed 2026-08-10 as variant deck `m1a_bz_1x.yaml` through the anchor stage
via `m1_chain.sh` (strictly sequential with M1b on one GPU, 12.8 h total);
frozen config and manifest here carry `stage_id: capstone.floating_body` and
the exploratory policy id. Files: `metrics.json`, `verdict.json`,
`acceptance_used.yaml` (analysis `20260810T131951Z_aae666a6`), figures,
frozen config, run manifest. Recorded in commit `0d12463`.
