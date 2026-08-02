# capstone.mission_envelope — does the design model predict the particles?

**The claim.** The 0-D operating-point model in `design_sims/` — fitted at a
single PIC operating point — predicts what the full chipsat deck actually does
at two *different* operating points, taken from a real year-long station-keeping
mission.

Every rung below this one asks "is the physics right?". This one asks a
different question: **"is the cheap model that we design with right?"** It is
the only rung whose gates are ratios against numbers written down *before* the
runs existed.

```
                 fitted here                         tested here
   n_e   1.627e12 m^-3                    2.138e12            1.972e11
   Te    1319 K                           1529 K              1505 K
   V     200 V                            300 V               300 V
   I     0.342 mA                         0.647 mA            0.114 mA
   chi   149                              ~200                ~386
         capstone.floating_body           A_day_p95           B_night_worst
```

## Evidence kind: `model_validation`, pre-registered

`capstone.floating_body` is a **system-integration regression** and says so: its
escape/F_beam/φ gate values were read off the very run they describe. This stage
is not that. `acceptance.yaml` and the `predicted:` blocks in `config.yaml` were
both committed **before either run existed**, so the predictions are in git with
a timestamp and cannot be quietly adjusted once the measurement lands.

Three guards make that more than a promise:

1. **`S__prediction_consistency ≤ 1e-9`.** `analyze.py` recomputes each
   `predicted:` block from the frozen `law_anchor:` constants and this run's own
   (V, I, n_e, Te). The frozen predictions were produced from exactly those
   rounded constants, so this is bit-identical arithmetic — anything above
   round-off means this stage's `opmodel.py` and `design_sims/opmodel.py` have
   drifted apart, and the pre-registration describes a model neither side runs.
2. **The stage never imports `design_sims`.** Constants arrive only by being
   committed into `config.yaml`. A stage that read the live `laws.yaml` would
   re-validate itself against whatever the design side currently believes, and a
   refit could silently turn a FAIL into a PASS.
3. **`cross_stage.py` re-derives the anchor every suite run** from
   `capstone.floating_body`'s *own* `metrics.json` and compares it to the frozen
   `law_anchor` at 2e-6. The model is pinned to the live measurement, not to a
   number someone typed.

## Scenario provenance

Both rows come from `orbit_sims/validation_cases/400km_station_keeping_chipsat/results/station_keeping.csv`
(105 121 rows, 2024, csv sha256 `5500c9e4…`), selected by the committed rule in
`design_sims/operating_point.py`. Nothing here was chosen by hand.

| | rule | row | UTC | n_e [m⁻³] | Te [K] | Ti [K] | drag [nN] | V | I [mA] |
|---|---|---|---|---|---|---|---|---|---|
| **A_day_p95** | nearest-rank p95 of `drag_N` | 31526 | 2024-04-19T23:10 | 2.138e12 | 1528.5 | 1383.5 | 61.33 | 300 | 0.6468 |
| **B_night_worst** | min supply margin, settle-guarded | 80173 | 2024-10-05T21:05 | 1.972e11 | 1504.9 | 1402.7 | 56.86 | 300 | 0.1139 |

### Predictions (pre-registered)

| | φ_body [V] | F_beam [nN] | exhaust KE [eV] | binding constraint | χ | τ = C·φ/I |
|---|---|---|---|---|---|---|
| A_day_p95 | +26.350 | 31.569 | 220.57 | `γ_CL` (emission ceiling) | 200 | 22.7 ns |
| B_night_worst | +50.000 | 5.311 | 201.50 | `φ_max` (float limit) | 386 | 244.3 ns |

The two sit at **different binding constraints**, which is the point: A probes
the space-charge/emission side, B probes the collection side. Two scenarios that
bound the same way would test one half of the model twice.

### The disclosed substitution

`B_night_worst` is **not** the worst-margin row of the mission. The true worst
(row 74419, 2024-09-15T21:35, n_e = 4.45e10 m⁻³, margin 0.031) would need
τ = 995 ns to settle — longer than the run — so a gate there would be testing a
transient, not an equilibrium. The selection rule therefore takes the worst row
satisfying `τ ≤ 0.25·t_end`, and both rows are recorded in the scenario's
`note:` field.

**The honest claim is bounded accordingly:** continuous-thrust validation extends
to the settle-guard boundary; below it the mission is duty-cycled on orbit
average, and this stage says nothing about it.

## Numerics per scenario

**`t_end` is per scenario, not shared.** The two operating points settle at very
different rates — τ = C·φ/I is 22.7 ns for the dense day row but 244 ns for the
thin night one — and every steady-state gate measures an equilibrium only many τ
in. A shared duration would either under-run B or waste ~5 h on A, so the schema
forces the author to state it per scenario. `run.max_steps` is 400 000 (up from
the capstone's 160 000) because the 300 V CFL step is ~4.14 ps;
`helpers.validate()` refuses a cap that truncates `t_end`.

| | t_end | t_end/τ | dt | steps | wall | grid | λ_D | dx/λ_D | r_p/λ_D | rmax/λ_D | CFL | ω_pe·dt |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| A_day_p95 | 800 ns | 35.3 | 4.135 ps | 193 440 | ~8.1 h | 200×440 | 1.85 mm | 0.081 | 2.71 | 16.3 | 0.30 | 3e-4 |
| B_night_worst | 1300 ns | 5.3 | 4.137 ps | 314 200 | ~13.1 h | 200×440 | 6.03 mm | 0.025 | 0.83 | 4.98 | 0.30 | 1e-4 |

A's 800 ns is deliberately the *same* duration as the `capstone.floating_body`
reference run, so the two are directly comparable at no extra cost.

**B's 1300 ns is set by the `current_balance` gate, not by taste.** That gate
measures `C·(dφ/dt)/I_escape`, so a run that stops while the float is still
climbing fails it for a purely finite-time reason. At 1.0 µs the tail window
would sit at 2.6–3.4 τ and the residual charging current would be ≈5 % of
`I_escape` — *exactly on* the 0.05 gate. At 1.3 µs it is ≈1.8 %, a 2.8× margin.
`tests/test_helpers.py::test_the_night_run_leaves_current_balance_margin` pins
that arithmetic so the duration cannot be trimmed without the reason failing.

Both scenarios stay inside OML's validity window (`r_p/λ_D` = 0.83 and 2.71).
The archived femtosat record found the OML-style form failing badly at
`r/λ_D ≈ 9`, which is why that ratio is reported here rather than assumed.

## Running it

```bash
conda activate warpx-cpu-mpich-dev

# smoke first: plumbing, the early phi trajectory, and the domain decision.
# t_end must exceed beam.t_on = 150 ns or the gun never fires.
python simulation.py --scenario B_night_worst --t-end 250e-9   # ~2.5 h

# the real runs -- ONE WarpX case at a time on this machine
python simulation.py --scenario A_day_p95        # ~8.1 h
python simulation.py --scenario B_night_worst    # ~13.1 h

# cohort analysis + the suite verdict
python analyze.py --runs outputs/<A-run> outputs/<B-run> --policy acceptance.yaml
cd ../.. && python run_ladder.py --analyze-only
```

`--scenario` is **required**: there is no default operating point, because a run
that silently picked one would be unattributable.

`--analyze-only` is how the suite verdict is produced for a multi-hour stage —
it re-reads the existing completed runs rather than re-running the 6.5 h
capstone dependency.

**Smoke runs are declared calibration, not evidence.** `--t-end` changes the
config hash *and* the study hash, so `lc.check_cohort` structurally refuses to
analyze a smoke run alongside a real one; and `validate_smoke()` is the only
path that relaxes the "t_end ≥ 3τ" invariant. Nothing else is relaxed.

### The domain decision point — RESOLVED, `rmax` stays at 30 mm

The smoke run existed to answer one question before ~21 hours were spent: **does
B's sheath stay inside the box?** Scenario B was run to 250 ns
(`20260802T101150Z_B_night_worst_c83ee39c`, declared calibration) and the answer
is yes, with a wide margin.

Edge |φ| was read from *every* field dump, not just the last, so the trend is
visible rather than a single frame:

| φ_body [V] | 0.99 | 5.38 | 10.57 | 14.91 |
|---|---|---|---|---|
| edge \|φ\| [V] | 0.045 | 0.020 | 0.040 | 0.056 |

Once the cathode-on transient decays (φ_body ≳ 5 V) the response is linear at
**3.77 mV of edge potential per volt of body potential**, so the predicted edge
|φ| at the full φ = 50 V float is **0.19 V — a 5× margin under the 1 V gate**.
The radial profile at the can mid-plane confirms the screening is doing its job:
|φ| falls 12.0 → 3.89 → 1.72 → 0.70 → 0.17 V across r = 1 → 5 λ_D.

`domain.rmax` therefore **stays at 30 mm**, saving the ×1.36 grid cost (~7 h
across the two runs). Had it needed to grow, it would have had to grow for the
*whole stage* before either real run started — changing it afterwards would mean
the two scenarios were not the same discretized machine.

The same smoke run also exercised the full `analyze.py` evidence path
(openPMD field and scrape readers, ledger integrals, refit) and confirmed
`prediction_consistency = 0.0` exactly, so the 1e-9 gate is measuring formula
drift and nothing else.

**Scenario A was not smoke-run.** Its domain margin is 3× more comfortable
(rmax/λ_D = 16.3 vs 5.0), it shares the deck byte-for-byte, and its distinct
risk — a 0.647 mA beam at `I/I_CL = 1.5` choking the body — is one the run's own
`phi_ceiling` watchdog aborts within 50 ns of onset rather than 8 hours later.
Its early trajectory was monitored live from `contactor_log.csv` instead.

## Gates

`acceptance.yaml`, policy `capstone.mission_envelope.v1`. Per scenario S:

| gate | bound | what it says |
|---|---|---|
| `S__current_balance` | ≤ 0.05 | the floating equilibrium IS a current balance |
| `S__f_net_over_f_beam` | ≤ 1.0 | the craft cannot catch more z-momentum than the beam carries |
| `S__edge_phi_max_V` | ≤ 1.0 V | sheath and plume contained (a clipped plume fakes escape) |
| `S__scrape_charge_consistency` (×2) | ≤ 0.02 | per-step ledger vs independent openPMD dumps |
| `S__f_beam_over_pred` | 1.0 ± 0.20 | **the thrust law, out of sample** |
| `S__phi_body_over_pred` | 1.0 ± 0.25 | **the collection law, out of sample** |
| `S__escape_fraction_pct` | ≥ 95 % | validates `f_esc` |
| `S__phi_body_V` | ≤ 75 V | sanity margin below the 100 V choke watchdog |
| `S__prediction_consistency` | ≤ 1e-9 | anti-post-hoc guard (see above) |

Cross-scenario:

| gate | bound | what it says |
|---|---|---|
| `day_minus_night_f_beam_nN` | ≥ 12 nN | the two points are actually distinguishable (predicted separation 26.3 nN) |
| `beta_log_spread` | ≤ 0.2231 (= ln 1.25) | **the law-form test proper**: β must not move between χ = 200 and χ = 386 |

### What `beta_log_spread` can and cannot see

Inverting a true `(1+χ)^p` law with the `(1+χ)` form gives
`β_meas ∝ (1+χ)^(p−1)`, so the observable spread is *exactly*
`|p−1| · ln((1+χ_B)/(1+χ_A))`. This mission's rows give χ = 200 and 386 — a
log-lever of only **0.654** — so the gate detects

```
|p − 1|  >  0.2231 / 0.654  =  0.341
```

It **would** catch a sqrt-like sheath-limited law (`p = 0.5`, spread 0.327) —
the failure mode the archived femtosat record actually hit. It **would not**
catch a mild curvature (`p = 0.8`, spread 0.131 — passes). Two operating points
1.9× apart in `(1+χ)` cannot prove more than that; buying it would take a third,
interior scenario (≈ +10 h). `tests/test_opmodel.py` pins both the lever and the
detection threshold so this claim cannot drift.

**Deviation from the stage plan, recorded.** The plan specified `≤ ln(1.5)`
against a hypothetical χ pair of 224/727 (lever 1.174), intending to catch
`|p−1| > 0.345`. The real CSV rows supply barely half that leverage, and at
`ln(1.5)` the gate would only have caught `|p−1| > 0.62` — too loose to notice a
sqrt-law, i.e. unable to do the job its own name claims. The tolerance is
therefore scaled to preserve the *intended discriminating power*:
`0.4055 × 0.654/1.174 = 0.226 ≈ ln(1.25)`. It remains ~5× above the expected
few-per-cent scatter in `β_meas` (which goes as `1/φ` at χ ≫ 1).

Reported, never gated: `late_dphidt_V_per_ns`, exhaust KE and its ratio to
prediction, observed settle time vs predicted, `k_meas` / `ke_ledger_meas` /
`beta_meas`, supply power, `I/I_CL`, χ, and thrust vs this row's drag demand.

### A FAIL here is a finding

If `beta_log_spread` fails, `I_return ∝ (1+χ)` is the wrong shape and needs a
χ-dependent β — which means a new `laws.yaml`, a new policy version, and fresh
runs. If `phi_body_over_pred` fails, the collection law is wrong somewhere
between χ = 149 and χ = 386. **Never retro-tune a tolerance to match a
measurement that has already landed.** The whole value of a pre-registered gate
is that it was allowed to fail.

## Caveats

Inherited from the rungs below, unchanged, and they travel with every mission
number this stage produces:

- **`m_i = 400 mₑ`**, not O⁺. The drag numbers are real (NRLMSISE-00 on observed
  2024 F10.7/Ap); the plasma *response* is surrogate-mass.
- **No ram drift, no magnetic field.** The ionosphere is at rest and
  unmagnetised.
- **Single grid, PPC and seed.** No convergence study at these operating points.
- **Collection physics is validated at PLASMA_MAX only.** The `collector.*` rungs
  all sit at n_e = 1.627e12. A cheap `collector.thermal`-style run at the night
  row (~2–3 h) would anchor `I_the(n, Te)` there directly; recommended,
  non-blocking, and not part of this stage.
- **Finite-time equilibrium.** 1 µs is 4.1 τ for B on the electron/charge-pump
  clock, but still short on the ion clock; `late_dphidt` is reported so the
  reader can judge.
