# reference result — characterization.transverse_b_numerics

Curated snapshot of a verified run+analysis. Read only for comparison;
its presence never makes a runner skip a run. The machine-readable
record is `metrics.json` + `verdict.json` here.

## Result

All 8 required gates PASS. On the measurement grid (64 x 64 x 72 at 1.0 mm) and step (36.71 ps): gyrofrequency ratio 0.99968 at both 30 uT and 300 uT (the Boris phase error, 3e-4, well inside the 2e-3 gate), circle-fit gyroradius ratio 1.000000 (gate 5e-3), kinetic energy conserved to 1.7e-9 (gate 1e-6); E x B drift ratio 1.000000 (gate 1e-2) with an axial drift of 1.5e-6 of v_d over 3.0 gyroperiods. The Boris push and the applied-field mechanism reproduce the closed forms at the field strengths and resolution the transverse-B measurement uses.

## Provenance

- **stage:** `characterization.transverse_b_numerics`
- **verdict:** **PASS** (exit 0)
- **policy:** `characterization.transverse_b_numerics.v1`  sha256 `a5106fb0d5644c11…`
- **analysis id:** `20260901T174525Z_a5106fb0`
- **git commit:** `148a7af6ccf0e4f67943a9f2cfb3481b118d2bc9` (dirty=False)
- **WarpX:** 26.5  |  **Python:** 3.12.13

## Runs

- `20260901T174206Z_gyro_1x_fa935f76` (scenario `gyro_1x`)  case_sha256 `fa935f7692c776a1…`  study_sha256 `cec5b622595e2926…`
- `20260901T174213Z_gyro_10x_0d90a7ef` (scenario `gyro_10x`)  case_sha256 `0d90a7efd2254c97…`  study_sha256 `cec5b622595e2926…`
- `20260901T174220Z_exb_10x_cca068af` (scenario `exb_10x`)  case_sha256 `cca068aff48a25d5…`  study_sha256 `cec5b622595e2926…`

## Gates

- [PASS] `gyro_1x_frequency_exact` — 0.999679 |x - 1| <= 0.002
- [PASS] `gyro_1x_radius_exact` — 1 |x - 1| <= 0.005
- [PASS] `gyro_1x_energy_conserved` — 9.31858e-10 <= 1e-06
- [PASS] `gyro_10x_frequency_exact` — 0.999678 |x - 1| <= 0.002
- [PASS] `gyro_10x_radius_exact` — 1 |x - 1| <= 0.005
- [PASS] `gyro_10x_energy_conserved` — 1.67748e-09 <= 1e-06
- [PASS] `exb_drift_exact` — 1 |x - 1| <= 0.01
- [PASS] `exb_no_axial_drift` — -1.46496e-06 |x - 0| <= 0.02
