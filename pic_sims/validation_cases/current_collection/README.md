# current_collection — the collector branch

A conducting sphere (embedded boundary) in the chipsat capstone plasma, tested at increasing bias levels and then floating.

## Plasma

| Parameter | Value |
|---|---|
| Density n0 | 1.627e12 m⁻³ |
| Electron temperature kTe | 113.6 meV |
| Ion temperature Ti | 936.2 K |
| Ion mass | 400 mₑ (reduced, not real O⁺) |
| Sphere radius a | 0.75 mm |
| a/λ_De | 0.382 (sub-Debye) |

The plasma is maintained by one-sided Maxwellian flux injection from the three open faces, on top of a bulk fill at t = 0. Each stage is a self-contained folder with its own simulation, config, analysis, and tests.

## Steps

| Stage | Dir | Bias | Theory reference | Key gates |
|---|---|---|---|---|
| `collector.thermal` | `1_thermal` | 0 V | I_th = n·e·⟨v⟩/4·4πa² (exact) | I_e ≤ 5%, I_i ≤ 10%, ratio ≤ 8% |
| `collector.biased_3v` | `2_biased_3v` | +3 V | OML ceiling I_th·(1+χ), χ = 26.4 | I_e/I_OML ∈ [0.85, 1.05] |
| `collector.biased_10v` | `3_biased_10v` | +10 V | OML ceiling, χ = 88.0; sheath growth | I_e/I_OML ∈ [0.80, 1.05]; edge containment |
| `collector.floating` | `4_floating` | floats | φ_f between −0.360 V and −0.213 V | φ_f bracket; current balance; C vs 4πε₀a |

### Dependency chain

`thermal` → `biased_3v` → `biased_10v`; `thermal` → `floating` → capstone

## Why this also validates the chipsat configuration

Every numerical choice the chipsat uses is tested here against closed-form theory: plasma parameters, dx = 0.15 mm (13.1 cells/λ_De), ppc = 16, flux-reservoir injection, domain sizing. The sphere is at a/λ_De = 0.382, the sub-Debye point where the contactor OML study measured 93% of the ceiling.

## Cross-stage checks (run by `cross_stage.py`)

- `collector_current_fraction_trend`: I_e/I_pred falls as bias increases (barrier deepening)
- `collector_sheath_radius_ordering`: sheath radius grows with bias
- `collector_shared_plasma_parameters`: all three share plasma/ppc/probe radius

## Ion-clock note

Electron current settles on the electron clock (~0.06 µs). Ion current and sheath structure settle on the ion clock (~20x slower). At positive bias, ions should be suppressed, but ions already inside the domain at t = 0 never had to climb the barrier — the measured trickle decays slowly. Ion current is reported, never gated.

## Cost

| Stage | Time |
|---|---|
| thermal | ~16 min |
| biased_3v | ~65 min |
| biased_10v | ~80 min |
| floating | ~37 min |

Run one at a time.

## Known issues

- **RZ radial-face flux**: r_max injection face has a known WarpX over-emission quirk; the far-field density gate is the check
- **EB faceting**: at 5 cells/radius the staircased EB area is ~1–2% below 4πa², pushing ratios slightly low
- **t = 0 spike**: bulk particles born inside the sphere are scraped in the first steps; the last-40% steady window excludes this
- **Not yet gated** (Phase 5): stationarity of the +10 V steady window (~4% drift), zero-bin accounting, connected-sheath-edge containment metric
