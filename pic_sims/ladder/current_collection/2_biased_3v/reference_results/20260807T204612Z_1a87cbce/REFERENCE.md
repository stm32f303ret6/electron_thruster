# reference results -- collector.biased_3v

`20260807T204612Z_1a87cbce/` is the curated snapshot of the sphere-at-+3 V OML step, re-gated under the **v2 policy**:
full production run, GPU build,
**PASS -- all 4 required gate(s) passed** under policy `collector.biased_3v.v2`.

Same physics, same tolerances as v1 -- the v2 policy only re-anchors the band's rationale on published probe theory (OML as an upper bound, Mott-Smith & Langmuir 1926; finite-radius reduction growing with a/lambda_De and chi, Laframboise 1966) plus this repo's own committed measurement, instead of an unpublished cross-code study. Measured **0.8523** of the OML ceiling -- reproducing the prior committed run's 0.8522 at the same seed, and consistent with the expected finite-radius reduction at a/lambda_De = 0.38, chi = 26.4.

| gate | result | status |
|---|---|---|
| electron_current_vs_oml | 0.852279 in [0.85, 1.05] | PASS |
| far_density_matches_n0 | 0.970161 \|x - 1\| <= 0.05 | PASS |
| far_field_quasineutral | 0.00251344 <= 0.02 | PASS |
| sheath_contained | 0.00252537 <= 0.5 | PASS |

Provenance: run `20260807T204612Z_1a87cbce`, case `1a87cbceda027f43...`,
git `9e1240cb1089` (dirty: False), seed 42,
WarpX 26.5, analysis `20260807T212457Z_350c2ba2`, wall 2026-08-07T20:46:12Z -> 2026-08-07T21:24:57Z.

The machine-readable record is `metrics.json` + `verdict.json` + the frozen
`config_used.yaml` of the run they describe; `run_manifests.json` carries the
full run manifest. Raw dumps (fields h5, ledger CSV) stay out of git and are
reproducible from `config_used.yaml` + seed. A reference result is read only
for comparison; it never makes `simulation.py` skip a run. Ladder-wide caveats
(reduced ion mass, single grid/PPC/seed, finite-time equilibrium on the ion
clock) are documented in the stage README and `SCALING_LAWS.md`.
