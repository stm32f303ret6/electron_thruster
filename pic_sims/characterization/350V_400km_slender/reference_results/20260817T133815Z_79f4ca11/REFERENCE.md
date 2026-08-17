# reference results -- characterization.350V_400km_slender

`20260817T133815Z_79f4ca11/` is the curated snapshot of the **slender body at
the 400 km-enabling drive (350 V, L/r = 6)** -- the fourth corner of the 2x2
voltage x geometry factorial: full production run (207,280 steps, 800 ns),
GPU build, **PASS -- all 7 required gate(s) passed** under policy
`characterization.350V_400km_slender.v1`.

**The composed laws hold.** Pre-registered predictions vs measured: float
11-17 V predicted (geometry collection law scaled from the slender 200 V
point through the voltage frontier) vs **14.00 V tail-averaged measured** --
dead center of the band; thrust 42-43 nN predicted vs **43.33 nN measured**.
With all four factorial corners now measured, the voltage frontier
(100-350 V) and the geometry law (L/r 1.1-6) compose into a validated 2D
operating map.

The mission-relevant contrast with the squat sibling at identical drive:

| | squat can (`../../350V_400km/`) | slender (this run) |
|---|---|---|
| float phi (tail) | 48.29 V -- ON the 50 V limit, endpoint 51.1 V rising | **14.00 V** -- 3.6x margin, endpoint 15.8 V |
| thrust | 40.48 nN | **43.33 nN** (+7 %, the returned-float KE bonus) |
| 400 km mean drag (32.9 nN) | ~81 % duty | **~76 % duty** |
| escape | 99.11 % | 99.14 % |

Settle caveat: phi at run end is 15.76 V with a +20.8 mV/ns late slope --
still drifting, band quoted 14-17 V settled; the 35 V distance to the limit
makes the benign verdict robust regardless (same argument as the slender
200 V run's 10x hypothesis gap).

| gate | result | status |
|---|---|---|
| beam_escapes | 99.1382 >= 95 | PASS |
| body_floats_benign | 14.0011 <= 50 | PASS |
| steady_current_balance | 0.043643 <= 0.05 | PASS |
| momentum_sanity_bound | 0.0101813 <= 1 | PASS |
| sheath_and_plume_contained | 0.0577296 <= 1 | PASS |
| scrape_ledger_consistent_with_dumps | 7.18356e-10 <= 0.02 | PASS |
| beam_escape_ledger_consistent_with_dumps | 7.57795e-10 <= 0.02 | PASS |
| covers_400km_mean_drag (reported, not required) | 43.3286 >= 32.9 | PASS |

Exhaust KE tail mean 272.7 eV vs injection-plane prediction 274.6 eV and
ideal V_GAP - phi = 336.0 eV (the kappa energy factor, consistent with the
ladder).

Provenance: run `20260817T133815Z_79f4ca11`, case `79f4ca1177081bb9...`,
git `bbacde15a6cd` (dirty: True -- the pre-registered spoke folder was
untracked at launch; config_used.yaml is the frozen deck), seed 42,
WarpX 26.5, analysis `20260817T232525Z_1112e593`,
wall 2026-08-17T13:38:15Z -> 2026-08-17T23:25:14Z (~9.8 h).

The machine-readable record is `metrics.json` + `verdict.json` + the frozen
`config_used.yaml` of the run they describe; `run_manifests.json` carries the
full run manifest. Raw dumps (fields h5, ledger CSV) stay out of git and are
reproducible from `config_used.yaml` + seed. A reference result is read only
for comparison; it never makes `simulation.py` skip a run. Ladder-wide caveats
(reduced ion mass, single grid/PPC/seed pending the convergence pass,
finite-time equilibrium on the ion clock) are documented in the stage README
and `SCALING_LAWS.md`.
