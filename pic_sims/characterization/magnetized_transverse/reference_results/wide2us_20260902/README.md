# record — the wide/long (2 µs, ±60 mm) follow-up pair, 2026-09-02

**This is not a verified PASS snapshot.** It is the curated record of the
pre-registered wide follow-up (`../../config_wide10x.yaml`, policy
`characterization.magnetized_transverse.wide10x.v1`), which ended on a
falsification branch and is superseded for absolute numbers by the settled
6 µs pair (stage README):

- `b0_control` run `20260901T213124Z_b0_control_344318de`: **COMPLETE**
  (54 480/54 480; the process aborted at interpreter teardown after the
  manifest was published — CUDA context-destroyed during finalizer
  ordering; evidence intact). Tail φ 20.51 V (endpoint 21.10 V, late slope
  −0.019 V/ns: past its peak), F_beam 14.15 nN, escape 99.45 %, current
  balance 0.002, C_float 0.594 pF. Its φ(t) is the first measured settling
  curve for this system: 7.8 V at 400 ns, 11.6 V at 800 ns (the committed
  campaign's clock), 18.2 V at 1.2 µs, peak ≈ 21 V near 1.9 µs.
- `transverse_10x` run `20260902T040815Z_transverse_10x_dfffde81`:
  **FAILED by design (choke)** — `phi_body = +160.0 V > 150 V sustained
  50 ns at step 33 596` (1.23 µs). φ rose monotonically (12.8 V at 200 ns,
  102.6 V at 800 ns, crossed 150 V at 1.156 µs) with escape pinned at
  98.4 % while the exhaust energy collapsed 157 → 51 eV and F_thrust
  14.6 → 8.6 nN. No benign equilibrium exists below the ceiling (91 % of
  the 164.5 eV available).

The cohort verdict under `...wide10x.v1` is therefore void (one member is
not COMPLETE); the choke IS the pre-registered falsification outcome for
the 10× corner, and it also identifies the first cohort's small-box 66.5 V
as boundary-fed (the ±32 mm faces supplied the collection flux tube from
artificially nearby). Files here: both runs' ledgers, calibrations, frozen
configs and manifests, verbatim.
