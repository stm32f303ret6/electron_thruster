# The 2026-08 simulation campaign — hypotheses, results, changes, implications

A complete record of the PIC campaign that took this project from *one
validated operating point* to *a measured frontier with a calibrated model*.
Everything here is traceable to committed evidence: each number cites a run in
`reference_results/`, and each prediction was written to git **before** the run
that tested it.

- **Reproducing the environment and runs:** `SETUP.md`
- **The physics reasoning and scaling laws:** `SCALING_LAWS.md`
- **The executable model and its calibration:** `model/MODEL.md`
- **The ladder architecture and contract:** `pic_sims/validation_cases/README.md`
- **The paper this feeds:** `paper/main.tex`

---

## 1. Where the campaign started

Before 2026-08-03 the project had **one** gated capstone run: the 200 V
"float200" anchor — a Ø10 × 5.9 mm conducting can floating in a dayside
ionospheric plasma, emitting 0.342 mA through a lid aperture and collecting
the return current on its own skin.

That single point supported one honest sentence: *in one prescribed-current PIC
case, escaping-electron momentum is about 13.65 nN.* It did not support any
claim about how the device scales, whether it could meet a mission's drag
demand, or what would happen at another voltage, density, or size.

The campaign's purpose was to convert that point into a **frontier** — enough
measured structure to build a predictive model, with the model's failure modes
mapped rather than hidden.

---

## 2. What was measured

Four gated production runs, all seed 42, all on the committed deck, each
promoted to `reference_results/` with its frozen config, manifest, metrics,
verdict, and the exact acceptance policy applied.

### 2.1 The voltage frontier (three points, one plasma row)

| stage | drive | steps | escape % | φ_body (V) | F_beam (nN) | exhaust KE (eV) | late dφ/dt |
|---|---|---|---|---|---|---|---|
| `capstone.low_power` | 100 V | 115,480 | 96.12 | 5.40 | 3.42 | 77.19 | +4.04 mV/ns |
| `capstone.floating_body` | 200 V | 159,160 | 98.44 | 16.98 | 13.65 | 147.52 | +16.46 mV/ns |
| `capstone.high_thrust` | 300 V | 192,680 | 98.99 | 36.30 | 30.13 | 210.11 | +26.83 mV/ns |

Trust gates on every run: current balance 0.015–0.035 (bound 0.05), momentum
ratio 0.004–0.088 (bound 1.0), edge potential 0.006–0.108 V (bound 1.0), and
the two ledger-vs-dump cross-checks at 1e-9 or better (bound 0.02).

### 2.2 The geometry axis (one point)

| stage | body | steps | escape % | φ_body (V) | F_beam (nN) | exhaust KE (eV) | late dφ/dt |
|---|---|---|---|---|---|---|---|
| slender variant | Ø10 × 30.5 mm (L/r = 6) | 159,160 | 98.42 | 4.38 | 14.22 | 159.73 | +4.36 mV/ns |

Same drive, same commanded current, same plasma row, same grid, same seed as
the 200 V anchor. Only the body shape changed.

### 2.3 Numerical convergence (two runs, 200 V anchor)

| axis | change | effect |
|---|---|---|
| particle count | ppc 16 → 32 | ≤ 0.05 % on every gated metric — **closed axis** |
| grid | dx 0.15 → 0.10 mm | F +4.0 %, KE +7.4 %, φ −1.8 % — **leading numerical uncertainty** |

The grid deltas are *conservative in sign* for every gate (finer grid gives
more thrust and more energy, less float), so the committed numbers are not
flattered by resolution. The dx run hit its `max_steps` cap at 536 ns rather
than 800 ns, so the comparison was made over a matched 430–536 ns physical
window on both runs; the truncation is disclosed in the paper's methods.

---

## 3. The hypotheses, and how they resolved

The campaign's discipline was to **write predictions to git before the run that
tests them**. Three pre-registrations were made. All three resolved.

### 3.1 The collection law (pre-registered 2026-08-04, before the 300 V run)

Three candidate exponents in `I_collect ∝ (1+χ)^α` existed in the project
lineage. They agree near the anchor (χ ≈ 150) and diverge at 300 V:

| α | source | predicted φ at 300 V | outcome |
|---|---|---|---|
| 1 (linear OML) | this repo's single-point anchor inversion | ~31 V | **REFUTED** — φ passed 31 V near 650 ns and kept climbing |
| **0.82** | `electron_contactor` U-curve campaign, fitted across six equilibria | **~36 V** | **SURVIVES** — measured 36.30 V |
| 0.5 (square root) | `electron_gun_probe` converged reservoir run | ~90 V | **REFUTED** — nothing in the trajectory heads there |

The 100 V run measured 5.40 V against a ~6 V prediction — consistent, but at
low χ the candidate laws converge, so it *confirms the anchor* rather than
discriminating. **The 300 V point carries the discrimination.**

*Caveat carried, as pre-registered:* φ was still rising at run end
(+26.8 mV/ns, decaying from +44.5), so the settled float extrapolates to
~42–48 V. That pushes the true α slightly below 0.82 and its top edge brushes
the 50 V benign gate. The winner is α ≈ 0.82, quoted as a band.

### 3.2 The slender body (pre-registered 2026-08-05, before the run)

Growing total skin 3.24× (3.4 → 11.0 cm²) at fixed escaped current:

| hypothesis | mechanism | predicted φ | outcome |
|---|---|---|---|
| **A — area-only scaling** | the can's fitted α holds; enhancement demand drops 3.24× | **4–5 V** | **CONFIRMED** — measured 4.38 V |
| B — cylinder-limit lateral | lateral wall slides toward OML cylinder α ≈ 0.5 | tens of V, possibly past the 50 V gate | **REFUTED by ~10×** |

The area arithmetic brackets the measurement: 4.66 V at α = 0.893 (tail fit),
4.14 V at α = 0.82 (settled fit), measured 4.38 V. **The fitted exponent
survives a 3.24× area change and an aspect-ratio change from L/r = 0.6 to 6.**

### 3.3 The thin-plasma density axis (pre-registered 2026-08-06, never run)

Predictions were recorded — α = 1 → 53.4 V, 0.893 → 60.9 V, 0.82 → 68.0 V,
0.5 → 160.4 V — and the run was then **unchained before launch by scope
decision**, with the reasoning recorded in the plan's amendment: the law's
density dependence is `I ∝ n·(1+χ)^α`, whose `n`-linear term is *already*
validated to ±1 % at rung `collector.thermal`, and whose α is *already*
discriminated on the voltage axis. The run tests one residual assumption (that
α and β do not drift as `r_probe/λ_D` goes 2.5 → 1.5), and the settle limit
would blur a 53–68 V discrimination anyway. It is a **gross-breakdown
detector, not a measurement.**

The pre-registration remains committed and unexecuted — a ready, un-p-hacked
run if a reviewer challenges the density extrapolation.

---

## 4. Changes made to the code and the contract

### 4.1 `geometry.cathode_standoff` — the one code change (commit `a7f4106`)

**Why it was needed.** The first slender attempt set `z_bot: -30 mm` and
inherited everything else. But the deck ties the cathode disk to the can floor,
so lengthening the can stretched the **gun gap** from 4.7 mm to 29.7 mm.
Child–Langmuir scales as `I_CL ∝ 1/d²`, which put the commanded 0.342 mA at
~60× the long gap's space-charge ceiling. The beam blew open and self-scraped:
91.1 % hit the body, 7.9 % escaped, φ ≈ 0.3 V and flat. **The hypotheses were
never tested.** The run was killed at 69 % by operator decision.

**The fix.** An optional geometry key — the cathode-top-to-lid-bottom distance,
which *is* the gun gap. When set, the floor assembly rides an internal pedestal
and a BODY cap seals the can bottom, so the outer skin stays a full cylinder
and the emitter sees the anchor's ceiling unchanged.

**Baseline preservation, verified not asserted.** Against the pre-change code,
every committed config produces byte-identical EB implicit functions, potential
strings, scraped-region masks, and frozen config dicts — so every existing
`case_sha256` stays valid. Four new tests; 38 pass in the stage, 278 across the
ladder.

The corrected run's demand-to-ceiling ratio is **1.457**, matching the anchor's
measured 1.46 — proof the gun is identically driven.

### 4.2 `capstone.exploratory_axes.v1` — a second acceptance policy (commit `9314327`)

The default policy gates φ to 16 ± 4 V and F_beam to 13.6 ± 2.04 nN. Those are
float200 **regression anchors**: correct for re-running the baseline, wrong for
a stage where **φ is the measurement**. Gating φ to the baseline would gate the
answer.

The new policy keeps as *required* exactly the gates that certify a measurement
is trustworthy — escape, current balance, momentum bound, sheath containment,
both ledger cross-checks — with tolerances verified identical field-by-field to
the original. The two baseline anchors become *reported, non-required* gates so
the comparison still appears in every verdict without deciding it.

It was committed while the slender run was at ~2 %, so it provably predates the
verdict it governs.

### 4.3 Documentation and infrastructure

- `SETUP.md` + `env/*.yml` — environments, the WarpX version and full build
  flag rationale, how to run the ladder and variant runs, GPU arena sizing, and
  the evidence rules. Every command verified, including the discovery that
  `pytest pic_sims/validation_cases` does **not** work (stage self-containment
  collides on test module basenames) — the per-stage loop does.
- `model/minimal_model.py` + `model/MODEL.md` — the executable model, calibrated
  from committed `reference_results` only.
- Plan documents with amendments rather than rewrites: `SLENDER_BODY_PLAN.md`
  records the killed run and *why* it was invalid; `THIN_PLASMA_PLAN.md`
  records why its run was cut.

---

## 5. The model the campaign made possible

Three voltage points plus a geometry point are enough to calibrate a minimal
predictive model (`model/minimal_model.py`), fitted **only** to committed
reference results:

```
collection   I = βA · j_the(n,Te) · (1+χ)^α ,  χ = eφ/kTe
thrust       F[nN] = c_F · I[mA] · √KE[eV] ,   KE = κ·(V − φ)
emission     I_CL ∝ V^1.5 / d²   (measured non-planar ratio 1.46)
```

Calibration: `c_F = 3.2675`, `κ = 0.8063`, `α = 0.8931` (tail) / `0.8451`
(settled), `βA = 2.507 cm²`. Float residuals across the three anchors:
−0.09 / +0.72 / −0.89 V.

**The flight rule.** Minimising input power at fixed thrust demand gives a
U-shaped valley in V, whose floor sits at `V = ctrl_factor · φ` with
`ctrl_factor = (2α+1)/α ≈ 3.12`. That is a **two-line servo on a quantity the
spacecraft can actually measure** — the float — with no need to sense plasma
density or temperature directly. φ is the sensor.

**Mission sweep**, all five committed orbit CSVs, with every row flagged as
measured or extrapolated:

| mission | drag mean/max (nN) | feasible % | duty cycle | P mean (mW) |
|---|---|---|---|---|
| 400 km axial | 32.9 / 92.4 | 21.0 | 140 % | 135.6 |
| 400 km lateral | 21.6 / 60.7 | 53.8 | 92 % | 110.9 |
| 500 km | 7.6 / 28.4 | 80.7 | 45 % | 39.4 |
| 550 km | 3.8 / 16.3 | 91.5 | 32 % | 16.9 |
| 600 km | 2.0 / 9.6 | 97.0 | 25 % | 8.0 |

The model's independent 400 km power figure (136 mW) reproduces the earlier
hand estimate (~110–165 mW), which is a weak but real cross-check.

---

## 6. What it implies

### 6.1 The device is a closed circuit, and the books balance

The most important result is not a thrust number — it is that **the charge and
momentum bookkeeping closes**. Current balance to 2–4 %, momentum bound at
0.4–8.8 % of the beam, and the per-step ledger agreeing with independent
openPMD dumps to 1e-9. That last check is what rules out the quiet failure mode
where the accounting is self-consistent but wrong.

This also answers the reviewer objection recorded in `THESIS.md` — that ambient
electron momentum might cancel the gun's. Measured: **F_net/F_beam = 0.4–1.4 %**
on the frontier runs. The return current arrives isotropically and its net axial
momentum is a percent-level correction, not a cancellation. (The direct
demonstration — a full-return null fixture measuring ~0 thrust — remains the
highest-value unbuilt test.)

### 6.2 Efficiency is the wrong axis; the empty corner is the right one

Two efficiencies must be quoted side by side, and only one is flattering:

- **Energy conversion η ≈ 0.68–0.73** — most of the supplied beam energy leaves
  as directed exhaust. Respectable.
- **Impulse economy F/P ∝ 1/√V** — measured 0.283 / 0.200 / 0.159 µN/W at
  100 / 200 / 300 V. This is **~200× below a gridded ion engine**, and it gets
  *worse* with voltage.

So this will never be an efficient thruster, and the paper should say so
plainly. The honest claim is different: **at gram scale there is no incumbent.**
Cold gas, PPT, electrospray and FEEP all carry a dry-system floor — tank, valve,
plumbing, PPU — that a gram-class craft cannot. This device's propellant is the
ionosphere, so its dry floor is a gun and a wire. The thrust–power plane has an
empty corner below ~10 nN, and that is the niche.

### 6.3 The mission corridor is real and narrow

- **550–600 km:** closes on harvested power. 25–32 % duty cycle, 8–17 mW.
- **500 km:** closes on impulse but is power-bound (39 mW mean, 45 % duty).
- **400 km:** does not close — 140 % duty cycle is a contradiction.

This is a feasibility corridor, not a solved station-keeping problem, and it
depends on assumptions (solar harvest, attitude, duty cycling) that only a full
mission analysis can settle.

### 6.4 Elongation is the up-mass path, and it is free

Drag charges for the **ram silhouette**; collection and solar harvest buy the
**total skin**. A slender body flying end-on decouples them, and the campaign
measured that the decoupling is not paid for elsewhere:

| | squat can | slender can |
|---|---|---|
| skin | 3.17 cm² | 11.0 cm² (3.24×) |
| ram silhouette | Ø10 mm cap | **unchanged** |
| φ_body | 16.98 V | **4.38 V** (3.9× lower) |
| exhaust KE | 147.5 eV | **159.7 eV** |
| F_beam | 13.65 nN | **14.22 nN** |

Because `KE = κ(V − φ)`, a body that floats lower keeps more of its drive. The
slender can makes **more** thrust at the same commanded current and the same
drag bill. The concept scales *along the rod*, not into the cube.

### 6.5 A hardware design rule, bought by a failed run

The killed slender attempt produced something a successful run would not have:
a rule that follows from measured physics. Because `I_CL ∝ 1/d²`, **a slender
body must keep the cathode–aperture gap at its short design value and grow the
body around the gun.** An emitter at the far end of a long can starves and
scatters its own beam before the slit. That is now in the paper, in the code as
an enforced parameter, and in the plan's amendment — before anyone machines a
part wrong.

---

## 7. What remains open

Ranked by how much they threaten the conclusions.

1. **The density axis is untested.** All runs share one dayside plasma row. The
   `n`-linear term is validated at ±1 % on a lower rung and α is discriminated
   on the voltage axis, so the exposure is narrow — but "untested" is the word.
   The pre-registered run is ready.
2. **Nothing is fully settled.** Every float is still drifting at 800 ns
   (+4 to +27 mV/ns). Every φ should be quoted as a band. Settle time scales
   with ion transit, not with run length, so this is expensive to close.
3. **The reduced ion mass (400 mₑ, not O⁺)** is a ladder-wide caveat that no
   run in this campaign removes.
4. **Grid resolution** is the leading numerical uncertainty (F +4.0 %,
   KE +7.4 %), conservative in sign but carried as an error band.
5. **Aspect ratios beyond L/r = 6**, and bodies whose radius approaches λ_D,
   remain extrapolation — the OML cylinder limit must bite eventually.
6. **The null fixture** — a full-return configuration whose measured thrust must
   be ~0 — would convert the momentum answer from a computation into a
   demonstration. This is the single highest-value unbuilt test.
7. **Emitter physics, total system power, and attitude** are outside every run
   here: the beam is prescribed, not thermionically modelled, and the power
   figures are ideal beam power `I·V`.

---

## 8. Campaign ledger

| date | event |
|---|---|
| 2026-08-03 | 300 V ceiling run configured and smoke-tested |
| 2026-08-04 | collection-law hypotheses pre-registered; 300 V launched; 100 V floor stage added |
| 2026-08-05 | 300 V and 100 V gated PASS; convergence pair run; minimal model built and swept; paper drafted; slender attempt launched, found invalid, killed |
| 2026-08-06 | cathode-standoff fix committed and slender relaunched; thin-plasma pre-registered then unchained; `SETUP.md` written; slender gated PASS, hypothesis A confirmed |

Total: **~50 GPU-hours** across four production runs, two convergence runs, and
one killed run. One code change. Three pre-registrations, three resolved.
