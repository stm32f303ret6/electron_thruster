# capstone.floating_body — the chipsat electron-thruster capstone

The top rung — **the thruster test itself**: emitter + collector physics in
one self-consistent system.  The stage ID names the defining mechanism under
validation (the body FLOATS while the gun fires — the thruster only works if
it floats to a benign potential); the thrust is gated directly
(`f_beam_nN`).
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

## Reviewer question: do the emitted electrons come back to the craft?

They measurably do not — and the stage *measures* this instead of assuming
it.  Escape is an energy-headroom condition: every beam electron starts on
the cathode, which the internal supply holds at `phi_body − 200 V`, so it
reaches infinity (plasma potential 0) with ≈ e·(200 V − phi_body) of kinetic
energy.  At the measured float (+16.98 V) that headroom is ~183 eV, and the
escaped beam indeed leaves with the full injection-plane energy (exhaust KE
147.5 eV vs −φ(injection plane) = 148.1 eV; ledger closes to 0.6 eV).
Return is possible only through specific mechanisms, and the per-step
beam-fate ledger (`FloatingBody.collect` classifies every scraped beam
macroparticle by electrode region) accounts for each:

| mechanism | ledger column | validated run (tail mean) |
|---|---|---|
| virtual-cathode stall (space charge reflects beam back to the cathode) | `pct_cathode` | **0.0000 %** |
| interception by BODY surfaces (space-charge-widened spot / thermal tail clipping the lid hole) | `pct_body` | **0.53 %** |
| true escape | `pct_escape` | **98.44 %** (gated ≥ 95 %) |

(the remaining 1.03 % is still in flight in the plume at end of run; both
return channels are REPORTED metrics, `beam_return_cathode_pct` /
`beam_return_body_pct`, from analysis runs after 2026-08-02).  Zero cathode
return at γ = I/I_CL = 1.46 means no virtual cathode forms at this drive;
that mechanism is exercised deliberately in `emitter.holed_anode` scenario B,
and the geometric-clipping mechanism in scenario A.

The "low enough spacecraft potential" premise is not left to luck — it is
enforced in three independent layers:

1. **Measured equilibrium** — the body floats to +16.98 V ≪ 200 V because
   the ionosphere neutralizes the escaping 0.342 mA (the `current_balance`
   gate is exactly this identity).
2. **Design box** — `design_sims/opmodel.py::Constraints.validate` refuses
   `phi_max ≥ v_min` outright ("else the beam can be fully stalled inside
   the allowed box"): the float limit is 50 V against a ≥ 100 V supply
   floor, and rung 9's night case sits exactly on that binding constraint
   (predicted φ_body = +50 V at a 300 V drive — still 250 V of headroom).
3. **Runtime watchdog** — `phi_body > 100 V` sustained 50 ns aborts the run
   CHOKED/FAILED rather than reporting a stalled thruster as data.

Caveat: the 0 % cathode return is a demonstration at this operating point
(single grid/ppc/seed, γ_CL = 1.46), not a theorem for all drives.

### Once outside, can the +17 V body pull them back? (Debye screening)

No — the body's attraction has finite *range*, not just finite depth,
because the ambient plasma screens it over the sheath scale (a few
λ_De = 1.97 mm; rungs 4–5 measure exactly that screening scale growing with
bias — 4.12 mm at +3 V, 6.89 mm at +10 V — and gate its containment).  An
electron that has climbed out of the screened well with energy to spare can
never be called back electrostatically.  The deck makes this measured, not
assumed:

- the domain is sized so a boundary crossing IS a genuine escape: ≥ 35 mm
  ≈ 18 λ_De of plasma above the lid, put there precisely so "the +z exhaust
  plume must reach φ ~ 0 so a z_hi crossing is a genuine escape"
  (`config.yaml`, `domain.zmargin_hi`);
- the `edge_phi_max_V` gate measures the leftover attraction where escapes
  are counted: **37.6 mV** (0.33 kTe/e) against a 1 V gate — the escaping
  electrons' 147.5 eV is ~3,900× the residual potential that would have to
  turn them around;
- the exhaust KE is measured *at the boundary* and matches −φ(injection
  plane) to 0.6 eV: the full climb out of the +17 V well was already paid
  inside the domain, and the rest is kept.

So the sharp statement is not "cross one Debye length" but "climb out of
the Debye-screened sheath well": the crossing is guaranteed by the energy
headroom above, the permanence by the screening.  One honest exclusion: the
model is electrostatic — no geomagnetic field (Bz stays a research variant
in `electron_contactor`).  In orbit a 148 eV electron gyrates with
r_g ≈ 1.4 m at ~30 µT, two orders above the craft scale, but whether a
gyrating plume can re-intersect a moving chipsat is beam-propagation
physics outside this domain and this ladder.

## Reviewer question: where is the neutralizer?

The thruster is its own neutralizer, and the stage verifies the closed
circuit rather than assuming it.  A conventional ion thruster ejects
positive charge and needs a separate electron-emitting neutralizer; this
concept inverts that — ejecting electrons charges the craft *positive*, and
the neutralizer role is played by the craft's own conducting surface
immersed in the ionosphere, which collects the ambient-electron return
current.  There is no neutralizer hardware anywhere in the system.

The floating body IS the closed-circuit measurement: nothing pins
`phi_body`, so a steady state exists only if the ionosphere resupplies the
escaping charge at a benign potential.  Validated-run tail means (run
ledger; reported metrics `i_escape_mA` / `i_amb_e_mA` / `i_amb_i_mA` from
analyses after 2026-08-02):

| term | value | role |
|---|---|---|
| I_escape | **0.340 mA** | beam current leaving to space |
| I_amb_e | **0.330 mA** | ambient electrons collected by the +17 V body — the return current |
| I_amb_i | **0.0003 mA** | ambient ions (repelled by the positive body; 0.1 % correction) |
| \|I_escape − (I_amb_e − I_amb_i)\| / I_escape | **3.2 %** | the gated `current_balance` identity |

Every layer under this claim has its own rung: rungs 3–5 gate the ambient
**collection physics** (thermal and OML electron collection at the
capstone's own plasma/dx/ppc), rung 6 gates the **float mechanism** (the
charge pump drives a conductor to the current-balance potential, checked
against the closed-form floating potential), and the capstone joins them
with the gun firing — the equilibrium that rung 6 finds at −0.251 V with no
emission moves to **+16.98 V** when the beam demands 0.34 mA of
neutralization.

Two honest qualifiers.  First, the **infinite-reservoir recycle** is
exactly the "ionosphere as unbounded electron source" assumption — without
it the finite domain would deplete and the run would measure reservoir
size, not neutralizer capacity; the real question "can *this* ionosphere
row supply the current at φ ≤ φ_max?" is the design model's
`i_ceiling / i_demand` starvation ratio, and rung 9's night case
(`B_night_worst`) sits exactly where that capacity binds (float limit
φ_max = 50 V, thrust capped by the thin night-time ionosphere).  Second,
the ion term uses the reduced 400 mₑ mass ladder-wide — negligible here
(ions are 0.1 % of the return budget), but a real-O⁺ I_amb_i would be
~8.6× smaller still.

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
