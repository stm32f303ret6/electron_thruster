# The 2026-08 simulation campaign — hypotheses, results, changes, implications

A complete record of the PIC campaign that took this project from *one
validated operating point* to *a measured frontier with a calibrated model*.
Everything here is traceable to committed evidence: each number cites a run in
`reference_results/`, and each prediction was written to git **before** the run
that tested it.

- **Reproducing the environment and runs:** `SETUP.md`
- **The physics reasoning and scaling laws:** `SCALING_LAWS.md`
- **The executable model and its calibration:** `model/MODEL.md`
- **The ladder architecture and contract:** `pic_sims/ladder/README.md`
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

Three candidate exponents in `I_collect ∝ (1+χ)^α` were on the table. They
agree near the anchor (χ ≈ 150) and diverge at 300 V:

| α | source | predicted φ at 300 V | outcome |
|---|---|---|---|
| 1 (linear OML) | this repo's single-point anchor inversion | ~31 V | **REFUTED** — φ passed 31 V near 650 ns and kept climbing |
| **0.82** | intermediate candidate between the OML sphere (α = 1) and cylinder (α = 0.5) limits, pre-registered with a ±0.06 band | **~36 V** | **SURVIVES** — measured 36.30 V |
| 0.5 (square root) | OML-cylinder / thin-sheath square-root theory | ~90 V | **REFUTED** — nothing in the trajectory heads there |

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

### 3.3 The thin-plasma density axis (pre-registered 2026-08-06; later executed — see §10)

Predictions were recorded — α = 1 → 53.4 V, 0.893 → 60.9 V, 0.82 → 68.0 V,
0.5 → 160.4 V — and the run was then **unchained before launch by scope
decision**, with the reasoning recorded in the plan's amendment: the law's
density dependence is `I ∝ n·(1+χ)^α`, whose `n`-linear term is *already*
validated to ±1 % at step `collector.thermal`, and whose α is *already*
discriminated on the voltage axis. The run tests one residual assumption (that
α and β do not drift as `r_probe/λ_D` goes 2.5 → 1.5), and the settle limit
would blur a 53–68 V discrimination anyway. It is a **gross-breakdown
detector, not a measurement.**

The pre-registration remains committed and unexecuted — a ready, un-p-hacked
run if a reviewer challenges the density extrapolation.

*Resolution (2026-08-08 → 08-12, after this section was written):* the run
was relaunched as exactly the gross-breakdown detector described above,
found healthy but unsettled at 800 ns, then continued to 2.4 µs under a
pre-registered continuation — producing the campaign's **first settled
float** and an unexpected verdict: every fixed-α prediction overshoots, and
the law is *conservative* along density. Full account in §10.

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
  `pytest pic_sims/ladder` does **not** work (stage self-containment
  collides on test module basenames) — the per-stage loop does.
- `model/minimal_model.py` + `model/MODEL.md` — the executable model, calibrated
  from committed `reference_results` only.
- Plan documents with amendments rather than rewrites: the slender-body plan
  (`pic_sims/thruster_characterization/slender_body/README.md`, plan and
  first-attempt sections; the pre-run `SLENDER_BODY_PLAN.md` is in git history)
  records the killed run and *why* it was invalid;
  `pic_sims/thruster_characterization/thin_plasma/THIN_PLASMA_PLAN.md`
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

**The throttle principle.** The concept argument now carries only the
analytical lower bound `P = F·√V / 2.93`, validated to 4–6 % against the
frontier anchors: largest feasible escaped current, lowest sufficient
voltage. The earlier flight-rule/servo formulation and its U-shaped
fixed-thrust cost surface were demoted to controller-optimization work —
see the scope decision in `future_work/README.md`.

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

### 6.5 The result is not about a Ø10 mm can

The campaign measured small bodies, but the geometry result licenses a scaling
argument in which **size cancels entirely**. Drag charges for the ram
silhouette, so thrust demand, current and power are all proportional to
`A_ram`; harvest is paid from the skin, so supply is proportional to
`A_skin`. Divide, and the closure margin depends only on the **shape ratio**
`A_skin/A_ram` and the altitude. Mass never enters: holding altitude needs
thrust = drag whatever the craft weighs.

Computed from committed data (`model/scale_analysis.py` →
`model/results/SCALE_ANALYSIS.md`), a slender Ø10 mm can and a 3U CubeSat in
end-on flight return **identical** margins — 1.4× / 2.8× / 5.4× at
500 / 550 / 600 km — because they share `A_skin/A_ram = 14`. A 3U needs
**8.8 mA at 0.88 W to hold 600 km**, 17 mA / 1.7 W at 550 km, 34 mA / 3.4 W at
500 km. The 400 km wall is scale-free too, and closes for nothing.

Larger bodies also need **less** extrapolation. The chipsat frontier runs at
χ ≈ 150–320, deep in the fitted enhancement regime; a 3U needs only ~4× the
bare thermal flux, which is the step validated to ±1 %. The unmeasured piece
is a *regime* change, not a size problem: CubeSat radii are 25–60 λ_D against
our 2.5, where collection proceeds through a thin φ-growing sheath rather than
an orbital-motion fan. A Child-sheath estimate puts a 3U float at ~12 V at
600 km and ~47 V at 500 km — benign in the corridor. That estimate is the
campaign's largest un-gated claim and the top candidate for the next run.

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
   `n`-linear term is validated at ±1 % on a lower step and α is discriminated
   on the voltage axis, so the exposure is narrow — but "untested" is the word.
   The pre-registered run is ready.
   *Update 2026-08-12: measured (§10). One 3× step, settled at 2.4 µs:
   φ = 42.5 V against 53–68 V predicted — the fitted law is conservative
   along density. What remains extrapolated is the regime beyond n0/3
   toward the ~1e11 m⁻³ night minimum, now with a measured directional
   bias.*
2. **Nothing is fully settled.** Every float is still drifting at 800 ns
   (+4 to +27 mV/ns). Every φ should be quoted as a band. Settle time scales
   with ion transit, not with run length, so this is expensive to close.
   *Update 2026-08-12: the thin-plasma continuation is the first settled
   float (2.4 µs, late slope −0.14 V/µs). The anchor-row floats remain
   800 ns reads with disclosed slopes.*
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
| 2026-08-07 | fixed-thrust throttle stages + gun voltage bracket pre-registered and committed (`UCURVE_PLAN.md`); gun cohort + biased_3v v2 re-gate run |
| 2026-08-08 | all three throttle runs gated PASS; H2 (perveance tax) wins the discrimination; valley measured at ~125 V; no-go wall at 78 V demonstrated; two-slice α fit committed |
| 2026-08-08 | thin-plasma n0/3 relaunched as the gross-breakdown detector; magnetized M1 axis pre-registered (`plasma.Bz_T`) |
| 2026-08-09 | thin-plasma 800 ns gated PASS — healthy, unsettled (φ_settled > 31.6 V); throttle/U-curve work rescoped to `future_work/` |
| 2026-08-10 | M1 pair gated PASS, run sequentially on one GPU: 1× LEO null (anchor unchanged), 10× collection tax (φ +33 V lower bound, F −11 %) |
| 2026-08-11 | thin-plasma 2.4 µs continuation pre-registered, then launched |
| 2026-08-12 | continuation gated PASS — the campaign's first settled float: 42.5 V, below every fixed-α prediction; the law is conservative along density |

Total: **~50 GPU-hours** across four production runs, two convergence runs, and
one killed run. One code change. Three pre-registrations, three resolved.
The follow-on campaigns add ~14 GPU-hours (throttle, §9) and ~44 GPU-hours
(characterization spokes, §10); with them, every pre-registration made in
this repository has been resolved or explicitly rescoped.

---

## 9. The fixed-thrust throttle campaign (2026-08-07/08)

The frontier of §2 holds perveance fixed and measures the envelope boundary;
this follow-on campaign holds the **demand** fixed (the anchor's 13.65 nN)
and measures the cost surface inside it. Pre-registered in
`UCURVE_PLAN.md` (hypotheses H1/H2 and numeric predictions committed before
any run), resolved in its 2026-08-08 amendment. Three capstone stages, each
gated PASS on the trust set. *(Scope note 2026-08-09: these stages, their
plan, and the controller work built on them were moved to `future_work/` —
geometry-specific optimization evidence, no longer part of the concept
argument.)*

| stage | V | escape | delivered F | P/F at delivered F |
|---|---|---|---|---|
| `capstone.ucurve_floor` | 78 V | 57.4 % | 10.38 nN (−24 %) | 6.31 mW/nN |
| `capstone.ucurve_left_arm` | 92.4 V | 79.9 % | 11.59 nN (−15 %) | 4.79 mW/nN |
| `capstone.ucurve_valley` | 125 V | 93.8 % | 13.09 nN (−4 %) | **4.43 mW/nN** |
| (`capstone.floating_body`) | 200 V | 98.4 % | 13.65 nN | 5.01 mW/nN |

Resolutions:

- **The perveance tax is real (H2).** The pre-registered discriminator —
  the sign of P/F(92.4) − P/F(125) — came out positive: the specific-power
  valley sits at ~125 V, refuting the calibrated laws' untaxed valley
  (~95 V). The flight servo's closed form is demoted to a lower bound
  (`model/MODEL.md` §2).
- **The no-go wall is measured, with a shape neither branch predicted:** at
  78 V a steady equilibrium forms but cannot meet the demand (−24 % at 10×
  the validated emission ceiling, F_net/F_beam = 0.89).
- **The tax is a can phenomenon.** The new `emitter.voltage_bracket` step
  ran the same 92.4 V command in the isolated-gun geometry: 0.9999
  transmission. Beam formation is clean at every capstone drive voltage
  (closing gap G3); the collapse happens inside the can.
- **The collection law survives a slice change.** All six committed
  equilibria — two slices, escape 57–99 % — fit `(1+χ)^α` with
  α_all = 0.922, residuals ≤ 9.3 %.

Cost: **~13.3 GPU-hours** for the three capstone runs, ~1 h for the gun
cohort and the collector re-gate. Two acceptance-policy refutations were
recorded and re-gated on the way (`emitter.voltage_bracket.v1`'s
current-limiting expectation; `collector.biased_3v.v1`'s rationale) — both
per the ladder's policy-versioning contract.

---

## 10. The characterization spokes: density and magnetization (2026-08-08 → 08-12)

Two axes the frontier left open — ambient density and the geomagnetic
field — were measured as spokes off the 200 V anchor
(`pic_sims/thruster_characterization/`), each pre-registered before its
run, each gated PASS on the trust set under
`capstone.exploratory_axes.v1`.

### 10.1 The density axis, closed by a continuation

The §3.3 pre-registration was relaunched 2026-08-08 as a gross-breakdown
detector: same deck at **n0/3** (5.42e11 m⁻³), rmax 30 → 40.8 mm for the
√3× larger λ_D. The 800 ns reference run passed all six required gates —
device healthy, no breakdown — but the float was still climbing, so the α
discrimination failed with only a hard bound, φ_settled > 31.6 V.

A **2.4 µs continuation** (3× the anchor's duration; `t_end`, `max_steps`,
and `phi_ceiling` 100 → 180 V pre-registered in the plan's §CONTINUATION
before launch) closed it:

| run | steps | escape % | φ_body (V) | F_beam (nN) | exhaust KE (eV) | late slope |
|---|---|---|---|---|---|---|
| 800 ns reference `41b114e2` | 159,160 | 98.39 | 29.47 (unsettled) | 13.04 | 135.1 | climbing |
| 2.4 µs continuation `acc8f8f9` | 477,480 | 99.13 | **42.5 — SETTLED** | 12.39 | 122.0 | −0.14 V/µs |

The campaign's **first settled float**, and the scorecard surprised on
both ends:

- **α = 0.5 refuted a second time**, now on the density axis, independent
  of the voltage-axis refutation (§3.1): the float saturated at 42.5 V
  with the choke ceiling parked above 160 V.
- **Every fixed α ≤ 1 overshoots** (predictions 53.4 / 60.9 / 68.0 V):
  `(1+χ)` rose only 2.39× for the 3× density drop, where any fixed
  α ≤ 1 requires ≥ 3×. Read as an exponent, the secant is
  α_eff = ln 3 / ln 2.39 = **1.26**; read at the model's default α, a
  **~38 % rise in βA** — the direction sheath expansion toward OML
  predicts as r_probe/λ_D falls 2.5 → 1.5.
- **The benign-float gate passes** (42.5 < 50 V), contrary to the plan's
  expectation. n0/3 does not end the envelope at the anchor's drive: the
  fitted law **over-predicts the float cost of thin plasma**. Every
  mission row flagged `extrap_density` is now bounded by a measured,
  conservative law over a 3× band.

Caveats carried: a two-point A/B (one 3× step) across the disclosed rmax
change; α_eff is a secant, not a fit; behavior beyond n0/3 toward the
~1e11 m⁻³ night minimum remains extrapolated — now with a measured
directional bias.

### 10.2 The magnetized axis (tier M1, field-aligned)

Pre-registered 2026-08-08 (H-M1-null at flight strength, H-M1-tax as the
alternative at 10×), run strictly sequentially on one GPU 2026-08-10.
The only external B compatible with the RZ deck is axial — exactly the
field-aligned-firing flight configuration.

| stage | Bz | escape % | φ_body (V) | F_beam (nN) | exhaust KE (eV) |
|---|---|---|---|---|---|
| `magnetized_1x` | 30 µT (1× LEO) | 98.44 | +17.22 | 13.64 | 147.3 |
| `magnetized_10x` | 300 µT (10×) | 98.32 | +48.63 (climbing) | 12.06 | 115.9 |

- **1× LEO: the null holds** on every pre-registered bound (Δφ ≤ 2 V,
  ΔF/F ≤ 5 %, Δescape ≤ 1 pp — measured +1.2 V, +0.3 %, 0.06 pp). The
  committed operating point is untouched by the flight-strength field;
  field-aligned firing is established as the baseline mode.
- **10×: a collection tax, entirely through the float.** Beam formation
  is B-independent (escape Δ ≈ 0.1 pp; r_g,beam ≥ 0.10 m ≫ device
  scale), but the magnetized skin collects less: φ rises +32.6 V over
  the anchor, KE = κ(V − φ) falls 147 → 116 eV, thrust follows at −11 %.
  The two-constant thrust law reproduces both runs (13.56 / 12.03 nN
  predicted vs 13.64 / 12.06 measured) — c_F is untouched by Bz; the
  entire tax enters through the collection side. The float had not
  settled, so +33 V is a lower bound on the tax; 10× is an amplification
  instrument, not a flight condition.

What M1 does *not* close, stated up front in its plan: the far-field
transverse case — where the emitted momentum ends up once the exhaust
gyrates at r_g ≈ 1.4 m, unanswerable in an RZ domain of 30 mm. That is
tier M2, the project's largest unexamined question
(`future_work/M2_TRANSVERSE_B.md`).

Cost: **~44 GPU-hours** — thin-plasma 8.4 (reference) + ~22 (continuation),
the M1 pair 12.8. No code changes beyond the pre-registered `plasma.Bz_T`
key; every run a variant deck through the anchor stage.
