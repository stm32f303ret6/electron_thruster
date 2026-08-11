# reference results -- emitter.voltage_bracket

`joint_0157ab7c/` is the curated snapshot of the three-scenario **voltage-bracket cohort** (200 V / 300 V / 92.4 V),
**PASS -- all 11 required gate(s) passed** under policy `emitter.voltage_bracket.v2`.

Scenarios A and B close the emitter branch's voltage gap (VALIDATION_GAPS.md G3): the capstone's 200 V anchor and 300 V ceiling commands, both at 23.9 % of the planar Child-Langmuir scale, transmit identically (spread 0.006 pp). Scenario C -- the 92.4 V ucurve command at **133.5 %** of the planar scale -- transmitted **0.9999**, refuting the v1 policy's required current-limiting gate: the planar I_CL over the emission spot is a conservative scale for this geometry, and the transmission loss `emitter.holed_anode` B measured at 79 % of the same scale was aperture clipping through the small hole, not virtual-cathode limiting. The v1 FAIL analysis (`20260807T204601Z_8f54b654`) is retained under `results/` as the recorded refutation; this v2 verdict re-gates the measured mechanism (transmission flat across voltage AND planar-scale fraction), so the capstone throttle-curve tax is attributable to the can's own gap and collection physics, not generic gun optics.

| gate | result | status |
|---|---|---|
| A_collector_transmits | 0.99999 >= 0.96 | PASS |
| B_collector_transmits | 1.00005 >= 0.96 | PASS |
| C_collector_transmits | 0.999884 >= 0.96 | PASS |
| transmission_flat_across_bracket | 5.70495e-05 <= 0.02 | PASS |
| C_transmission_flat_vs_A | 0.000106044 \|x - 0\| <= 0.02 | PASS |
| A_collector_ke_conserved | -0.0191419 \|x - 0\| <= 1.5 | PASS |
| B_collector_ke_conserved | -0.0447229 \|x - 0\| <= 1.5 | PASS |
| C_collector_ke_conserved | 0.027493 \|x - 0\| <= 1.5 | PASS |
| A_budget_closure | 0.000699831 \|x - 0\| <= 0.1 | PASS |
| B_budget_closure | 0.000699831 \|x - 0\| <= 0.1 | PASS |
| C_budget_closure | 0.000971937 \|x - 0\| <= 0.1 | PASS |

Runs:
- `20260807T203301Z_A_200v_anchor_drive_0bb2c097`  case `0bb2c09709d8cd3b...`  git `9e1240cb1089` (dirty: False)
- `20260807T203716Z_B_300v_ceiling_drive_58e09715`  case `58e0971500fa80cc...`  git `9e1240cb1089` (dirty: False)
- `20260807T204111Z_C_ucurve_overperveance_335806d6`  case `335806d6539477af...`  git `9e1240cb1089` (dirty: False)

Policy `emitter.voltage_bracket.v2` sha256 `9b72cb0b4fbc2b4d...`, analysis `20260808T104718Z_9b72cb0b`, WarpX 26.5, seed 42.

The machine-readable record is `metrics.json` + `verdict.json` + the frozen
`config_used.yaml` of the run they describe; `run_manifests.json` carries the
full run manifest. Raw dumps (fields h5, ledger CSV) stay out of git and are
reproducible from `config_used.yaml` + seed. A reference result is read only
for comparison; it never makes `simulation.py` skip a run. Ladder-wide caveats
(reduced ion mass, single grid/PPC/seed, finite-time equilibrium on the ion
clock) are documented in the stage README and `SCALING_LAWS.md`.
