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

`run.t_end` is 1.0 µs (up from the capstone's 800 ns) because B needs 4.1 settle
times; `run.max_steps` is 300 000 (up from 160 000) because the 300 V CFL step
is ~4.14 ps and 1 µs needs ~242 k steps — the old cap would have silently
truncated the run to 660 ns. `helpers.validate()` refuses a config where the cap
truncates `t_end`.

| | dt | steps | grid | λ_D | dx/λ_D | r_p/λ_D | rmax/λ_D | CFL | ω_pe·dt | t_end/τ |
|---|---|---|---|---|---|---|---|---|---|---|
| A_day_p95 | 4.135 ps | 241 800 | 200×440 | 1.85 mm | 0.081 | 2.71 | 16.3 | 0.30 | 3e-4 | 44.1 |
| B_night_worst | 4.137 ps | 241 680 | 200×440 | 6.03 mm | 0.025 | 0.83 | 4.98 | 0.30 | 1e-4 | 4.1 |

**`rmax/λ_D = 5.0` for B is the known risk.** The thin night plasma has a
6 mm Debye length, so the 30 mm domain holds only five of them and the sheath
may reach the grounded boundary — which would clip the plume and fake an escape.
This is what the `S__edge_phi_max_V ≤ 1 V` gate is for, and the **smoke runs
check it before the real runs commit**: see below.

Both scenarios stay inside OML's validity window (`r_p/λ_D` = 0.83 and 2.71).
The archived femtosat record found the OML-style form failing badly at
`r/λ_D ≈ 9`, which is why that ratio is reported here rather than assumed.

## Running it

```bash
conda activate warpx-cpu-mpich-dev

# smoke first (~1.5 h each): plumbing, early phi trajectory, and the domain decision
python simulation.py --scenario A_day_p95     --t-end 150e-9
python simulation.py --scenario B_night_worst --t-end 150e-9

# the real runs, ~10 h each -- ONE WarpX case at a time on this machine
python simulation.py --scenario A_day_p95
python simulation.py --scenario B_night_worst

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

### The domain decision point

The smoke runs exist to answer one question before ~20 hours are spent: **does
B's sheath stay inside the box?** If its edge |φ| trends toward the 1 V gate,
`domain.rmax` goes 30 → 40 mm for the *whole stage* (grid 200×440 → 272×440,
cost ×1.36) before either real run starts, and this README records that it
happened. Changing it afterwards would mean the two scenarios were not the same
discretized machine.

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
