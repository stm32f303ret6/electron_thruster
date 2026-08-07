# collector.floating — passive sphere on the capstone's charge pump

![Schematic](viz/schematic_4_floating.png)

Closes **`capstone/2_chipsat_thruster/VALIDATION_GAPS.md` G2** (the floating charge pump had no
ladder rung with an analytic anchor beneath the capstone): the collector
rungs' sphere (a = 0.75 mm, a/λ_De = 0.38) in the same capstone plasma, but
the EB potential is **not prescribed** — it is computed every step by the
chipsat capstone's charge-pump mechanism, transcribed verbatim from
`capstone/2_chipsat_thruster/simulation.py`:

- the EB starts at a uniform 1 V so the init solve calibrates the
  self-capacitance C by Gauss' law on the domain faces;
- every step, the scraped-this-step weights of both species are read from the
  particle boundary buffers and `dQ = e·(w_i − w_e)` accumulates into Q;
- `set_potential_on_eb` rewrites φ = φ_init + Q/C before the next solve.

With no beam, the pump must drive the sphere to the **floating potential** —
the bias where electron and ion collection balance.  That equilibrium has
closed-form anchors, giving the pump the analytic validation the capstone's
own regression anchors cannot provide.

## Analytic references

Let R = I_th_e/I_th_i = √((mi/me)(Te/Ti)) = 23.74 for this plasma.

| ion-collection model | balance equation | φ_f |
|---|---|---|
| thermal-ion (ions unaffected by φ) | exp(φ/kTe)·R = 1 | **−0.360 V** |
| OML-ion (attracted ions at the OML sphere ceiling) | exp(φ/kTe)·R = 1 − φ/kTi | **−0.213 V** |

The truth for this sub-Debye sphere lies between the two models (the biased
rungs measured ion-side collection at 85–99 % of OML ceilings).  Crucially,
**φ_f is independent of C** — C only sets the charging timescale — so the
bracket gate isolates the pump's dQ accounting and EB rewrite from the
calibration.

## What this stage proves

- The charge pump's sign conventions, per-step scrape-buffer accounting, and
  `set_potential_on_eb` rewrite drive a floating conductor to the physically
  correct equilibrium (a sign error saturates at the wrong sign; a
  double-count or missed channel lands outside the bracket).
- The Gauss-law C calibration reproduces the analytic sphere capacitance
  (measured 89.1 fF vs 4πε₀a = 83.4 fF — the ~+7 % is the grounded-box
  correction).
- The per-step ledger and the openPMD scrape dumps agree (the capstone's
  G5-style cross-check, here on an analytically-anchored rung).

## What it does NOT prove

- Nothing about the beam, the two-node EB, or the supply offset (that is
  `capstone.two_node_laplace` and the capstone itself).
- The exact φ_f value: the gate is a two-model bracket, not a single-model
  verification — the ion-collection model uncertainty is real physics, not
  numerics.
- Long-term (ion-clock ≫ 6 µs) drift of the equilibrium.

## Gates (`acceptance.yaml`, policy `collector.floating.v1`)

| gate (metric) | bound | provenance |
|---|---|---|
| `phi_float_V` | in [−0.40, −0.19] V | two-model theory bracket ±10 % noise margin |
| `current_balance` | ≤ 0.15 | equilibrium identity; ion shot-noise allowance |
| `capacitance_over_analytic` | in [0.8, 1.4] | 4πε₀a + box correction; catches O(1) mechanism errors |
| `scrape_charge_consistency` | ≤ 0.02 | ledger vs openPMD dumps (capstone G5 gate value) |
| `far_density_e_over_n0` | 1.0 ± 0.05 | carried over from collector.thermal |
| `quasineutrality` | ≤ 0.02 | carried over from collector.thermal |
| `edge_phi_max_V` | ≤ 0.2 V | φ_f is Debye-shielded to ~1e-4 V at the wall |

Reported, never gated: the Boltzmann-retardation cross-check
φ = (kTe/e)·ln(I_e/I_th_e), I_e/I_th_e and I_i/I_th_i, and the late dφ/dt.

## Run-length rationale

The pump's RC clock **slows as it settles**: near equilibrium
τ = C·kTe/(e·I_eq) ≈ 89 fF·0.114 V/6 nA ≈ 1.7 µs.  A 3 µs run (the thermal
stage's budget) would leave the tail window still sliding; 6 µs puts the
last-40 % window (3.6–6 µs) within a few percent of balance.  Set from this
arithmetic before the full run.

## Dependencies and cost

Requires `collector.thermal` (same sphere/plasma/grid — the cross-stage check
`floating_shares_thermal_configuration` hash-verifies it).
`capstone.floating_body` requires this stage.  Cost: ~35 min CPU
(100k steps at ~20 ms/step including the per-step pump callback).

## Commands

```bash
python simulation.py
python analyze.py --run outputs/<run-id> --policy acceptance.yaml
```

## Dashboard

<video src="viz/20260806T162656Z_40e77ecd_dashboard.mp4" controls width="100%"></video>

## Known numerical limitations

- Single grid/PPC/seed (ladder-wide C12; Phase 5).
- The ion-collection physics itself is validated only as a bracket here; the
  biased rungs pin the electron-side OML fractions.
- The reduced ion mass (400 mₑ) is the ladder-wide caveat, not real O⁺.
