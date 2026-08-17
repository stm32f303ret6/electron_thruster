# PLAN — capstone.thin_plasma (density axis; pre-registered 2026-08-06)

**This is the "night-density" stage** of `SCALING_LAWS.md` §8 and
`model/MODEL.md` §6, named for what it actually varies. Recorded before
launch; queued behind the slender-body run.

## Why it exists

The three committed frontier runs (100/200/300 V) all sit on ONE plasma row
(`n0 = 1.627e12 m^-3`, `Te = 1318.8 K`). They scan **voltage**. The fitted
collection law

```
I = beta*A * j_the(n, Te) * (1 + chi)^alpha ,   chi = e*phi / kTe
```

therefore has its `alpha` pinned by the voltage axis only — yet every mission
row in `model/results/` uses it to extrapolate along **density**, which is the
axis the ionosphere actually swings on (day/night, solar activity, latitude).
That is why 70–99 % of high-altitude mission rows carry the
`extrap_density` flag. One run on the density axis converts the fitted law
from *interpolated in V, extrapolated in n* to *measured on both*.

## Design: a single-variable density step

Delta from `2_chipsat_thruster/config.yaml` — **only the plasma density and
the domain radius change**:

```yaml
plasma:
  n0: 5.4233e11            # exactly n0_anchor / 3
domain:
  rmax: 0.040              # containment, see below (was 0.030)
compute:
  gpu_arena_bytes: 9000000000
```

Held fixed at the 200 V anchor's values: `cathode_offset -200 V`,
`i_beam 0.342 mA`, `Te = 1318.8 K`, geometry, `dx = 0.15 mm`, `ppc 16`,
`t_end 800 ns`, seed 42 — so `max_steps` is identical (159,160) and the run
is a clean A/B against the anchor with **one** physics variable moved.

`Te` is deliberately *not* moved even though real night rows are also cooler:
`Te` enters the law twice (through `j_the ∝ √Te` and through `chi ∝ 1/Te`),
so moving it would confound the exponent test. This isolates `n`.

**Why n/3 and not the night minimum.** The mission CSVs bottom out near
`n ~ 1e11 m^-3`. At fixed 200 V the model says that row floats to ~200 V —
i.e. it *chokes*, and the flight rule's answer there is to throttle `V` up,
not to hold it. A 3× decrement is the largest step that stays inside the
device's working regime at the anchor's drive, and it lands at roughly the
35th percentile of the 500 km rows — thin, but flyable.

**Bonus: it sits on the servo's commanded point.** The two-line flight rule
commands `V = 3.12*phi`; at the predicted `phi ≈ 61–68 V` that is 190–215 V.
Running at 200 V therefore also tests the throttle rule at its own optimum,
within 7 %.

## Pre-registered predictions (recorded before the run)

The anchor pins `chi_0 = 155.9` at `phi_0 = 17.7 V`. Holding demand and `Te`
fixed and dropping `n` by 3× forces `(1+chi)^alpha` to rise 3×, so each
candidate exponent predicts a **different float**:

| law | (1+chi) factor | predicted phi | V - phi | predicted exhaust KE |
|---|---|---|---|---|
| alpha = 1 (OML sphere) | 3.00 | **53.4 V** | 146.6 V | 118 eV |
| alpha = 0.893 (tail fit, the model's default) | 3.42 | **60.9 V** | 139.1 V | 112 eV |
| alpha = 0.82 (settled fit) | 3.82 | **68.0 V** | 132.0 V | 107 eV |
| alpha = 0.5 (OML cylinder) | 9.00 | **160.4 V** | 39.6 V | 32 eV |

`alpha = 0.5` is refuted outright by any healthy run: it predicts a near-choke
(escape collapses, KE ~32 eV). The `1` / `0.89` / `0.82` trio spans 53–68 V —
a 27 % spread, wider than the anchor's settle band, so the run discriminates
along a **new axis** using an exponent fitted on the old one. That is the
strongest test this campaign can buy for one overnight.

**A float of 53–68 V also puts the run above the 50 V benign-float gate.**
That is expected and is itself the headline: it would be the first *measured*
confirmation that thin plasma, not emission, is what ends the operating
envelope. A gate flagged for this reason is a finding, not a failure — the
same convention as the slender stage's hypothesis B.

## Domain sizing (why rmax grows 30 → 40 mm)

`lambda_D` grows as `1/sqrt(n)`: 1.96 mm → 3.40 mm. The containment gate
(`phi` at the radial edge < 1.0 V) would fail at the old radius. The new
radius is not guessed — it is sized from the **measured** radial decay of the
committed 200 V run (`outputs/20260805T045954Z_b87fbefc`, ppc32 convergence
run), whose potential falls off as

```
phi(r) ~ phi_skin * exp( -(r - r_probe) / (1.79 * lambda_D) )
```

At `rmax = 40 mm` that leaves 10.3 `lambda_D` of skin-to-edge standoff and
predicts `phi_edge ~ 0.22 V`, a 5× margin under the gate. (The same formula
predicts 0.1 V for the anchor, which actually measured 0.0016 V — the
estimate is conservative by ~60×.) Cost: 119,680 cells, 1.36× the anchor.

This is a *numerics* change, not a physics one, and must be disclosed as such
wherever the run is cited: the thin row is compared to the anchor across a
domain-size change, justified by the measured decay law above.

## Acceptance

The frontier gate family, unchanged (escape ≥ 95 %, current balance, momentum
bound, sheath containment, ledger-vs-dump cross-checks, thrust floor), plus:

- **the exponent discrimination reported as a finding, not a gate** — any
  float in 45–75 V is a successful measurement;
- the benign-float gate (`phi < 50 V`) is expected to flag, and flagging is
  a publishable result, not a run failure;
- the settle caveat of `SCALING_LAWS` §5 applies with more force here: thin
  plasma is a slower spring, so the late-time `phi` slope must be reported
  with the float and the settled value bracketed, exactly as the 300 V run
  did (36.3 V tail → 42–48 V extrapolated).

## AMENDMENT — 2026-08-06: unchained before launch, deferred by scope decision

The run was queued behind the slender-body run and **unchained before it ever
started** (operator decision; no run directory exists, nothing to discard).
The pre-registration above stands unchanged and unexecuted.

Why, recorded so the reasoning survives the decision. Re-examining what this
run actually tests, the value is narrower than the plan implies:

- The law's density dependence is `I ∝ n · (1 + chi)^alpha`. The `n`-linear
  part is the one-sided thermal flux, **already validated to ±1 % at step
  `collector.thermal`**, and `chi = e*phi/kTe` has no density dependence at
  all. `alpha` is **already discriminated on the voltage axis** (§4 VERDICT:
  1 refuted, 0.5 refuted, 0.82 favored).
- So no new fitted parameter is under test. The single assumption being probed
  is that `alpha` and `beta` do not drift as the body moves toward the OML
  limit — `r_probe/lambda_D` goes 2.5 -> 1.5 at n0/3.
- And the settle caveat blunts even that. The 300 V run read 36.3 V at 800 ns
  against a ~42–48 V settled value, a 15–30 % under-read; the thin row's
  spring is ~3x stiffer. The pre-registered predictions span 53–68 V, a 27 %
  spread — the settle uncertainty eats the discrimination.

**Net: a gross-breakdown detector, not a measurement.** It would refute a
collapse toward `alpha = 0.5` unmistakably (phi heading for 160 V) and
otherwise return "no breakdown over 3x of a 30x mission swing". Worth ~9.5
GPU-hours only when the card is otherwise idle, and the first thing to cut.

The plan is left committed and intact: if the density axis is ever challenged
by a reviewer, this is a ready, pre-registered, un-p-hacked run — the config
recipe, predictions, domain sizing, and acceptance policy
(`acceptance_exploratory.yaml`) are all fixed in advance.

Higher-value use of a comparable slot, if one opens: the **full-return null
fixture** (roadmap item: momentum ledger + null test), which answers the
reviewer momentum objection in `THESIS.md` head-on — a configuration where
every beam electron returns to the craft and the measured thrust must be ~0 —
rather than answering it by computation from existing runs.

## What it opens

- Mission rows carrying `extrap_density` become interpolated over a 3× band
  instead of extrapolated, tightening `model/MODEL.md` §6's envelope semantics.
- The `1/(n*sqrt(Te))` float-stiffness claim of `SCALING_LAWS` §8 gets its
  first direct measurement.
- If the float lands above 50 V, the corridor argument in the paper
  (550–600 km closes on harvested power) gains a *measured* upper edge on the
  density side rather than a modelled one.

## RESULTS — 2026-08-09: executed as pre-registered; float unsettled at 800 ns

Run `2_chipsat_thruster/outputs/20260808T165839Z_41b114e2`
(config `variants/thin_plasma.yaml`, deltas exactly as pre-registered above;
grid resolved to 272×440 = 119,680 cells, rmax snapped to 40.8 mm on the
0.15 mm grid; steps and dt bit-identical to the anchor: 159,160 @
5.0261e-12 s). 8.4 h wall on the RTX 3060. Analysis
`results/20260808T165839Z_41b114e2/20260809T012347Z_aae666a6`, exploratory
policy: **VERDICT PASS — all 6 required gates**. Informational
`phi_vs_float200_reference` flags, as it must (the float moving off the
anchor is the experiment).

**The device is healthy at n0/3** — the amendment's realistic deliverable,
delivered: escape 98.5 %, exhaust KE 132.9 eV, F_beam 12.95 nN (thrust gate
vs anchor PASSES), current balance closes to 4.9 %, containment margin 10×
under the gate at the enlarged radius. No breakdown over a 3× step of the
30× mission density swing.

**The exponent discrimination was NOT achieved.** phi_body read 29.5 V
(analysis window; final sample 31.6 V) at 800 ns — below the 45–75 V
pre-registered measurement band — and the tail is still *accelerating*:
windowed slopes 8.1 → 12.1 → 19.3 → 27.7 → 26.8 V/µs over 300–800 ns.
Exponential-settle fits diverge (the trace is nowhere near its asymptote),
so unlike the 300 V run there is no defensible settled bracket, only a hard
lower bound: **phi_settled > 31.6 V**. For calibration, the anchor's own
committed trace ends the same way (16.5 V/µs at 800 ns, final 18.3 V) — the
campaign's "float" has always been an 800 ns read with a disclosed slope,
and the settle caveat this plan flagged is decisively stronger on the thin
row, exactly as the `1/(n*sqrt(Te))` stiffness claim predicts (the thin
trace at 800 ns has covered ~1.7× of a required ≥3× rise in (1+chi); the
anchor at the same age was substantially closer to its own asymptote).

Scorecard against the pre-registered predictions:

- `alpha = 0.5` (near-choke at 160 V, KE ~32 eV): **disfavored but not
  refuted.** No choke signature at 800 ns and beam observables are fully
  healthy — but at phi = 31.6 V the run never entered the regime where that
  candidate's escape collapse would show, and the accelerating tail cannot
  exclude a much higher settled float.
- `alpha = 1 / 0.893 / 0.82` (53.4 / 60.9 / 68.0 V): **undiscriminated.**
  All three remain consistent with a trace that is still >20 V below the
  nearest prediction and climbing.
- Matched-time A/B (the one clean comparison this run gives): at identical
  demand, steps, and age, `(1+chi)` rose 1.73× for a 3× density drop. Any
  settled `alpha <= 1` requires >= 3×, so the trace is at most ~55 % of the
  way to the nearest candidate's asymptote in chi. (A dynamic I–V fit from
  the climb is NOT usable: in balance the collected current is pinned at
  the ~330 µA demand — the trace rides the load line, not the collection
  characteristic. Both runs measure `alpha_dynamic ~ 0` for this reason.)

**Disclosure**: the thin row is compared to the anchor across the
rmax 30 → 40.8 mm domain change, per the sizing section above.

**What it would take to finish the measurement**: simulated time, not
resolution — the pre-registered acceptance band sits several spring times
beyond 800 ns at this stiffness. A t_end ~2.4 µs continuation (~3× cost,
~25 GPU-h) with the same deck would put the 53–68 V band inside reach, or
refute alpha = 0.5 by observing saturation well below 160 V.

## CONTINUATION — 2026-08-11: the 2.4 µs run, recorded before launch

Launched as the paragraph above prescribes: the same deck re-run from
scratch with **three** `run:` changes and nothing else —

- `t_end 800 ns → 2.4 µs` (the point of the run);
- `max_steps 160,000 → 480,000` (cap raised to admit the ~477.5k resolved
  steps at the anchor dt; the old cap would have truncated at 1/3);
- `phi_ceiling 100 → 180 V` (disclosed: the alpha = 0.5 candidate predicts
  a 160.4 V float, which the old ceiling would have aborted as a choke
  mid-climb; the continuation exists to *observe* that saturation or its
  absence, so the detector is moved above the highest live prediction.
  A genuine runaway still trips it).

Physics deck, grid, dt, seed, plasma row, drive: bit-identical to the
executed 800 ns run. The pre-registered predictions and the 45–75 V
measurement band stand unchanged; acceptance is the same exploratory
policy (`acceptance.yaml`). Expected cost ~25 h wall on the RTX 3060
(measured 8.4 h / 800 ns, ~3× steps at identical per-step cost).
Launch record: `thin_plasma_continuation_chain.sh`, `logs/`.

### RESULTS — 2026-08-12: the float SETTLED, and it settled LOW

Run `outputs/20260811T213635Z_acc8f8f9` (477,480 steps @ the anchor dt,
2399.9 ns, 22.4 h wall). Analysis
`results/20260811T213635Z_acc8f8f9/20260812T200258Z_aef34e72`:
**VERDICT PASS — all 6 required gates.** Escape 99.13 %, F_beam 12.39 nN
(thrust gate vs anchor passes), exhaust KE 122.0 eV vs 122.6 eV predicted
from the injection-plane potential, current balance closes to 0.10 %,
edge phi 0.19 V (5× under the gate at the enlarged radius).

**phi_body = 42.5 V, settled.** Tail mean 42.47 V, final sample 42.59 V,
late slope −0.00014 V/ns — i.e. flat to within noise, versus +27 V/µs and
climbing when the 800 ns run ended. This is the campaign's first *settled*
float: the finite-time-equilibrium caveat does not apply to this row.

Scorecard against the pre-registered predictions:

- **alpha = 0.5 (160.4 V): REFUTED.** The float saturated at 42.5 V with
  the choke detector deliberately parked above 160 V; nothing heads there.
  The density axis now refutes it independently of the voltage axis.
- **alpha = 1 / 0.893 / 0.82 (53.4 / 60.9 / 68.0 V): ALL OVERSHOOT.** The
  settled float lands *below* the entire 45–75 V measurement band. At
  fixed demand, `(1+chi)` rose 2.39× for the 3× density drop, where any
  fixed alpha <= 1 requires >= 3×. Read as an exponent, the density axis
  measures **alpha_eff = ln 3 / ln 2.39 = 1.26**; read at the model's
  default alpha = 0.893, it is a **~38 % rise in beta** (effective
  collection area) as `r_probe/lambda_D` fell 2.5 → 1.5 — the direction
  sheath-expansion toward the OML limit predicts.
- **The benign-float gate (phi < 50 V) PASSES** — the plan expected it to
  flag. Thin plasma at n0/3 does *not* end the operating envelope at the
  anchor's drive; the fitted law is **conservative along the density
  axis** (it over-predicts the float cost of thin plasma).

Caveats, disclosed: this is a two-point A/B along density (one 3× step),
compared across the rmax 30 → 40.8 mm domain change per the sizing
section; alpha_eff = 1.26 is a secant exponent between those two points,
not a fit, and says nothing about behavior beyond n0/3 toward the
`~1e11 m^-3` night minimum where `r_probe/lambda_D` keeps falling.

What it changes: mission rows carrying `extrap_density` are now bounded
by a *measured, conservative* law over a 3× band — the model's density
extrapolations err toward pessimism (predict more float than occurs); the
`1/(n*sqrt(Te))` stiffness claim gets its settle time (~2 µs to flat at
n0/3); and the corridor argument gains a measured density-side data point
*inside* the benign envelope rather than a modelled edge.
