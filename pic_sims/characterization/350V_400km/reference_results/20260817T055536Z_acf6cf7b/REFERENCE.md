# reference results -- characterization.350V_400km

`20260817T055536Z_acf6cf7b/` is the curated snapshot of the **350 V envelope
extension (the 400 km-enabling drive)**: full production run (207,280 steps,
800 ns), GPU build, **PASS -- all 7 required gate(s) passed** under policy
`characterization.350V_400km.v1`.

Pre-registered predictions vs measured: thrust 40.5 nN predicted (frontier
F ~ V^2) vs **40.48 nN measured**; float 47 V predicted (fitted collection
law) vs **48.29 V tail-averaged** -- both laws hold one step past the tested
ceiling, and the model's 400 km axial row (V_min = 304 V) is now an
interpolation inside the measured 100-350 V envelope. Covers the 400 km
axial mean drag gate (40.48 >= 32.9 nN, ~81 % duty).

**Settle caveat (the honest margin):** the gated float is the tail mean
(48.29 V over the last 160 ns), but phi at run end is 51.14 V and still
rising at +33.8 mV/ns -- the settled float extrapolates ABOVE the 50 V
benign design limit. The 350 V squat can sits ON the limit, not inside it;
the benign-float PASS is marginal and finite-time. The slender-geometry
sibling (`../../350V_400km_slender/`, predicted phi ~ 11-17 V) is the
pre-registered route to margin at this drive.

| gate | result | status |
|---|---|---|
| beam_escapes | 99.1136 >= 95 | PASS |
| body_floats_benign | 48.2905 <= 50 | PASS |
| steady_current_balance | 0.0321098 <= 0.05 | PASS |
| momentum_sanity_bound | 0.0110069 <= 1 | PASS |
| sheath_and_plume_contained | 0.153704 <= 1 | PASS |
| scrape_ledger_consistent_with_dumps | 1.61787e-10 <= 0.02 | PASS |
| beam_escape_ledger_consistent_with_dumps | 1.61008e-10 <= 0.02 | PASS |
| covers_400km_mean_drag (reported, not required) | 40.4832 >= 32.9 | PASS |

Exhaust KE tail mean 237-239 eV vs injection-plane prediction 240.7 eV and
ideal V_GAP - phi = 301.7 eV (the kappa energy factor, consistent with the
ladder).

Provenance: run `20260817T055536Z_acf6cf7b`, case `acf6cf7b74a5fb88...`,
git `bbacde15a6cd` (dirty: True -- the pre-registered spoke folder was
untracked at launch; config_used.yaml is the frozen deck), seed 42,
WarpX 26.5, analysis `20260817T133738Z_0518d3ce`,
wall 2026-08-17T05:55:36Z -> 2026-08-17T13:37:26Z (~7.7 h).

The machine-readable record is `metrics.json` + `verdict.json` + the frozen
`config_used.yaml` of the run they describe; `run_manifests.json` carries the
full run manifest. Raw dumps (fields h5, ledger CSV) stay out of git and are
reproducible from `config_used.yaml` + seed. A reference result is read only
for comparison; it never makes `simulation.py` skip a run. Ladder-wide caveats
(reduced ion mass, single grid/PPC/seed pending the convergence pass,
finite-time equilibrium on the ion clock) are documented in the stage README
and `SCALING_LAWS.md`.
