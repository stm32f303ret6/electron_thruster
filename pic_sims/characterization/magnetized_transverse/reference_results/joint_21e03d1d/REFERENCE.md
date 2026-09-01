# reference result — characterization.magnetized_transverse

Curated snapshot of a verified run+analysis. Read only for comparison;
its presence never makes a runner skip a run. The machine-readable
record is `metrics.json` + `verdict.json` here.

## Result

Verdict FAIL (exit 1): 22 of 24 required gates PASS; the two failures are transverse_10x trust gates and are the finding for that corner, not a defect of the deck. b0_control (8/8 required + all reported bands): phi 13.37 V, F_beam 14.42 nN, escape 99.06 %, C 0.622 pF - the 1 mm solid-body 3D deck closes on the RZ anchor inside every pre-registered band. transverse_1x (8/8 + all null bands): dphi +0.29 V, dF_thrust -0.14 %, descape 0.00 pp, Lorentz correction -0.04 % - H-M2-null CONFIRMED at flight field. transverse_10x: phi 66.5 V still rising 0.031 V/ns at 800 ns and edge |phi| 1.04 V > 1 V (current balance 6.8 % > 5 %): the 66.5 V float and the -14.3 % thrust tax are bounds from an unsettled, box-limited state; every pre-registered prediction band nevertheless holds (dphi +53.1 V in [20,60]; dF -14.3 % in [-25,-5]; Lorentz correction +3.6 % in [2,8]; ledger vs reduced diag 0.9 %).

## Provenance

- **stage:** `characterization.magnetized_transverse`
- **verdict:** **FAIL** (exit 1)
- **policy:** `characterization.magnetized_transverse.v1`  sha256 `9b3513becfca342d…`
- **analysis id:** `20260901T194231Z_9b3513be`
- **git commit:** `148a7af6ccf0e4f67943a9f2cfb3481b118d2bc9` (dirty=False)
- **WarpX:** 26.5  |  **Python:** 3.12.13

## Runs

- `20260901T174526Z_b0_control_d6f56019` (scenario `b0_control`)  case_sha256 `d6f56019eaf6b908…`  study_sha256 `c3ee1a09d947ae4c…`
- `20260901T182023Z_transverse_1x_6a65fe5a` (scenario `transverse_1x`)  case_sha256 `6a65fe5a07a70559…`  study_sha256 `c3ee1a09d947ae4c…`
- `20260901T190346Z_transverse_10x_8ab76d60` (scenario `transverse_10x`)  case_sha256 `8ab76d605aae74d9…`  study_sha256 `c3ee1a09d947ae4c…`

## Gates

- [PASS] `b0_beam_escapes` — 99.0599 >= 95
- [PASS] `b0_steady_current_balance` — 0.0246499 <= 0.05
- [PASS] `b0_momentum_sanity_bound` — 0.00969009 <= 1
- [PASS] `b0_sheath_and_plume_contained` — 0.352012 <= 1
- [PASS] `b0_scrape_ledger_consistent_with_dumps` — 9.32804e-09 <= 0.02
- [PASS] `b0_beam_escape_ledger_consistent_with_dumps` — 6.91116e-09 <= 0.02
- [PASS] `b0_source_delivers_commanded_current` — 1.00127 |x - 1| <= 0.03
- [PASS] `b0_capacitance_calibration_sane` — 0.621923 in [0.35, 1.2]
- [PASS] `t1x_beam_escapes` — 99.0592 >= 95
- [PASS] `t1x_steady_current_balance` — 0.0250932 <= 0.05
- [PASS] `t1x_momentum_sanity_bound` — 0.00946258 <= 1
- [PASS] `t1x_sheath_and_plume_contained` — 0.35758 <= 1
- [PASS] `t1x_scrape_ledger_consistent_with_dumps` — 1.25776e-09 <= 0.02
- [PASS] `t1x_beam_escape_ledger_consistent_with_dumps` — 9.45439e-09 <= 0.02
- [PASS] `t1x_source_delivers_commanded_current` — 1.00127 |x - 1| <= 0.03
- [PASS] `t1x_capacitance_calibration_sane` — 0.621923 in [0.35, 1.2]
- [PASS] `t10x_beam_escapes` — 98.9222 >= 95
- [FAIL] `t10x_steady_current_balance` — 0.0679811 <= 0.05
- [PASS] `t10x_momentum_sanity_bound` — 0.0474674 <= 1
- [FAIL] `t10x_sheath_and_plume_contained` — 1.03591 <= 1
- [PASS] `t10x_scrape_ledger_consistent_with_dumps` — 3.84921e-09 <= 0.02
- [PASS] `t10x_beam_escape_ledger_consistent_with_dumps` — 2.07685e-09 <= 0.02
- [PASS] `t10x_source_delivers_commanded_current` — 1.00127 |x - 1| <= 0.03
- [PASS] `t10x_capacitance_calibration_sane` — 0.621923 in [0.35, 1.2]
- [PASS] `b0_closes_on_anchor_float` — 13.3687 |x - 17| <= 4
- [PASS] `b0_closes_on_anchor_thrust` — 14.4204 |x - 13.65| <= 1
- [PASS] `b0_lorentz_term_vanishes` — 0 |x - 0| <= 0.1
- [PASS] `t1x_null_float` — 0.293196 |x - 0| <= 2
- [PASS] `t1x_null_thrust` — -0.13917 |x - 0| <= 5
- [PASS] `t1x_null_escape` — -0.000688636 |x - 0| <= 1
- [PASS] `t1x_lorentz_correction_negligible` — -0.03681 |x - 0| <= 0.2
- [PASS] `t10x_float_tax_in_band` — 53.1406 in [20, 60]
- [PASS] `t10x_thrust_tax_in_band` — -14.2626 in [-25, -5]
- [PASS] `t10x_lorentz_correction_in_band` — 3.58522 in [2, 8]
- [PASS] `t10x_lorentz_ledger_matches_reduced_diag` — 0.00854124 <= 0.25
- [PASS] `b0_benign_float` — 13.3687 <= 50
- [PASS] `t1x_benign_float` — 13.6619 <= 50
- [FAIL] `t10x_benign_float` — 66.5093 <= 50
