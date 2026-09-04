# reference result — characterization.magnetized_transverse

Curated snapshot of a verified run+analysis. Read only for comparison;
its presence never makes a runner skip a run. The machine-readable
record is `metrics.json` + `verdict.json` here.

## Result

Verdict PASS (exit 0): all 18 required gates, including the settledness gate both scenarios (late dphi/dt 0.0019 / 0.0020 V/ns vs the 0.005 requirement; current balance < 1e-4). The first fully settled operating point for this system on the model's ion clock: b0_control floats at 26.76 V with F_beam 13.91 nN, exhaust 146.3 eV, escape 99.83 % - thrust within 2 % of the committed RZ anchor despite the float sitting 10 V above the anchor's 800 ns reading. transverse_1x (flight-strength field, worst orientation): float 29.35 V, F 13.81 nN, escape 99.82 %, Lorentz correction +0.03 %. Deltas vs the settled control: dphi = +2.60 V (JUST outside the pre-registered +-2 V null band - the one new physics finding: a small, real magnetized-collection tax on the float, resolvable only at the settled equilibrium), dthrust = -0.75 % (inside +-5 %), descape = 0.00 pp. The thrust/escape null holds; the float null is refined to a +2.6 V (+10 %) shift, far inside the 50 V benign limit.

## Provenance

- **stage:** `characterization.magnetized_transverse`
- **verdict:** **PASS** (exit 0)
- **policy:** `characterization.magnetized_transverse.settled.v1`  sha256 `2ea5449d7525f463…`
- **analysis id:** `20260904T012209Z_2ea5449d`
- **git commit:** `334154546b1605342316825b809a002df5a66dd8` (dirty=False)
- **WarpX:** 26.5  |  **Python:** 3.12.13

## Runs

- `20260902T084534Z_b0_control_232cd445` (scenario `b0_control`)  case_sha256 `232cd445aa2b3db8…`  study_sha256 `c1b28dc641fcf7eb…`
- `20260903T040431Z_transverse_1x_487c410e` (scenario `transverse_1x`)  case_sha256 `487c410eb6b6c49a…`  study_sha256 `c1b28dc641fcf7eb…`

## Gates

- [PASS] `b0s_beam_escapes` — 99.8254 >= 95
- [PASS] `b0s_steady_current_balance` — 0.000103475 <= 0.05
- [PASS] `b0s_momentum_sanity_bound` — 0.0175581 <= 1
- [PASS] `b0s_sheath_and_plume_contained` — 0.176411 <= 1
- [PASS] `b0s_scrape_ledger_consistent_with_dumps` — 2.37635e-09 <= 0.02
- [PASS] `b0s_beam_escape_ledger_consistent_with_dumps` — 3.08893e-09 <= 0.02
- [PASS] `b0s_source_delivers_commanded_current` — 1.00017 |x - 1| <= 0.03
- [PASS] `b0s_capacitance_calibration_sane` — 0.593564 in [0.35, 1.2]
- [PASS] `b0s_tail_settled` — 0.00192166 |x - 0| <= 0.005
- [PASS] `t1xs_beam_escapes` — 99.8243 >= 95
- [PASS] `t1xs_steady_current_balance` — 0.000173464 <= 0.05
- [PASS] `t1xs_momentum_sanity_bound` — 0.0180478 <= 1
- [PASS] `t1xs_sheath_and_plume_contained` — 0.172292 <= 1
- [PASS] `t1xs_scrape_ledger_consistent_with_dumps` — 2.35935e-10 <= 0.02
- [PASS] `t1xs_beam_escape_ledger_consistent_with_dumps` — 5.15653e-10 <= 0.02
- [PASS] `t1xs_source_delivers_commanded_current` — 1.00017 |x - 1| <= 0.03
- [PASS] `t1xs_capacitance_calibration_sane` — 0.593564 in [0.35, 1.2]
- [PASS] `t1xs_tail_settled` — 0.00195036 |x - 0| <= 0.005
- [FAIL] `b0s_float_in_band` — 26.7552 in [14, 21]
- [PASS] `b0s_thrust_in_band` — 13.9138 |x - 14.2| <= 0.8
- [PASS] `b0s_lorentz_term_vanishes` — 0 |x - 0| <= 0.1
- [FAIL] `t1xs_null_float` — 2.59509 |x - 0| <= 2
- [PASS] `t1xs_null_thrust` — -0.754495 |x - 0| <= 5
- [PASS] `t1xs_null_escape` — -0.00112661 |x - 0| <= 1
- [PASS] `t1xs_lorentz_correction_negligible` — 0.0258579 |x - 0| <= 0.2
- [PASS] `b0s_benign_float` — 26.7552 <= 50
- [PASS] `t1xs_benign_float` — 29.3503 <= 50
