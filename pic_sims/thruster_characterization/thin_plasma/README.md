# characterization.thin_plasma — the density axis (n0/3)

**Question.** Do the collection law's fitted exponents (α, β) hold as
`r_probe/λ_D` drops 2.5 → 1.5? Pre-registered 2026-08-06 in
`THIN_PLASMA_PLAN.md` with per-α float predictions (α = 1 → 53.4 V,
0.893 → 60.9 V, 0.82 → 68.0 V, 0.5 → 160.4 V), then **unchained before
launch by scope decision** (the n-linear term was already validated ±1 % at
`collector.thermal`, and the settle limit would blur a 53–68 V
discrimination); relaunched 2026-08-08 as a gross-breakdown detector.

**Deck.** The 200 V anchor with exactly one physics change, `plasma.n0 →
n0/3` (5.4233×10¹¹ m⁻³), plus two disclosed numerics changes: `rmax` 30→40 mm
(containment for the √3× larger λ_D — the `sheath_and_plume_contained` gate is
what proves the enlargement sufficed) and a larger GPU arena.

**Result (gated PASS, 2026-08-09, run `20260808T165839Z_41b114e2`).**
Device **healthy at n0/3**: all 6 required trust gates pass, escape 98.39 %,
F_beam 13.04 nN, exhaust KE 135.1 eV. The float is **unsettled at 800 ns** —
tail mean 29.47 V, run-end above it — so the α discrimination was **not
achieved**; the recorded hard bound is **φ_settled > 31.6 V**. No gross
breakdown of the collection law was observed. Details:
`reference_results/20260808T165839Z_41b114e2/REFERENCE.md`.

**Provenance.** Executed as a variant deck through the anchor stage under the
pre-registered exploratory policy `capstone.exploratory_axes.v1`; frozen run
config and manifests carry `stage_id: capstone.floating_body`. This
`config.yaml` is that same deck (git-moved, history intact) under the new
stage id; `acceptance.yaml` re-identifies the same gates for future runs.
Launch record: `thin_plasma_chain.sh`, `logs/`.

**Re-run.** `python simulation.py` then
`python analyze.py --run outputs/<RUN_ID> --policy acceptance.yaml`
(~7 GPU-hours; CUDA build required, see `/SETUP.md`).
