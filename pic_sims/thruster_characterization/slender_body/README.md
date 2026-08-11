# characterization.slender_body — the geometry axis

**Question.** Where does the float settle when total skin grows 3.24×
(3.17 → 11.0 cm²) at fixed drive and fixed commanded current — i.e. does
collection scale with area (hypothesis A, φ ≈ 4–5 V) or does the elongated
wall collect like an OML cylinder (hypothesis B, tens of volts)?
Pre-registered 2026-08-05 in `SLENDER_BODY_PLAN.md`, before the run.

**Deck.** The 200 V anchor deck with the can lengthened to Ø10 × 30.5 mm
(`z_bot: -30 mm`, L/r = 6) and — the load-bearing fix — `cathode_standoff:
4.7 mm`, which pins the gun gap at its short design value while the body grows
around it. The first attempt (2026-08-05) inherited the floor-tied cathode,
stretched the gap to 29.7 mm, exceeded the Child–Langmuir ceiling ~60× and
self-scraped; it was killed at 69 % and produced the design rule *grow the
body around the gun, never stretch the gun* (`CAMPAIGN.md` §4.1, §6.5).

**Result (gated PASS, 2026-08-06, run `20260806T011847Z_5670e54c`).**
φ_body **4.378 V** (tail mean; still rising, settled plausibly ~5–6 V),
F_beam **14.22 nN**, escape 98.42 %, exhaust KE 159.7 eV. Hypothesis A
confirmed; B refuted by an order of magnitude. Because KE = κ(V − φ), the
lower float *returns* drive energy to the beam: the slender can out-thrusts
the squat anchor (13.65 → 14.22 nN) at the same current and drag bill.
Details and settle caveat: `reference_results/20260806T011847Z_5670e54c/REFERENCE.md`.

**Provenance.** Executed as a variant deck through the anchor stage
(`../../ladder/capstone/2_chipsat_thruster`) under the pre-registered
exploratory policy `capstone.exploratory_axes.v1`; the frozen run config and
manifests therefore carry `stage_id: capstone.floating_body`. This folder's
`config.yaml` reproduces that deck (verified against the frozen
`config_used.yaml`) under the new stage id; `acceptance.yaml` re-identifies
the same trust gates for future runs. Launch logs: `logs/`.

**Re-run.** `python simulation.py` then
`python analyze.py --run outputs/<RUN_ID> --policy acceptance.yaml`
(~6.5 GPU-hours; CUDA build required, see `/SETUP.md`).
