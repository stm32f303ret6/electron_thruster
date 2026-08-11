# Capstone — stage map and variant-campaign index

The capstone directory holds the device runs. There are two kinds of evidence
here, and they are filed differently:

1. **Ladder stages** — the numbered folders below, each self-contained, run
   under its own `acceptance.yaml`.
2. **Variant campaigns** — one-off physics axes (geometry, density, magnetic
   field) run *through stage 2's* `simulation.py` with a modified deck, gated
   under the exploratory policy `capstone.exploratory_axes.v1`. Their runs are
   filed under `2_chipsat_thruster/{outputs,results}/` with
   `<timestamp>_<config-hash>` names, so they are invisible from directory
   listings. This file is the index that makes them findable.

To identify any run: read `2_chipsat_thruster/outputs/<run_id>/config_used.yaml`
(the frozen effective deck) — geometry (`z_bot`), density (`n0`), and field
(`Bz_T`) distinguish every variant.

## Ladder stages

| folder | stage id | what it is |
|---|---|---|
| `1_two_node_laplace` | `capstone.two_node_laplace` | two-node EB in vacuum (seconds) |
| `2_chipsat_thruster` | `capstone.floating_body` | 200 V anchor, Ø10 × 5.5 mm can (~6.3 GPU-h) |
| `3_high_thrust` | `capstone.high_thrust` | 300 V ceiling |
| `4_low_power` | `capstone.low_power` | 100 V floor |

## Variant campaigns (run through stage 2)

All run IDs below are under `2_chipsat_thruster/`. Anchor for comparison:
200 V baseline — φ_body 16.98 V, F_beam 13.65 nN, escape 98.44 %, KE 147.5 eV
(`reference_results/20260801T142601Z_2f822a95`).

### Slender body (geometry axis) — gated PASS 2026-08-06

- **Plan:** `SLENDER_BODY_PLAN.md` (pre-registered 2026-08-05, amended for the
  cathode-standoff fix after the first attempt was killed invalid)
- **Deck:** frozen copy at `outputs/20260806T011847Z_5670e54c/config_used.yaml`
  (predates the `variants/*.yaml` convention; identified by `z_bot: -0.03`,
  i.e. Ø10 × 30.5 mm, L/r = 6)
- **Run / result / reference:** `outputs|results|reference_results/20260806T011847Z_5670e54c`
- **Logs:** `slender_queue_20260805.log`, `slender_20260806.log` (this dir)
- **Result:** φ_body 4.38 V, F_beam 14.22 nN, escape 98.42 %, KE 159.7 eV —
  elongation is free; lower float returns drive energy to the beam.
  Written up in `CAMPAIGN.md` §3.2/§6.4 and `SCALING_LAWS.md` §8b.

### Thin plasma (density axis, n0/3) — gated PASS 2026-08-09

- **Plan:** `THIN_PLASMA_PLAN.md`; deck `2_chipsat_thruster/variants/thin_plasma.yaml`
- **Run / result:** `outputs|results/20260808T165839Z_41b114e2`
- **Logs:** `thin_queue_20260806.log` (this dir), `variants/thin_plasma_logs/`
- **Result:** φ_body 29.47 V, F_beam 13.04 nN, escape 98.39 %, KE 135.1 eV.

### Tier M1 magnetized (field-aligned Bz) — both gated PASS 2026-08-10

- **Plan:** `MAGNETIZED_PLAN.md`; chain script `2_chipsat_thruster/variants/m1_chain.sh`
- **Decks:** `variants/m1a_bz_1x.yaml` (Bz = 30 µT, 1× LEO),
  `variants/m1b_bz_10x.yaml` (Bz = 300 µT, 10×)
- **Runs / results:**
  - M1a: `outputs|results/20260810T064845Z_5e785001` —
    φ 17.22 V, F 13.64 nN, escape 98.44 %, KE 147.3 eV → **null at 1× LEO**
    (anchor unchanged; H-M1-null holds)
  - M1b: `outputs|results/20260810T131955Z_0b81e70a` —
    φ 48.63 V, F 12.06 nN (−11 %), escape 98.32 %, KE 115.9 eV →
    **collection tax at 10×**, entirely through φ (caveat: 10× float still
    climbing at 800 ns)
- **Logs:** `variants/m1_logs/`
- Documented in `README.md` (repo root), `OPTIMISTIC_HYPOTHESES.md`, commit `0d12463`.
  Far-field transverse coupling (tier M2) remains open.

### Housekeeping notes

- `outputs/20260808T130303Z_5e785001` and `outputs/20260808T130307Z_0b81e70a`
  are earlier launches of the same M1 decks with **no gated result** —
  superseded by the 2026-08-10 runs above.
- `results/20260805T045954Z_b87fbefc` is a 200 V anchor member of the
  2026-08-05 convergence pair (matches the anchor numbers).
