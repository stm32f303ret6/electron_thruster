# design_sims — from a mission row to an operating point

`orbit_sims/` says how much drag must be cancelled and in what ionosphere.
`pic_sims/` says what actually happens when you fire an electron gun there. This
tree is the thing in between: a 0-D model whose every constant is an exact
algebraic inversion of a **committed PIC measurement**, used to pick the
operating point and to predict what the next PIC run should find.

```
station_keeping.csv          calibration/laws.yaml          config.yaml scenarios:
(n_e, Te, Ti, drag_N)   +    (k, ke_ledger, f_esc, beta)  ->  (V, I) + predictions
```

## Environment

numpy + PyYAML + matplotlib + scipy only, so it imports in either conda env.

```bash
python3 operating_point.py --csv ../orbit_sims/validation_cases/400km_station_keeping_chipsat/results/station_keeping.csv \
                           --emit scenarios.yaml --plots plots/
python3 -m calibration          # print the loaded constants and their provenance
PYTHONNOUSERSITE=1 python -m pytest tests/ -q
```

## The contract

| file | role | who writes it |
|---|---|---|
| `calibration/laws.yaml` | the constants | **only** `refit_laws.py` |
| `calibration/runs/*.yaml` | one promoted PIC measurement each | **only** `promote.py` |
| `calibration/__init__.py` | the loader, and the provenance refusal | — |
| `opmodel.py` | the four laws + the operating-point solver | — |
| `operating_point.py` | CSV → scenario selection → YAML + plots | — |

**Dependency direction is one-way.** This tree reads the orbit CSV and
`pic_sims/`'s committed `reference_results/*/metrics.json`. Nothing in
`pic_sims/` imports anything here — a PIC stage that read the live `laws.yaml`
would silently re-validate itself against whatever the model currently believes.
Constants reach a stage only by being **frozen into that stage's committed
`config.yaml`** before the run.

## The provenance rule, and why it is enforced in code

Every constant in `laws.yaml` carries the in-tree path of the `metrics.json` it
was derived from **and that file's SHA-256**. A constant missing either is
refused at load time with a `ProvenanceError` — not warned about, not defaulted.

This is not paranoia; it is a specific inherited failure. The predecessor's
`laws.yaml` stated the rule in its own header —

> *An entry without provenance is an assumption wearing a measurement's clothes.*

— and then shipped with **every cited run deleted**, its own header admitting
that "no constant in this file is currently reproducible from anything in the
working tree". The numbers stayed in circulation for months. Here that state is
unloadable rather than merely documented, and
`tests/test_calibration_loader.py` reproduces each way it can arise (vanished
anchor, changed anchor, missing entry) and asserts the refusal.

## The four laws

| | form | constant | value |
|---|---|---|---|
| thrust | `F[nN] = k·I[mA]·√(KE[eV])`, `KE = ke_ledger·(V−φ)` | `k`, `ke_ledger` | 3.28652, 0.806016 |
| escape | `I_escape = f_esc·I_beam` | `f_esc` | 0.984364 |
| collection | `I_return(φ) = β·I_the(n_e,Te)·(1 + eφ/kTe)`, `I_the = e·A·n_e·√(kTe/2πm_e)` | `β`, `A` | 0.46158, 3.2987 cm² |
| settle | `τ ≈ C·φ/I` | `C` | 0.5563 pF |

All four are inverted from the single committed reference run
(`capstone.floating_body`, float200: 13.652 nN, +16.977 V, 98.436 % escape,
147.52 eV at 0.342 mA / 200 V / n_e = 1.627e12 / Te = 1318.8 K). `k/k_ideal =
0.975` is the escape-plus-injection-offset penalty against the no-loss slope.

### What changed vs the predecessor's model

The old area law was `I_max ∝ area^0.85 · n_e` — **no Te dependence at all**,
while the IRI data swings Te over 800–3400 K. The new collection law carries Te
in two places that pull in opposite directions, and the net sign is the one
people get backwards:

> `I_the` grows as `√Te`, but the `(1+χ)` pull weakens as `1/Te`. At the
> χ ≈ 150–400 this design runs at, the second wins: **at fixed potential the
> collection ceiling goes as `n_e/√Te`.** Hot dayside electrons are *harder* to
> collect per unit density, not easier.

Only a body sitting at plasma potential (χ → 0) sees the bare `n_e·√Te` flux.
`tests/test_opmodel.py` pins both limits.

### Two roots, and why the solver is closed-form

`I` and `φ` are coupled — more current charges the body higher, and a higher body
robs the beam of energy. Substituting the collection law's inverse into the
thrust law makes thrust an explicit function of current:

```
φ(I) = a·I − b        a = (kTe/e)·f_esc/(β·I_the),  b = kTe/e
F(I) = k·I·√(ke_ledger·(V + b − a·I))
```

`F(0) = 0` and `F → 0` again as `φ → V`, so **F has an interior maximum** and a
thrust demand generally has *two* solutions. The rising branch is the one to fly
(same thrust, less current, less power) and the maximum is closed-form
(`I* = 2(V+b)/3a`), which turns "is this row feasible at all?" into an exact
question instead of a search that might have missed a root.

## Results on the 2024 400 km mission

Run against `orbit_sims/.../station_keeping.csv` (105 121 rows, csv sha
`5500c9e4…`), constraints `V ∈ [100, 300] V`, `φ ≤ 50 V`, `I ≤ 1.5·I_CL`:

```
drag        mean 32.921 nN, p95 61.331 nN, max 92.367 nN
deliverable mean 25.235 nN at full throttle
continuous thrust meets demand on 28.7 % of rows
required duty cycle 130.5 %  ->  DOES NOT CLOSE even at 100 % duty
```

**The mission as currently specified does not close.** At 400 km in 2024 (near
solar maximum, real historical F10.7/Ap) an *axial* 5 mm chipsat needs 33 nN
mean and the thruster tops out at 25 nN mean — the emission ceiling
`1.5·I_CL(300 V) = 0.647 mA` caps thrust near 31 nN no matter how dense the
plasma is.

That is a finding, not a blocker, and the levers are visible in the same model:

- **Attitude.** `orbit_sims` `rotation: lateral` cuts S_ref from 8.34e-5 to
  5.48e-5 m² (broadside is the *low*-drag pose for a squat r = h can), scaling
  mean drag to ≈ 21.7 nN — an 86 % duty cycle, which closes. This is the
  cheapest lever by far and costs one 11-minute orbit re-run.
- **Emission ceiling.** Thrust is pinned by `γ_CL·I_CL`, which scales as
  `V^1.5/d_gap²`. A shorter accelerating gap or a larger emission spot moves it
  directly; the PIC ladder would have to re-anchor `γ_CL` if it moved far.
- **Altitude.** Drag falls much faster with altitude than collection does.

The two PIC scenarios below are selected from the axial (conservative) mission,
because validating the model where it is most stressed is the point.

## The selection rule

Committed in `operating_point.py`, not chosen by hand. Rows come from the real
CSV; nothing is invented.

- **`A_day_p95`** — the nearest-rank 95th percentile of `drag_N`. Dayside peak
  demand; probes the **emission/space-charge** side.
- **`B_night_worst`** — the row minimising the supply margin
  `i_ceiling(row, φ_max)/i_demand(row, v_max)`, **subject to a settle-time
  guard** `τ = C·φ/I ≤ 0.25·t_end`. Probes the **collection** side.

The guard matters: τ grows as `1/n_e`, so the true worst row of the year would
still be charging when a 1 µs PIC run ends, and a gate on a transient means
nothing. When the guard bites, the substitution is written into the emitted
scenario block as a `note:` — disclosed, not silent.

Selected (2026-08-02):

| | row | UTC | n_e [m⁻³] | Te [K] | drag [nN] | V | I [mA] | φ_pred [V] | F_pred [nN] | χ | τ | binding |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| A_day_p95 | 31526 | 2024-04-19T23:10 | 2.138e12 | 1529 | 61.33 | 300 | 0.6468 | 26.35 | 31.57 | 200 | 23 ns | `γ_CL` |
| B_night_worst | 80173 | 2024-10-05T21:05 | 1.972e11 | 1505 | 56.86 | 300 | 0.1139 | 50.00 | 5.31 | 386 | 244 ns | `φ_max` |
| *anchor (reference)* | — | — | 1.627e12 | 1319 | — | 200 | 0.3420 | 16.98 | 13.65 | 149 | 28 ns | — |

Different binding constraints and χ spanning 149 → 386 is the point: it probes
the `(1+χ)·n_e/√Te` law form and the `γ_CL` calibration independently. The
true worst-margin row (74419, n_e = 4.4e10, margin 0.031) was excluded by the
guard at τ = 995 ns; the honest claim is that continuous-thrust validation
extends to the guard boundary and the mission is duty-cycled below it.

## VALIDATION RESULT (2026-08-03): the collection law is wrong

`pic_sims`'s `capstone.mission_envelope` rung ran both operating points below
and **failed 2 of 22 pre-registered gates**. The failure is specific and
useful.

**Three of the four laws transferred out of sample**, at 1.5× the fitted
voltage and across 11× in density:

| | anchor (fitted) | A_day_p95 | B_night_worst |
|---|---|---|---|
| `k` | 3.2865 | 3.2999 (+0.4 %) | 3.3252 (+1.2 %) |
| `ke_ledger` | 0.8060 | 0.8010 (−0.6 %) | 0.8012 (−0.6 %) |
| `f_esc` | 0.9844 | 0.9899 | 0.9949 |
| `β` | 0.4616 | **0.3967** | **1.0078** |

**β is not a constant, and it is not a function of χ.** It is non-monotonic in
χ (0.462 at χ=149, 1.008 at χ=178, 0.397 at χ=234). Regressing `ln β` against
each candidate variable, only density gives consistent exponents:

| β tracks… | anchor→A | anchor→B | A→B | spread |
|---|---|---|---|---|
| `(1+χ)` | −0.338 | +4.490 | −3.407 | 7.90 |
| `r_p/λ_D` | −2.415 | −0.697 | −0.788 | 1.72 |
| **`n_e`** | **−0.555** | **−0.370** | **−0.391** | **0.19** |

So `I_return ∝ n_e^0.58·√Te·(1+χ)`, not linear in density. The physical reading:
**β is the OML-efficiency factor and tracks `r_p/λ_D`** — at `r_p/λ_D` = 0.83
the body collects at full OML (β ≈ 1.0), at 2.5–2.7 it is barrier-limited to
40–46 %. The two readings cannot be separated by these three points, which all
sit at Te ≈ 1320–1530 K.

**Consequence for the mission.** The error is optimistic in dense day rows and
pessimistic at night — and night is where the margin is thin. Re-evaluating all
105 121 rows with an indicative `β(n) = 0.4616·(n/1.627e12)^−0.42`:

| | deliverable ⟨F⟩ | duty cycle | rows meeting demand |
|---|---|---|---|
| as-validated | 25.235 nN | 130.5 % | 28.7 % |
| indicative β(n) | 28.195 nN | 116.8 % | 41.9 % |

Indicative only — that form has not itself been validated.

**`laws.yaml` has deliberately NOT been refitted.** Averaging β across three
points where it is manifestly not constant would replace a visible failure with
an invisible one. The next step is a revised *form*
(`β₀·(r_p/λ_D)^−q`), a new `laws.yaml`, policy `capstone.mission_envelope.v2`
with fresh predictions, and a re-run — never a widened tolerance.

## Promotion discipline

```bash
python3 promote.py --analysis <a passing pic_sims analysis dir> --name <record>
python3 refit_laws.py --write        # or --check, which is what CI wants
```

`promote.py` **refuses** an analysis whose `verdict.json` is not `PASS`: a number
the ladder rejected must not calibrate the model the ladder validates.
`--force --reason '…'` exists for the rare deliberate case and writes the reason
*into the record*, so a reader of the YAML sees it without going back to shell
history.

**Changing a constant invalidates downstream evidence.** A PIC stage that froze
the previous values and gated a prediction against them is no longer testing the
model that now exists: it needs a new policy version and fresh runs.
`refit_laws.py --write` says so every time.

## Caveats that travel with every number here

- **Surrogate ion mass.** The whole ladder uses `m_i = 400 mₑ`, not O⁺. Drag is
  real (NRLMSISE-00 on observed F10.7/Ap); the plasma *response* is not.
- **No ram drift, no B-field.** The ionosphere is at rest and unmagnetised in
  the PIC model.
- **One anchor point.** Every constant comes from a single operating point
  (200 V, χ = 149). `k` and `ke_ledger` are used out to 300 V; the archived
  800 V record implies ~4 % drift over 4× voltage. The `(1+χ)` linearity is
  extrapolated from χ = 149 to 386 — which is exactly what the
  `capstone.mission_envelope` stage exists to test, and a failure there is a
  finding about the law form, not a tolerance to widen.
