# capstone.floating_body — the chipsat capstone

The top rung: emitter + collector physics in one self-consistent system.
Migrated verbatim from the validated **float200** baseline of the
`electron_contactor` project (external, not part of this repository; see
`MIGRATION_PLAN.md`; the audit of what the lower rungs do and do not validate
is `VALIDATION_GAPS.md`).

## Physical system

```
      r=0 (axis)                         r_probe = 5 mm
  z=+0.5 +---hole----+------------------+   <- lid (BODY): washer r in [2.0, 5.0] mm
         |  r_slit   |                  |
         |           ^ beam (+z)        |   <- can wall (BODY)
  z=-5.0 +--CATHODE--+  gap  +----------+   <- floor: cathode disk r < 1.5 mm
         | phi_body - 200 V  |  BODY    |      + body floor annulus,
         +-----------+---+---+----------+      >= 2-cell insulating gap between nodes
```

A conducting can **floats electrically** in the capstone ionospheric plasma
(the identical PLASMA_MAX row, dx = 0.15 mm, and ppc = 16 the collector rungs
gate). The enclosed electron gun fires a prescribed **0.342 mA** beam
(spot r < 0.5 mm, on at 150 ns) from the cathode disk, which an internal
supply holds **200 V below the body** (on at 100 ns). Whatever clears the lid
hole escapes to space; the escaping current must be neutralized by ambient
collection, and the body potential emerges from that balance.

### The floating-body charge pump (the physics this stage adds)

1. Self-capacitance C is measured **once**, from the uniform-1 V init solve,
   by Gauss's law on the domain faces (C ≈ 0.5–1 pF; analytic scale
   4πε₀r_p = 0.556 pF).
2. Every step the net scraped charge integrates:
   `dQ = e·(dW_beam + beam_escape) − e·amb_e_coll + e·amb_i_coll`,
   `phi_body = phi0 + Q/C`. The supply is an internal EMF, so beam returning
   to ANY craft surface cancels out of dQ; only true escape charges the body.
3. The piecewise two-node EB potential (BODY = phi_body, CATHODE = phi_body −
   200 V) is rewritten every step via `set_potential_on_eb`.

A **reservoir** re-injects every EB-collected ambient particle into the outer
radial shell (r > 22.5 mm, every 25 steps) as a fresh Maxwellian — the floating
equilibrium is a current balance, and without refill the finite domain would
deplete and the run would measure reservoir size, not physics.

### Included / excluded physics

Included: everything above, self-consistently (RZ electrostatic, three species,
EB scraping, plume). Excluded (research variants stay in `electron_contactor`;
config rejects them): ram drift, applied Bz, exit shroud, pinned-probe mode,
checkpoint/restart, real-mass O⁺ (mi = 400 mₑ ladder-wide).

## What this stage proves / does not prove

**Proves** (evidence kind: **system_integration_regression**): the migrated
system reproduces the validated float200 capstone — escape ≥ 95 % (anchor
98.5 %), F_beam = 13.6 nN ± 15 %, phi_body = +16 ± 4 V — and satisfies the
internal-consistency identities: steady current balance
|I_escape − (I_amb_e − I_amb_i)|/I_escape ≤ 5 %, momentum sanity
|F_net| ≤ F_beam, sheath/plume containment (edge |φ| ≤ 1 V), and the
per-step-ledger vs openPMD-dump charge cross-check (≤ 2 %).

**Does not prove**: the regression anchors themselves (they were read off the
validated run — disclosed calibration per plan §9.3); stationarity of the
800 ns plateau (finite-time equilibrium on the ion clock — the analysis
*reports* late dφ/dt honestly; plan C6/Phase 5); grid/PPC/seed convergence
(plan C12); anything about real O⁺. See `VALIDATION_GAPS.md` for the full
audit, including the two mechanisms with **no** ladder rung beneath them
(the two-node EB and the charge pump itself, G1/G2).

## Upstream dependencies

`emitter.holed_anode` and `collector.biased_10v` — the two branch tips. The
cross-stage check `capstone_inherits_validated_configuration` additionally
asserts the frozen capstone plasma/dx/ppc hash-match `collector.thermal`'s.

## Run cost

159 160 steps at dt ≈ 5.0 ps (t_end 800 ns), 200×440 grid, ~3 M ambient
macroparticles. **Measured: 6.34 h on the CPU build (14 OpenMP threads,
0.14 s/step)** — comparable to ~6 h on an RTX 3060 with the GPU build, because
this deck is *callback-bound*: the per-step Python observer (scrape-buffer
reads + `set_potential_on_eb` rewrite) forces a host↔device round-trip every
step, so the GPU never gets to stretch its legs. Run ONE WarpX case at a time.

## Commands

```bash
conda activate warpx-cpu-mpich-dev     # (GPU build env for the real run)
python simulation.py                    # -> outputs/<run-id>/ (prints RUN_ID=...)
python analyze.py --run outputs/<run-id> --policy acceptance.yaml
python animate.py --run outputs/<run-id>              # optional movie
PYTHONNOUSERSITE=1 python -m pytest tests/ -q          # unit tests (no WarpX)
```

A CHOKED run (phi_body > 100 V sustained 50 ns — the ionosphere cannot
neutralize the current) or a non-finite phi_body aborts as **FAILED**; there
is no checkpoint/restart (an interrupted run is rerun from scratch).

## Gate definitions and tolerance rationale

`acceptance.yaml` (`policy_id: capstone.floating_body.v2`):

| gate (metric) | bound | provenance |
|---|---|---|
| `escape_fraction_pct` | ≥ 95 % | float200 regression (anchor 98.5 %) |
| `f_beam_nN` | 13.6 ± 2.04 nN | float200 regression |
| `phi_body_V` | +16 ± 4 V | float200 regression |
| `current_balance` | ≤ 0.05 | steady-state identity (theory) |
| `f_net_over_f_beam` | ≤ 1.0 | momentum bound (theory) |
| `edge_phi_max_V` | ≤ 1.0 V | containment (collector-rung style) |
| `scrape_charge_consistency` | ≤ 0.02 | ambient-e ledger-vs-dump cross-check (closes gap G5) |
| `scrape_charge_consistency_beam_escape` | ≤ 0.02 | beam-escape ledger-vs-dump cross-check (closes gap G5 for the dominant, most complex charge-pump term) |

Reported, never gated: mean exhaust KE (~146 eV anchor), the energy ledger
(injection-plane φ reconciliation), late dφ/dt (V/ns), far-shell density
(confounded by the recycle shell). Changing any tolerance requires a new
`policy_id`; every verdict records this file's SHA-256.

## Known numerical limitations

- The 800 ns horizon is a **finite-time equilibrium**: the ion-clock tail is
  still moving (late dφ/dt reported). Phase 5 adds stationarity gating.
- ppc_beam = 16 (the emitter rungs validated emission at 128) — gap G3.
- Single grid/PPC/seed; EB staircase at 0.15 mm; reduced ion mass 400 mₑ.
- `max_steps` is floored to a diag-period multiple (−11 steps vs the contactor
  baseline ≈ −0.06 ns of 800 ns) so the final dump lands on the last iteration.

## Status

**Parity-validated.** The full baseline ran on 2026-08-01 (run
`20260801T142601Z_2f822a95`, 6.34 h CPU) and **PASSed all 7 gates**,
reproducing the float200 anchors: escape 98.44 % (anchor ~98.5), F_beam
13.65 nN (13.6), φ_body +16.98 V (+16), exhaust KE 147.5 eV (~146; the
energy ledger closes to 0.6 eV), current balance 3.2 %, edge |φ| 38 mV,
ledger-vs-dump consistency 3e-9. The verified snapshot is in
`reference_results/`; the full-suite verdict (all 6 stages + all cross-stage
checks PASS) is suite `20260801T204741Z`. Scientific caveats (finite-time
equilibrium, single grid/PPC/seed, Phase 5 items) still apply as documented
above and in `VALIDATION_GAPS.md`.
