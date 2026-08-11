# Thruster characterization — spokes off the anchor

The concept-validation **ladder** (`../ladder/`) ends at the 200 V anchor,
`capstone.floating_body`. Everything here is a **characterization spoke**: one
physics axis moved off that anchor, with everything else carried verbatim.
Spokes depend only on "the anchor passed" — never on each other — so this is a
hub-and-spoke, not a ladder. `../run_ladder.py` runs the ladder group by
default; spokes run only when named (`--stages characterization.slender_body`).

Every folder is self-contained per the architecture contract
(`../ladder/ARCHITECTURE_REFACTOR_PLAN.md` decision 1): its own
`simulation.py`, `config.yaml`, `helpers.py`, `analyze.py`, `acceptance.yaml`,
tests, and committed evidence under `reference_results/`.

| spoke | axis (delta from the anchor deck) | stage id | gated result |
|---|---|---|---|
| `high_thrust/` | drive voltage 300 V | `capstone.high_thrust` | PASS 2026-08-05 — φ 36.30 V, F 30.13 nN |
| `low_power/` | drive voltage 100 V | `capstone.low_power` | PASS 2026-08-05 — φ 5.40 V, F 3.42 nN |
| `slender_body/` | geometry: z_bot −30 mm, cathode standoff pinned (L/r = 6) | `characterization.slender_body` | PASS 2026-08-06 — φ 4.38 V, F 14.22 nN |
| `thin_plasma/` | density: n0/3 (+ rmax 30→40 mm containment) | `characterization.thin_plasma` | PASS 2026-08-09 — trust gates only; φ unsettled, > 31.6 V bound |
| `magnetized_1x/` | field-aligned Bz = 30 µT (1× LEO) | `characterization.magnetized_1x` | PASS 2026-08-10 — null: anchor unchanged |
| `magnetized_10x/` | field-aligned Bz = 300 µT (10×) | `characterization.magnetized_10x` | PASS 2026-08-10 — collection tax: φ +33 V, F −11 % |

## Provenance of the migrated evidence

`high_thrust` and `low_power` have always been their own stages; they moved
here from `capstone/3_…/4_…` with ids frozen (committed manifests embed them).

The other four spokes were **executed as variant decks through the anchor
stage** (then `capstone/2_chipsat_thruster`, config hash in each run id) under
the pre-registered exploratory policy `capstone.exploratory_axes.v1`, before
these folders existed. Their evidence was migrated here unchanged: run
manifests, frozen configs, metrics, and verdicts still carry
`stage_id: capstone.floating_body` and that policy id — that is the honest
record of how they ran. Each folder's `acceptance.yaml` re-identifies the same
gates (byte-for-byte tolerances) under the new stage id **for future runs**;
it is not a pre-registration for the migrated evidence.

Historical launch records: `m1_chain.sh` (both magnetized spokes, strictly
sequential on one GPU), `thin_plasma/thin_plasma_chain.sh`, and each spoke's
`logs/`. Campaign narrative: `/CAMPAIGN.md`; plans live inside the spokes
(`slender_body/SLENDER_BODY_PLAN.md`, `thin_plasma/THIN_PLASMA_PLAN.md`) and
at `MAGNETIZED_PLAN.md` here (it spans both M1 spokes and defines tier M2,
the open transverse-field question).
