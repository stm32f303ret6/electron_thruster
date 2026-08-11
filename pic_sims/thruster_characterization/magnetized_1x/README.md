# characterization.magnetized_1x — magnetic axis, tier M1a (Bz = 30 µT, 1× LEO)

**Question.** Does a field-aligned (axial) magnetic field at LEO strength move
the anchor's operating point — through gun optics, plume containment, or
collection? Pre-registered in `../MAGNETIZED_PLAN.md` (hypothesis H-M1-null:
at 1× LEO, nothing moves outside the anchor's own bands).

**Deck.** The 200 V anchor with exactly one change: `plasma.Bz_T: 3.0e-5`.
Gyro-resolution of the timestep is enforced in `helpers.py`
(ω_ce·dt check). Everything else, including grid and step count, is the
anchor's, so the run is a clean A/B along the field axis.

**Result (gated PASS, 2026-08-10, run `20260810T064845Z_5e785001`).**
**Null confirmed**: φ_body 17.22 V, F_beam 13.64 nN, escape 98.44 %, exhaust
KE 147.3 eV — the anchor's operating point within its bands (Δφ ≈ +1 V,
ΔF +0.3 %). H-M1-null holds; the near-field, field-aligned half of the
magnetized question is closed. The open half is tier M2 — **transverse** B,
the actual LEO flight geometry, whose ~1.4 m beam gyroradius cannot fit the
30 mm domain (see `../MAGNETIZED_PLAN.md` and `/OPTIMISTIC_HYPOTHESES.md` H1).
Details: `reference_results/20260810T064845Z_5e785001/REFERENCE.md`.

**Provenance.** Executed 2026-08-10 as a variant deck through the anchor stage
under the pre-registered exploratory policy `capstone.exploratory_axes.v1`
(launch record `../m1_chain.sh`, logs in `logs/`); frozen run config and
manifests carry `stage_id: capstone.floating_body`. This `config.yaml` is that
deck (git-moved) under the new stage id; `acceptance.yaml` re-identifies the
same gates for future runs. `outputs/20260808T130303Z_5e785001` is an earlier
launch of the same deck with no gated result (superseded).

**Re-run.** `python simulation.py` then
`python analyze.py --run outputs/<RUN_ID> --policy acceptance.yaml`
(~6.5 GPU-hours; CUDA build required, see `/SETUP.md`).
