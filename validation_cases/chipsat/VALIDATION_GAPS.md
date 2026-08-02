# Validation gaps: what the ladder does and does not prove about the chipsat

The premise of the ladder is that by the time `capstone.floating_body` runs,
every numerical choice it rides on has already passed a gate somewhere cheaper.
This document audits that claim against the actual capstone deck
(`electron_contactor` float200 baseline). First what genuinely carries over,
then the gaps, ordered by how much they matter.

## What the lower rungs DO validate for the capstone (verified matches)

| capstone ingredient | value | validated by | match |
|---|---|---|---|
| plasma row n0/Te/Ti/mi | 1.627e12 m⁻³ / 1318.8 K / 936.2 K / 400 mₑ | `collector.*` (all three) | identical |
| cell size dx | 0.15 mm = 13.1 cells/λ_De | `collector.*` far-density gates | identical |
| ambient ppc | 16/species (bulk + flux) | `collector.*` shot noise inside 5 % gate | identical |
| flux-reservoir injection | bulk + 3 one-sided Maxwellian faces, Γ = n·vth/√2π, ν-matched layouts | `collector.*` far-density + quasineutrality | identical construction |
| EB collection + scraping | conducting EB absorbs, per-species accounting | `collector.*` current gates | same mechanism |
| domain-sizing vs sheath | edge-\|φ\| watchdog a few cells inside open boundaries | `collector.biased_10v` (THE gate there) | same metric, capstone gates it too |
| prescribed-current z-flux emission | expression-gated disc spot, Gaussian flux momentum | `emitter.negative_cathode` (calibrates to ~1.0) | same mechanism |
| aperture transmission vs space charge | hole clips thermal tail / space-charge blowup | `emitter.holed_anode` A/B/C | same mechanism |
| energy conservation through a holed plate | arrival KE = drop from emission plane | both emitter rungs | same bookkeeping |
| RZ ES solver + particle_shape=1 + seed 42 | Multigrid, 1e-6 | every rung | identical |

## Gaps

### G1 — ~~The two-node piecewise EB potential is validated nowhere~~ **CLOSED 2026-08-01**
Closed by the new rung **`capstone.two_node_laplace`** (`chipsat_two_node/`):
the capstone's exact can geometry and grid, in vacuum, with BODY pinned at
+16 V and CATHODE at −184 V through the same potential string and per-step
`set_potential_on_eb` rewrite. Gates: assigned surface values (cathode exact,
body 0.22 V cut-cell), the Laplace maximum principle (exact), agreement with
an independent stair-step sparse-direct solve (1.86 V ≥ 20 cells out), and
bit-exact rewrite idempotency. The cross-stage check
`two_node_matches_capstone_geometry` hash-verifies the frozen geometry/dx/
offset against the capstone's. *Remaining residue:* cut-cell field accuracy
AT the surface is only bounded to 1 V, and the vacuum stage cannot see
plasma–EB interaction (G6 territory).

### G2 — ~~The floating-potential charge pump has no analytic rung~~ **CLOSED 2026-08-01**
Closed by the new rung **`collector.floating`**
(`current_collection/4_floating/`): the thermal rung's sphere in the same
plasma, with the potential computed every step by the capstone's charge pump
(transcribed verbatim: Gauss-law C calibration at the 1 V init solve, per-step
dQ from the scrape buffers, `set_potential_on_eb` rewrite). The analytic
anchor is the floating potential bracketed by the two limiting ion-collection
models: thermal-ion −0.360 V and OML-ion −0.213 V (φ_f is independent of C,
isolating the dQ accounting). Also gated: equilibrium current balance,
Gauss-law C vs 4πε₀a (measured ratio 1.07 ≈ the grounded-box correction), and
the G5-style ledger-vs-dump consistency. The cross-stage check
`floating_shares_thermal_configuration` hash-verifies plasma/ppc/radius
against `collector.thermal`. *Remaining residue:* one node, no beam — the
two-node float under beam load first occurs in the capstone (G6).

### G3 — Gun operating point differs from the validated emitter rungs
| quantity | emitter rungs | capstone | status |
|---|---|---|---|
| accelerating voltage | 100 V | 200 V | not bracketed in the ladder (the contactor's own E-sweep 78–300 V exists but outside the ladder) |
| accel gap | 1.9 mm planar, flat mid-plate | 4.7 mm inside a closed can | different geometry class; I_CL scale differs |
| beam current | 10 µA (A) / 400 µA (B,C) | 342 µA | bracketed ✓ |
| aperture radius | 0.7 / 1.4 mm | 2.0 mm | larger than C's restored-transmission hole → favorable side ✓ |
| launch temperature (per-axis rms) | 2.10e5 m/s (0.25 eV) | 2.60e5 m/s (0.39 eV) | capstone beam is hotter; thermal-tail clip σ_r ~24 % larger — not covered by A's calibrated bound |
| emission ppc | 128/cell/step | 16/cell/step | emission graininess at 16 ppc unvalidated by the emitter rungs |

### G4 — Reservoir recycling (add_particles re-injection) is unvalidated
Collectors validate the *flux* reservoir; the capstone additionally *recycles*
every EB-collected ambient particle back into the outer shell (banked weight →
Maxwellian at n∞, every 25 steps, its own RNG). Injection-weight calibration
and the isotropic re-injection are not gated anywhere below the capstone.
*Mitigation:* report far-shell density in capstone analysis (not gated — the
recycle shell confounds it); current-balance gate catches gross errors.

### G5 — Per-step scrape-buffer accounting vs post-hoc dumps
The pump trusts `get_particle_scraped_this_step` (buffer-cleared-per-step
semantics) every step; the ladder only ever reads accumulated openPMD scrape
dumps after the run. No rung checks the two agree.
*Closed in migration:* `analyze.py` adds a `scrape_charge_consistency` gate —
cumulative CSV ledger charge vs openPMD scrape totals must agree to ≤ 2 %.

### G6 — Beam + ambient plasma never coexist below the capstone
Emitter rungs are vacuum; collector rungs are beamless. Beam–plasma coupling
(neutralization dynamics, plume potential structure, beam-driven sheath
asymmetry) first appears at the top. This is inherent to the ladder topology —
it is exactly why the capstone's evidence kind is *system integration
regression*, not analytic verification. No cheaper rung can close it.

### G7 — Sheath containment is an extrapolation, not a repeat
`collector.biased_10v` gates containment for a +10 V pinned sphere in an
11 λ_De box. The capstone floats to ~+17 V body (cathode −183 V, but enclosed)
in a 15 λ_De box with an exhaust plume crossing z_hi. Same metric, new regime.
*Mitigation:* the capstone gates edge-\|φ\| itself (≤ 1 V).

### G8 — Steady state is a finite-time equilibrium on the ion clock
The capstone's 800 ns plateau still has non-zero late dφ/dt (the analysis
prints it honestly); collectors showed ion-clock relaxation takes ~2 µs for
this plasma. The float200 regression numbers are therefore an 800 ns snapshot,
not a demonstrated stationary state. Ties to refactor-plan **C6** — a
stationarity gate is Phase 5 work, and the capstone tail metrics inherit that
caveat.

### G9 — Acceptance gates are self-referential regression values
escape ≥ 95 %, F_beam = 13.6 nN ± 15 %, φ_body = 16 ± 4 V were read off the
validated float200 run — they are calibration, per plan §9.3, and are
disclosed as such in `acceptance.yaml` and the stage README. The only
theory-anchored gates in the capstone are current balance, \|F_net\| ≤ F_beam,
and edge containment.

### G10 — Shared numerics that are *consistently unvalidated*
- **Reduced ion mass 400 mₑ** everywhere (ladder + capstone): internally
  consistent, but every real-O⁺ conclusion is an unvalidated extrapolation
  (the contactor flags this too).
- **dt regime**: capstone dt ≈ 5.0e-12 s (beam CFL) differs from every rung's
  dt; each rung validated its own CFL/ωpe·dt, and the capstone's satisfies the
  same invariants, but no rung ran ambient plasma at beam-scale dt.
- **Single grid/PPC/seed** across the whole ladder — convergence evidence is
  the refactor plan's **C12** (Phase 5); the capstone inherits it.

### G11 — Dropped machinery (accepted trade-offs, not oversights)
- Checkpoint/restart is not migrated (plan defers it): an interrupted capstone
  run is FAILED and rerun (~GPU-hours at stake per interruption).
- Probe/pinned mode, shroud, ram drift, Bz: research configs stay in
  `electron_contactor`; the migrated stage is the float200 baseline only.

## Priority summary

1. **G1/G2: CLOSED (2026-08-01)** by the two new rungs `collector.floating`
   and `capstone.two_node_laplace` — the capstone's two core mechanisms are
   now ladder-validated, not just lineage-validated. Both are required
   dependencies of `capstone.floating_body` in `ladder.py`.
2. **G3** would be closed by one extra `emitter.holed_anode` scenario at
   200 V / 4.7 mm-gap-equivalent / rms 2.6e5 / ppc_beam 16.
3. **G5** is closed by the consistency gates (capstone: ambient-e AND
   beam-escape channels; `collector.floating` repeats the check on an
   analytically-anchored rung).
4. **G6–G10** are inherent or Phase 5 items; they are documented in the stage
   README so the capstone's PASS is never over-claimed.
