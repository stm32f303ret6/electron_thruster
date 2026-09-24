# Cathode launch: correcting κ = 0.81, with settled floats

> **Status (2026-09-23): plan only, nothing run.** Step 1 (correct the
> explanation of κ in the docs, no numbers changed) is done. Steps 2 (PIC
> confirmation) and 3 (recalibrate and rerun the mission analysis) are below,
> for the author's review before anything runs.

## The finding

κ = 0.81 in `KE = κ(V − φ)` is set by where the simulated beam is born, not
by gun physics.

1. The beam is launched 2 cells (0.3 mm) above the cathode face
   (`pic_sims/ladder/capstone/2_chipsat_thruster/helpers.py`, `z_emit`; the
   comment explains why: a launch on the embedded-boundary face puts
   macroparticles in the covered cut cell, where WarpX scrapes them). The
   body-potential floor ring sits 2 cells from the cathode edge.
2. A vacuum Laplace solve of the can (axisymmetric, sparse direct, converged
   at 25–50 µm) puts the launch plane, averaged over the r ≤ 0.5 mm emission
   spot, **19.0 % of V** above the cathode. The outside plasma potential
   couples in at 0.1 %.
3. Every committed run shows the deficit ΔV = (V − φ) − KE as a fixed
   fraction of V, not of V − φ:

   | runs | I/I_CL | ΔV / V |
   |---|---|---|
   | anchor, 100 / 300 / 350 V, slender (200, 350 V), thin plasma, Bz 1× and 10× | 1.46 | 0.174–0.181 |
   | U-curve valley / left arm / floor (125 / 92.4 / 78 V) | 4.0 / 8.2 / 14.7 | 0.165 / 0.146 / 0.116 |

   At the frontier loading the deficit is 35.5 V at 200 V whether φ is 4.4 V
   or 48.6 V (Bz 10×, where KE/(V − φ) drops to 0.77). The ~1 % of V between
   the vacuum 19.0 % and the measured 17.4–18.1 % is the beam's own space
   charge pulling the launch point down; at higher loading it pulls further
   and the deficit shrinks. A space-charge depression of the exhaust energy
   would do the opposite.
4. In a steady electrostatic field an electron's energy at the domain edge is
   e(φ_edge − φ_launch). Emitted at cathode potential it leaves with
   e(V − φ): a real cathode has κ ≈ 1.

Consequences at 200 V: +11 % thrust at the same current (√(183/147.5)),
η 0.73 → 0.90. In the mission model (KE = V − φ in place of 0.806(V − φ),
everything else unchanged):

| case | mean power | duty @ 350 V |
|---|---|---|
| 400 km, 2024, equatorial | 292 → 255 mW (−13 %) | 102 → 92 % |
| 400 km, 2024, sun-synchronous | 278 → 241 mW (−13 %) | 100 → 90 % |
| 500 km, 2024 | 47.9 → 41.8 mW (−13 %) | 25 → 22 % |
| 600 km, 2024 | 9.9 → 8.7 mW (−12 %) | 7.5 → 6.8 % |
| 400 km, 2019 | 21.2 → 18.5 mW (−13 %) | 16 → 14 % |

400 km near solar maximum would close on average inside 350 V; about a third
of its points would still need more.

## Why the runs must be long (the author's point)

The float settles on the ion clock, and every committed RZ float is an
800 ns snapshot. The thin-plasma run rose ×1.44 from 800 ns to its settled
2.4 µs value; the 3D transverse-field campaign found the 800 ns floats at
about half their 6 µs settled values. The mission model's collection law is
fitted to 800 ns floats (paper limitation 1). A higher settled float costs
exhaust energy through KE = e(V − φ) and partly offsets the κ gain, so the
mission answer needs both corrections, measured together.

A single long corrected run would mix the two effects (launch fix and
settling). Hence a matched pair, both run to settling:

## Step 2: the PIC pair

A new characterization spoke, `pic_sims/characterization/cathode_launch/`,
self-contained per `pic_sims/ARCHITECTURE.md` (its own `simulation.py`,
`config.yaml`, `helpers.py`, `analyze.py`, `acceptance.yaml`, tests,
`reference_results/`). The anchor stage and its evidence stay untouched.

| run | deck | launch | length |
|---|---|---|---|
| **2A control** | capstone 200 V anchor, verbatim | today's: 2 cells up, thermal spread only | to settled, cap 6 µs |
| **2B corrected** | the same | 2 cells up, plus a directed velocity along +z worth the skipped potential | to settled, cap 6 µs |

- Launch correction. `picmi.AnalyticFluxDistribution` already injects a
  Gaussian flux with `rms_velocity`; 2B adds `directed_velocity =
  [0, 0, v_L]` with ½ m_e v_L² = e ΔΦ_L. ΔΦ_L is read from the deck's own
  field at the launch cells, in 2A's supply-on/gun-off window
  (100–150 ns), not from the external solve (expected ≈ 0.19 V, 38 V at
  200 V, v_L ≈ 3.7 × 10⁶ m/s). Using the vacuum value over-corrects by the
  ~1 % of V the beam's space charge removes; that bias is stated, not tuned.
- Matched pair. Same grid, domain, seed, plasma row, current (0.342 mA),
  dt and analysis windows. The deck derives dt from the full drop
  (`v_beam = √(2eV/m_e)`, `helpers.py`), so it already covers 2B's faster
  beam and is identical in both runs. The injected current must stay
  0.342 mA with the drift added: the deck scales the flux by a
  `flux_correction`, so 2B re-verifies the emitted-current ledger before the
  long run (a short smoke run).
- Length. Until the settledness gate of
  `magnetized_transverse/acceptance_settled.yaml` passes (|dφ/dt| ≤
  0.005 V/ns over the closing 50 ns), capped at 6 µs. The pair is compared
  at 800 ns (against the committed anchor) and at the settled end.
- Gates. The capstone trust gates (escape, current balance, net force,
  edge potential, ledgers) plus settledness.
- Diagnostics. The anchor's, plus the launch-plane potential over time
  (the space-charge offset, measured).

### Predictions (recorded before any run)

| quantity | prediction | falsified if |
|---|---|---|
| KE_2B − KE_2A, matched time | +32 to +36 eV (0.16–0.18 V) | < +24 eV (0.12 V): part of the deficit is real gun physics |
| KE_2B vs e(V − φ_2B) | within 3 % | > 5 % short |
| F_2B / F_2A, same current | 1.10–1.12 | < 1.06 |
| escape, 2B vs 2A | ≥ | 2B lower by > 1 pp |
| φ_2B vs φ_2A | within ±10 % (same escaping current, same collection) | differs by > 20 % |
| 2A settled φ vs its 800 ns value (17.0 V at 800 ns) | ×1.3–2 (22–34 V) | settles below 19 V or above 40 V |
| 2A settled thrust vs 800 ns | down 1–5 % (float tax via KE) | moves > 10 % |

### Cost

About 0.17 s per step on the RTX 3060 (thin plasma: 477 k steps in 22.4 h),
and dt ≈ 4.5–5 ps, so 1 µs ≈ 9–10 h. A full 6 µs run is ~55–60 h; the pair
~5 days sequential on one GPU. If both settle by ~2.4 µs, as the thin-plasma
run did, ~23 h each. Running the two concurrently on the one GPU saves no
compute.

Optional 2C, decided after 2A/2B: the 350 V slender corrected run to
settling (the 400 km operating point, `350V_400km_slender`), ~2.5 days.

## Step 3: recalibrate and rerun

1. Thrust law. Replace `KE = κ(V − φ)` with the form 2B measures. If its
   residual deficit is ≤ 2 % of V, adopt `KE = e(V − φ)` and state the
   residual; otherwise `KE = (V − φ) − δ·V` with δ from 2B. The deficit
   scales with V, so one voltage calibrates it; c_F (plume divergence, 97 %)
   is unchanged.
2. Collection law. 2A gives the settled/800 ns float ratio at 200 V, but the
   other anchors (100, 300, 350 V; the slender pair) remain 800 ns values.
   Either (a) scale them by 2A's ratio as a stated assumption and carry the
   800 ns fit as the comparison, or (b) run long controls at the other
   voltages first (3–4 more runs, ~1–2 weeks of GPU). **Open.**
3. Rerun, in order: `mission_model.py --all` (44 cases), `altitude_hold.py`,
   `scale_analysis.py`, `paper/figs/make_missions.py`, then the numbers in
   the paper, README, `model/README.md`, `SCALING_LAWS.md` and
   `ALTITUDE_HOLD.md`. The 1U plan (`1U_LOW_ORBIT_PLAN.md`) uses the
   recalibrated law from the start.
4. Expected direction: −13 % mission power from the launch correction, then
   some of that back from settled floats, most at high voltage and in thin
   plasma where φ is largest. The net is what the paper reports.

## Caveats

- 2B reproduces a real cathode's exhaust energy, not its near-cathode space
  charge: its electrons start at ~38 eV, a real emitter's near zero, so the
  real space-charge limit near the cathode is not tested. The emission
  ceiling (1.46 × planar Child–Langmuir, also measured with the offset
  launch) stays an assumption; a cathode-surface emitter needs a finer mesh
  at the cathode and is a separate study.
- Ions stay at 400 m_e. Settled on that clock is not settled for real O⁺,
  which is ~9× slower (paper limitation 1 narrows, it does not close).
- One voltage, one plasma row, one seed.

## Open questions

1. Settling: gate-based early stop with a 6 µs cap, or a fixed 6 µs?
2. Run 2C (350 V slender) as well, or decide after the pair?
3. Step 3, collection law: scale the 800 ns anchors by 2A's ratio, or wait
   for long runs at every voltage?
4. The cathode-surface emission study (true near-cathode space charge):
   plan it now, or after the pair?
