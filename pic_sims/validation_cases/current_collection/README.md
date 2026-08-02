# current_collection — the collector branch

A conducting **sphere** (embedded boundary) in the ionospheric plasma of the
electron_contactor **chipsat capstone** (n0 = 1.627e12 m⁻³, kTe = 113.6 meV,
Ti = 936.2 K, reduced ion mass 400 mₑ) — at fixed bias in the first three
rungs, floating on the capstone's charge pump in the fourth. The ambient
plasma is maintained by one-sided Maxwellian **flux injection** from the
three open faces on top of a bulk fill at t = 0.

Each stage is a **self-contained folder** (its own `simulation.py`, `helpers.py`,
`analyze.py`, `config.yaml`, `acceptance.yaml`, tests). The PIC deck is
duplicated verbatim across the fixed-bias three so the differing domains, time
steps, and gates are obvious per folder — there is no shared `cc_common.py`
any more; `4_floating` adds the charge pump to the same deck.

## The ladder

| Stage | dir | bias | key theory | main gates |
|---|---|---|---|---|
| `collector.thermal`   | `1_thermal`   | 0 V  | I_th = n·e·⟨v⟩/4·4πa², **exact for any convex probe**; I_th_e = 0.10393 µA, ratio = 23.74 | I_e 5%, I_i 10%, ratio 8%, density 5% |
| `collector.biased_3v` | `2_biased_3v` | +3 V | OML ceiling I_th·(1+χ), χ = 26.4 → 2.847 µA | I_e/I_OML ∈ [0.85, 1.05] |
| `collector.biased_10v`| `3_biased_10v`| +10 V| χ = 88.0 → 9.249 µA; **sheath growth** | I_e/I_OML ∈ [0.80, 1.05]; edge containment |
| `collector.floating`  | `4_floating`  | floats | current balance: φ_f between thermal-ion −0.360 V and OML-ion −0.213 V | φ_f bracket; \|I_e−I_i\|/I_i ≤ 15%; C vs 4πε₀a; ledger-vs-dump |

`collector.biased_3v` requires `collector.thermal`; `collector.biased_10v`
requires `collector.biased_3v`; `collector.floating` requires
`collector.thermal` and runs the chipsat capstone's charge-pump mechanism
(see `4_floating/README.md` — it closes `capstone/2_chipsat_thruster/VALIDATION_GAPS.md` G2).

## Why this branch also validates the chipsat configuration

Every numerical choice the chipsat case rides on is used here unchanged and gated
against closed-form theory: plasma row, **dx = 0.15 mm = 13.1 cells/λ_De**,
**ppc = 16**, flux-reservoir injection, domain sizing vs sheath. The sphere puts
**a/λ_De = 0.382** — the sub-Debye point where the electron_contactor OML study
measured 93% of the ceiling (the cross-code reference for the biased rungs).

## Cross-stage expectations (checked by `run_ladder.py` / `cross_stage.py`)

- `collector_current_fraction_trend`: I_e/I_pred falls monotonically 0 V → 3 V →
  10 V (barrier deepening grows with χ).
- `collector_sheath_radius_ordering`: the |φ| = kTe/e sheath radius grows with
  bias.
- `collector_shared_plasma_parameters`: all three share plasma / ppc / probe
  radius.

## Ion-clock caveat (why ions are gated loosely or not at all)

Collected **electron** current equilibrates on the electron/plasma clock
(~0.06 µs); **ion** current and sheath structure on the ion clock (√(mi/me) ≈ 20×
slower). At positive bias the ions should be Boltzmann-suppressed to ~zero, but
ions already inside the domain at t = 0 never had to climb the barrier, so the
measured trickle starts high and decays on the ion clock — reported, never gated.

## Run cost

Measured on the CPU build (2026-08-01): thermal ~16 min, +3 V ~65 min,
+10 V ~80 min, floating ~37 min — the original "GPU-only" assumption is
retired (verified reference runs for all four rungs were produced on CPU).
Run ONE at a time (each caps its arena but they contend). There is no
checkpointing: a killed run is FAILED and restarts from zero (an interrupted
run is rerun from scratch, by design).

## Known risks (documented up front)

- **RZ radial-face flux over-emission**: the r = r_max injection face has a known
  WarpX over-emission quirk (z-normal faces calibrate to ~1.0). The far-field
  density gate is the arbiter.
- **EB faceting**: at 5 cells/radius the staircased EB area sits ~1–2% below
  4πa², pushing ratios slightly **low** (inside the 5% electron gate).
- **t = 0 spike**: bulk particles born inside the sphere are scraped in the first
  steps; the last-40% steady window excludes the transient.
- **Not yet gated** (Phase 5): stationarity of the +10 V steady window (~4%
  drift), zero-bin accounting, and a connected-sheath-edge containment metric.
