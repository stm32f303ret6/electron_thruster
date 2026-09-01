# Thruster characterization: spokes off the anchor

The concept-validation ladder (`../ladder/`) ends at the 200 V anchor,
`capstone.floating_body`. Everything here is a characterization spoke: one
physics axis moved off that anchor, with everything else carried verbatim.
Spokes depend only on "the anchor passed", never on each other, so this is a
hub-and-spoke layout rather than a ladder. `../run_ladder.py` runs the ladder
group by default; spokes run only when named
(`--stages characterization.slender_body`).

Every folder is self-contained per the architecture contract
(`../ARCHITECTURE.md` decision 1): its own
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
| `350V_400km/` | drive voltage 350 V (400 km-enabling envelope step) | `characterization.350V_400km` | PASS 2026-08-17 — φ 48.29 V (tail; 51.1 V endpoint still rising), F 40.48 nN vs 40.5 predicted |
| `350V_400km_slender/` | voltage 350 V **and** slender geometry — the 2×2 factorial corner | `characterization.350V_400km_slender` | PASS 2026-08-17 — φ 14.00 V (predicted 11–17), F 43.33 nN (predicted 42–43): the laws compose |
| `transverse_b_numerics/` | numerics mini-ladder for tier M2: test electrons on the 3D grid vs closed forms (gyration, E×B) | `characterization.transverse_b_numerics` | PASS 2026-09-01 — ω to 3 × 10⁻⁴, r_g and E×B drift exact |
| `magnetized_transverse/` | field **perpendicular** to the thrust axis (tier M2, the flight geometry): Cartesian 3D deck, anchor body resolved, Bx = 0 / 30 / 300 µT | `characterization.magnetized_transverse` | pre-registered 2026-09-01, running |

The `350V_400km_slender` spoke is the one deliberate exception to the
one-axis rule: it moves voltage and geometry together. Both single-axis
legs are measured (`slender_body` at 200 V, `350V_400km` pre-registered at
350 V), so with the anchor it completes a 2×2 voltage × geometry factorial.
This makes it a test of whether the two committed laws compose rather than
an unattributable jump. Both corners ran 2026-08-17 (squat first) and the
composed prediction held. See the spoke READMEs for the closed factorial.

## Provenance of the migrated evidence

`high_thrust` and `low_power` have always been their own stages; they moved
here from `capstone/3_…/4_…` with ids frozen (committed manifests embed them).

The other four spokes were executed as variant decks through the anchor
stage (then `capstone/2_chipsat_thruster`, config hash in each run id) under
the pre-registered exploratory policy `capstone.exploratory_axes.v1`, before
these folders existed. Their evidence was migrated here unchanged: run
manifests, frozen configs, metrics, and verdicts still carry
`stage_id: capstone.floating_body` and that policy id, which is the record
of how they ran. Each folder's `acceptance.yaml` re-identifies the same
gates (byte-for-byte tolerances) under the new stage id for future runs;
it is not a pre-registration for the migrated evidence.

Launch console logs are local working files, not committed (the magnetized
pair ran strictly sequentially on one GPU); the run manifests under each
spoke's `reference_results/` carry the exact decks. Pre-registered
predictions and results live inside the spokes (each spoke README's plan
and results sections; the pre-run plan files are preserved in git
history). Tier M2 (transverse field) is executed by the two 3D stages
above; the design note that preceded them, and why its far-field
control-volume instrument was not built, is at
[`../../future_work/M2_TRANSVERSE_B.md`](../../future_work/M2_TRANSVERSE_B.md).
