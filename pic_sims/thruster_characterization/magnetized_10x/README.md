# characterization.magnetized_10x — magnetic axis, tier M1b (Bz = 300 µT, 10× LEO)

**Question.** Where does the field-aligned axis *start* to matter? 10× LEO is
the deliberate overdrive point of the M1 pair (`../MAGNETIZED_PLAN.md`,
hypothesis H-M1-tax): if 1× is a null, the 10× run locates the mechanism that
eventually bites.

**Deck.** The 200 V anchor with exactly one change: `plasma.Bz_T: 3.0e-4`.
Same grid, same step count — a clean A/B against the anchor and against
`../magnetized_1x/`.

**Result (gated PASS, 2026-08-10, run `20260810T131955Z_0b81e70a`).**
**A real collection tax, entirely through the float**: φ_body 48.63 V
(≈ +33 V over the anchor, disclosed caveat: still climbing at 800 ns),
F_beam 12.06 nN (−11 %), escape 98.32 % (beam formation unharmed), exhaust
KE 115.9 eV — the thrust loss enters through KE = κ(V − φ) as the magnetized
skin collects less effectively, not through the gun. Combined with the 1×
null this brackets the field-aligned axis; the transverse geometry (tier M2)
remains the open risk and can move thrust in either direction.
Details: `reference_results/20260810T131955Z_0b81e70a/REFERENCE.md`.

**Provenance.** Executed 2026-08-10 as a variant deck through the anchor stage
under the pre-registered exploratory policy `capstone.exploratory_axes.v1`
(launch record `../m1_chain.sh`, logs in `logs/`); frozen run config and
manifests carry `stage_id: capstone.floating_body`. This `config.yaml` is that
deck (git-moved) under the new stage id; `acceptance.yaml` re-identifies the
same gates for future runs. `outputs/20260808T130307Z_0b81e70a` is an earlier
launch of the same deck with no gated result (superseded).

**Re-run.** `python simulation.py` then
`python analyze.py --run outputs/<RUN_ID> --policy acceptance.yaml`
(~6.5 GPU-hours; CUDA build required, see `/SETUP.md`).
