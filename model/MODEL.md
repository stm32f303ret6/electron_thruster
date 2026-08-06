# MODEL — the minimal executable model of the electron thruster

`model/minimal_model.py` is the executable form of `SCALING_LAWS.md` §9: one
file that turns the **measured three-point voltage frontier** into mission
predictions, with every constant derived from committed `metrics.json` files
(residuals printed, never hidden) and every out-of-envelope row flagged.

It answers, per orbit-CSV row `(n_e, Te, drag)`:
**what V and I does the controller choose, what does the body float to, what
does the thrust cost in watts, and is that prediction measured or
extrapolated?**

The §9 contract, restated: this model **never feeds an acceptance gate**. PIC
stages stay self-contained; fitted constants stay home; physics forms travel.

---

## 1. The laws and their measured constants

Calibration inputs — the three committed, all-gates-PASS frontier runs
(single dayside plasma row n₀ = 1.627·10¹² m⁻³, Te = 1318.8 K):

| V | I (mA) | φ (V) | F (nN) | escape | KE (eV) | provenance (run / analysis) |
|---|---|---|---|---|---|---|
| 100 | 0.121 | 5.40 | 3.42 | 96.12 % | 77.2 | `capstone.low_power` `20260804T230218Z_0adb478f` / `20260805T045648Z_ff61c01a` |
| 200 | 0.342 | 16.98 | 13.65 | 98.44 % | 147.5 | `capstone.floating_body` `20260801T142601Z_2f822a95` (committed reference) |
| 300 | 0.630 | 36.30 | 30.13 | 98.99 % | 210.1 | `capstone.high_thrust` `20260804T154756Z_b854dcbe` / `20260805T002119Z_d81b7f96` |

**Thrust law** (`SCALING_LAWS` §1) — plasma-independent gun physics:

```
F [nN] = c_F · I [mA] · √KE [eV]        c_F = 3.2675  (per-anchor 3.216–3.300; ideal 3.372)
KE     = κ_KE · (V − φ)                 κ_KE = 0.8063 (per-anchor 0.797–0.816)
```

Both constants hold to ~1 % across the full 3× voltage range — the beam side
is solved physics.

**Emission ceiling** (§3) — analytic scale × measured ratio:

```
I_CL [mA] = 8.298·10⁻⁵ · V^1.5     (planar Child–Langmuir, r=0.5 mm spot, d=4.7 mm gap)
I_max     = 1.46 · I_CL            (non-planar ratio, measured at 200 V, held by all stages)
```

Reproduces the quoted 0.083 / 0.235 / 0.431 mA at 100/200/300 V exactly.

**Collection law / floating potential** (§4) — the plasma-dependent return
circuit:

```
I_esc = β·A · j_the(n, Te) · (1 + χ)^α        χ = eφ/kTe
j_the = e·n·√(kTe / 2π mₑ)
```

Fit over the three anchors (log-space least squares):

| φ input | α | β·A | φ residuals at 100/200/300 V |
|---|---|---|---|
| tail-averaged (policy) — **default** | **0.8931** | 2.51 cm² (β ≈ 0.76) | −0.09 / +0.72 / −0.89 V |
| settled-extrapolated (late-slope) | 0.8451 | 2.83 cm² (β ≈ 0.86) | −0.26 / +1.96 / −2.44 V |

The fitted α band **0.845–0.893** sits at the upper edge of the
pre-registered winner α = 0.82 ± 0.06 (the discrete-hypothesis verdict in
`SCALING_LAWS` §4: linear and √ refuted, 0.82 the surviving form). The two
fits bracket the tail-vs-equilibrium uncertainty of the 300 V float; closing
the band needs the longer-tail 300 V run (not scheduled).

---

## 2. The control law (flight rule, §7b) — documented for the paper

The controller the model applies per row is the two-line servo on the
spacecraft's own measured float — **no ionosphere model, no lookup table**:

```
1.  V = ((2α+1)/α) · φ            servo V to the measured float  (= 3.12·φ at fitted α)
2.  I = F_required / (c_F·√(κ_KE·(V − φ)))       current from the thrust demand
    guards:  I ≤ 1.46·I_CL(V)    (emission ceiling)
             φ ≤ 50 V            (benign-float design limit)
    infeasible → duty-cycle at the valley; never push V below it
```

Why it works: φ is the sensor — density, temperature, day/night, and the
vehicle's own draw all collapse into where the body floats, which the body
measures by existing. The 3.12 factor is physics
(`V_opt = ((2α+1)/α)·φ_eq`, the U-valley marginal-cost balance), not tuning,
and the valley is shallow (measured flat over ~110–160 V dayside), so factor
errors cost percent-level power. Hardware clamps V to [100, 300] V; where the
servo target sits below the emission-feasibility floor, the model lifts V to
the lowest feasible value — "the optimum is the boundary."

In the model the rule is solved self-consistently per row (damped fixed
point over φ → V → I → φ), which is what the real servo does in time.

## 3. Capability, duty cycle, closure — definitions

- **Feasible row**: a benign equilibrium exists at the demanded thrust
  (I ≤ ceiling and φ ≤ 50 V).
- **Capability F_cap(n, Te)**: max benign thrust at V = 300 V with
  I = min(emission ceiling, collection limit at φ = 50 V) — what the device
  could do duty-cycled at full throttle.
- **Duty cycle needed** = mean(drag)/mean(F_cap): ≤ 100 % means the
  impulse budget closes by duty-cycling; > 100 % means the altitude is
  simply beyond the device.
- Reported φ above the 100 V choke ceiling is **not a physical prediction**
  (PIC aborts there — the ionosphere cannot neutralize); it appears only in
  flag accounting as "no benign equilibrium exists on this row."

## 4. Envelope flags — what "measured" means per row

| flag | condition | meaning for the paper |
|---|---|---|
| `in_envelope` | none of the below | prediction interpolates measured runs |
| `extrap_density` | n·√Te outside 0.7–1.3× the anchor row | the collection law's **theory-only axis** (§8): no committed run has measured another density |
| `extrap_chi` | solved χ outside the measured 47–319 | the (1+χ)^α form extrapolated beyond its fitted range |
| `phi_over_benign` | φ > 50 V | design limit exceeded — duty-off region |
| `infeasible_emission` | demand needs I > 1.46·I_CL(300 V) | beyond the hardware's thrust ceiling |

Mission claims must be split into the measured-envelope bucket and the
flagged bucket; the flagged bucket says exactly where the next GPU-hours go.

---

## 5. Mission sweep results (2024 orbit CSVs, real F10.7/Ap, 1 yr @ 5 min)

Generated by `python model/minimal_model.py --all`; machine-readable copies
in `model/results/` (`MISSION_SUMMARY.md`, `mission_summary.json`, one
per-row CSV per mission).

| mission | drag mean/max (nN) | feasible % | duty cycle needed | P mean/max (mW) | φ > 50 V % | in-envelope % |
|---|---|---|---|---|---|---|
| 400 km axial | 32.9 / 92.4 | 21.0 | **140 %** — does not close | 135.6 / 188.9 | 40.9 | 11.9 |
| 400 km lateral | 21.7 / 60.7 | 53.8 | 92 % — marginal, no margin | 110.9 / 188.9 | 31.0 | 33.4 |
| 500 km axial | 7.6 / 28.4 | 80.7 | 45 % | 39.4 / 182.2 | 19.3 | 29.1 |
| 550 km axial | 3.8 / 16.3 | 91.5 | 32 % | 16.9 / 94.9 | 8.5 | 8.0 |
| 600 km axial | 2.0 / 9.6 | 97.0 | 25 % | 8.0 / 51.7 | 3.0 | 0.9 |

**Readings:**

- **The feasibility corridor is 500–600 km**, exactly the THESIS altitude
  honesty: at 400 km the demand exceeds the emission ceiling 63 % of the
  time and the impulse budget cannot close even duty-cycled (140 %). The
  model's 400 km mean power (136 mW) independently reproduces the THESIS
  power-side figure (~110–165 mW) from different inputs.
- **At 550–600 km the concept closes on harvested power**: mean demand-side
  power 8–17 mW against the ~30 mW body-mounted harvest estimate, with
  duty cycles of 25–32 % and >91 % instantaneous feasibility.
- **500 km is the frontier altitude**: closes on impulse (45 % duty) but the
  mean power at demand (39 mW) sits above the harvest estimate — closure
  there relies on thrusting preferentially when the plasma is dense and the
  charging tax low (the servo does this for free).
- **The night corner is real and now quantified**: φ exceeds the 50 V benign
  limit on 19 % of 500 km rows and 8.5 % at 550 km — always the thin, cold
  night plasma (the 1/(n√Te) stiffness of §8). These rows are also nearly
  all density-extrapolated.

## 6. What this run decides about the ladder

The night-density PIC run (`SCALING_LAWS` §8's "missing measurement") is now
**data-motivated, not optional**: the model says the benign-float boundary is
governed by exactly the plasma rows no committed run has measured (70–99 %
of rows at 500–600 km are density-extrapolated, and the duty-off fraction is
set there). One run at a night-row density (~2·10¹¹ m⁻³, fixed V) either
validates the (1+χ)^α form on the density axis — collapsing most of the
flagged bucket into the measured one — or moves the corridor. It is the
highest-value GPU-hour in the campaign.

## 7. Caveats that travel with every number

Ladder-wide (inherited from the PIC evidence): reduced ion mass (400 mₑ),
electrostatic (no B, no ram drift), single grid/PPC/seed (convergence pass
in progress), finite-time equilibrium on the ion clock (tail-vs-settled α
band above). Model-specific: escape interpolated in V at the measured
perveance path (1.46·I_CL) only; the density axis of the collection law is
theory-only until the night-row run; supply power is beam power I·V —
emitter heating and converter losses are system engineering, not modeled.

**Size/geometry axis:** the fitted (α, β·A) pair is valid for the committed
squat can ONLY. The enhancement exponent is geometry-dependent by theory
(OML: sphere α = 1, long cylinder α = 0.5; the can's 0.82–0.89 sits between
the limits), so do not apply the fitted law to slender or larger bodies.
For any other geometry the theory-safe floor is bare thermal collection
(α = 0: `I = A_skin · j_the`, validated ±1 % on the ladder), which scales
linearly with skin area — a 1U CubeSat thermal-collects ~0.9 mA at φ ≈ 0,
more than the chipsat's entire 300 V demand. The geometry-split law and its
calibrating run are pre-registered in
`pic_sims/validation_cases/capstone/SLENDER_BODY_PLAN.md`.

## 8. Usage

```bash
python model/minimal_model.py --calibrate            # constants + residuals
python model/minimal_model.py --all                  # sweep every mission CSV
python model/minimal_model.py --mission path.csv     # one mission
python model/minimal_model.py --all --alpha-settled  # sensitivity variant
```

Requires only numpy. Outputs to `model/results/` by default (`--out DIR`).
