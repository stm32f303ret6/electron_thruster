# THESIS_PLAN — put the claim at the top, let the ladder prove it

**Trigger:** execute after `capstone.mission_envelope` (rung 9, scenarios A_day_p95
and B_night_worst) finishes and its cohort analysis lands.

**Goal:** the repository currently proves physics but never states its thesis.
The README leads with architecture; the actual discovery — a propulsion regime
nothing else occupies — exists only in conversation. This plan restructures the
top-level README so the claim comes first, every leg of the claim maps to a
ladder rung, and the three missing quantitative pieces (figures of merit, power
closure, the envelope figure) get computed from committed measurements.

---

## The claim (draft text, to be finalized in Phase 3)

> Drag compensation for gram-class spacecraft at 450–600 km requires 1–100 nN
> of continuous thrust. No flight propulsion system can supply it: the smallest
> controllable flight EP (precision electrosprays/FEEP, ~5–30 µN) sits two to
> three orders of magnitude above the demand, in packages heavier than the
> entire spacecraft. This device fills that slot with ion-thruster-class energy
> conversion (~73 %), zero propellant and zero net mass flux, at 10–100 mW — a
> power level the spacecraft's own skin can harvest — using no tank, no feed
> system, no discharge chamber, and no neutralizer, because the ionosphere is
> the propellant reservoir and the spacecraft surface is the return electrode.
> Its thrust-per-watt is ~200× below an ion thruster's, which is precisely why
> it only owns the nN regime — and why nothing else does.

### Wording guardrails (agreed, do not regress)

- **Energy efficiency, not thrust-per-watt.** η ≈ 0.73 is jet-power /
  electrical-power. F/P is ~0.2 µN/W, ~200× below gridded ion. Never let the
  README imply parity on F/P; state both numbers side by side.
- **"Continuous" means no total-impulse limit, argued via the system floor,
  not propellant mass.** At nN scale, 5 years of thrust is ~5 N·s ≈ 0.3 g of
  electrospray propellant — propellant *mass* is not the argument. The argument
  is the dry-system floor: tank + feed + valves + PPU is ~0.3–1 kg and does not
  shrink to gram scale; this concept's floor is a cathode, a boost converter,
  and the spacecraft skin.
- **The nuance on "no ion thruster goes that low":** gridded ion/Hall bottom
  out ~mN; LISA-Pathfinder-class colloids/FEEP reach 5–30 µN with ~0.1 µN
  resolution — still 100–1000× above chipsat drag, in kg-class systems. State
  it that way so the claim is armored.
- **The efficiency-indifference boundary is real and must be stated:** the
  F/P penalty is invisible at nN (mW), noticeable at µN (~10 W for CubeSat
  drag — disqualifying), decisive at mN. The handoff — electron thruster below
  ~0.1 µN, electrospray at µN, ion/Hall at mN — is part of the claim, not a
  concession.
- **Altitude honesty:** at 400 km / solar max the *power* side does not close
  on the can's body-mounted cells (~110–165 mW mean demand vs ~30 mW
  harvest). The unconditional claim lives at ~450–600 km (or 400 km with a
  plate geometry). Phase 2 turns this from estimate into computed rows.

---

## Phase 0 — ingest rung 9 (prerequisite, nothing else starts before this)

1. Run the cohort analysis; record the measured φ_body / F_beam ratios against
   the pre-registered predictions and the β-spread across χ = 149 / 200 / 386.
2. Update `LADDER_SUMMARY.md` rung 9 table (it carries a "runs in progress"
   placeholder) with measured values and the verdict.
3. **Branch on outcome:**
   - **PASS:** the (1+χ) collection-law linearity is validated to χ = 386 and
     the design model is out-of-sample-validated. The thesis section may cite
     the full 400 km mission envelope as model-validated.
   - **FAIL / partial:** a gate failure is a finding about the law form, not a
     tolerance to widen (per `design_sims/README.md`). The thesis still stands
     on rung 8 + the bounded envelope; scope the claim to the validated χ range
     and document the law-form finding prominently. The README restructure
     proceeds either way — only the wording of the model-validation sentence
     changes.

## Phase 1 — figures of merit (no new sims; committed metrics only)

Add the numbers the claim rests on, derived the same way `design_sims`
constants are — from committed `metrics.json`, with provenance.

1. **New small module `design_sims/figures_of_merit.py`** (or a section in
   `operating_point.py --report`): for each operating point (rung 8 anchor,
   rung 9 A and B, measured where available), compute and print:
   - electrical input `P = I·V`
   - jet power `P_jet = f_esc·I·KE`  (KE = ke_ledger·(V − φ))
   - energy efficiency `η = P_jet / P`  (expect ≈ 0.66–0.74 across the envelope)
   - thrust-per-watt `F/P`  (expect ≈ 0.15–0.2 µN/W)
   - effective exhaust velocity and the note that net mass flux is exactly zero
     (charge balance ⇒ electrons in = electrons out).
2. **Sanity identities to pin in `design_sims/tests/`:**
   `η = f_esc·ke_ledger·(V−φ)/V` and `F/P = k·f_esc·√(ke_ledger·(V−φ))/V`
   (in consistent units) — so the README numbers can never drift from
   `laws.yaml`.
3. **Competitive-landscape table** (README material, sourced from literature,
   clearly marked as such — these are *context*, not measurements):

   | system | F/P | min controllable thrust | propellant system | works at mW |
   |---|---|---|---|---|
   | gridded ion / Hall | 30–60 µN/W | ~mN | tank + feed + neutralizer | no |
   | electrospray / FEEP | ~10–30 µN/W | ~5 µN (0.1 µN res.) | tank + feed, ~kg class | no (~0.1 W floor) |
   | photon (laser/LED) | 0.0033 µN/W | arbitrarily low | none | yes |
   | **this** | **~0.2 µN/W** | **~nN** | **none** | **yes** |

4. **"Why electrons, not ions" paragraph** (defines the regime boundary):
   ejecting collected ambient ions at 200 V would give ~30 µN/W — but passive
   ion collection is ram-flux-limited to ~0.2 µA/cm², vs the OML-enhanced
   electron ceiling ~(1+χ)-fold above thermal. Electrons lose ~240× on F/P and
   win ~10³ on supply ceiling. The emission cap (1.5·I_CL) and the night
   collection cap are the measured edges of exactly this trade.

## Phase 2 — power closure (the one genuinely missing analysis)

The claim says "a power level the spacecraft's own skin can harvest" — make
that a computed statement instead of an estimate.

1. **Minimal solar ledger in `orbit_sims/`** (restoring, in minimal form, what
   the port dropped): per CSV row, `P_avail` from sun vector + eclipse flag +
   a declared cell assumption set (cell efficiency, packing factor, orientation
   model for the three rotation poses), and `P_req = drag_N / (F/P)` using the
   Phase 1 figure of merit. Keep it spacecraft-geometry-explicit and in the
   CSV, consistent with the existing schema discipline.
2. **Closure metric per mission:** fraction of orbits where the energy budget
   balances (with a small storage buffer assumption, stated), analogous to the
   existing duty-cycle metric for thrust.
3. **Altitude sweep:** re-run `orbit_sims` at 500 and 550 km (~13 min each,
   one config override per case) so the claim's sweet spot rests on real
   NRLMSISE-00/IRI rows, not on the ρ ≲ 7×10⁻¹³ kg/m³ back-of-envelope.
   Expected outcome: 400 km closes in thrust (lateral pose, 86 % duty) but not
   in power on the can; ~500–600 km closes in both on body-mounted cells.
4. **Record the crossover** in the README: the altitude/solar-activity boundary
   where the concept is unconditional, and the two levers below it (plate
   geometry — A_solar/A_ram ≳ 10; duty-cycling).

## Phase 3 — README restructure (the deliverable)

New top-level README order:

1. **The claim** — the pitch paragraph above, finalized with Phase 0–2 numbers.
2. **The demand** — nN drag at 400–600 km, from `orbit_sims`' own CSV
   (mean/p95/max at each altitude), one sentence on why this is measured
   demand, not assumption.
3. **The gap** — the competitive-landscape table + the system-floor argument.
4. **The device in one paragraph** — cathode at body − 200 V, skin as return
   electrode, ionosphere as reservoir; zero net mass flux.
5. **The evidence — claim-to-rung map** (the ladder proves the physics):

   | claim leg | rung / artifact |
   |---|---|
   | the gun works and conserves energy | 1–2 (`emitter.*`), µV/meV-level agreement |
   | the skin collects the return current as theory says | 3–5 (`collector.*`), thermal exact ±1 %, OML fraction + sheath trend |
   | an unpinned body floats where theory says | 6 (`collector.floating`), −0.251 V inside the closed-form bracket |
   | the two-electrode craft solves correctly | 7 (`capstone.two_node_laplace`), Laplace-exact |
   | the whole thruster closes its own circuit | 8 (`capstone.floating_body`): balance 3.2 %, escape 98.44 %, 13.65 nN, +16.98 V |
   | emitted electrons do not come back | 8: beam-fate ledger 0.0000 % cathode return; Debye-screening section |
   | no neutralizer hardware is needed | 8: return current 99.9 % ambient electrons at +17 V |
   | the return current costs no thrust | 8: \|F_net\|/F_beam = 0.0035 (measured) |
   | the design model extrapolates | 9 (`capstone.mission_envelope`), pre-registered — result per Phase 0 |
   | the electrode principle works on real hardware | `lab_experiments/electron_gun/` (qualitative) |

6. **Figures of merit** — η, F/P, power closure vs altitude (Phase 1–2).
7. **Honest boundaries** — kept as prominent as today: 400 mₑ surrogate ions,
   electrostatic (no B, no ram), single grid/ppc/seed, finite-time equilibrium,
   400 km power non-closure on the can, and the efficiency handoff above ~0.1 µN.
8. **Then the current content** — the three-trees architecture, dependency
   direction, environments (unchanged, just demoted below the thesis).

Also: add a short "figures of merit" subsection to `LADDER_SUMMARY.md`'s
capstone entry (η and F/P at the anchor point) so the digest carries the
headline numbers next to the evidence.

## Phase 4 — the operating-envelope figure (the discovery as a picture)

1. **Envelope chart** (`design_sims/plots/`): thrust demand distribution
   (drag percentiles vs altitude, from the Phase 2 sweep) overlaid with the two
   supply ceilings — emission `1.5·I_CL(V)` and collection
   `β·I_the·(1+χ_max)` — and the power-available line. The claim is the region
   where demand sits below all three.
2. **Landscape handoff chart:** thrust–power plane with the regions owned by
   electron thruster / electrospray / ion, showing the nN slot as unoccupied
   by anything else. This is the figure a reader remembers.
3. Reuse the existing `dataviz`-quality plotting conventions in
   `design_sims/plots/`.

## Phase 5 — optional hardening (post-README, cheap first)

- **`collector.thermal` at the night-row density** (~2–3 h, already on the
  ladder's gap list): anchors `I_the(n, Te)` at 1.97×10¹¹ m⁻³ directly,
  decoupling "collection law wrong at low n" from "system model wrong".
- **Charged-body ion drag note:** one documented estimate of ram-ion
  deflection drag on the +17…+50 V body (sheath-scale cross-section;
  ~1 % of drag at day, possibly ~5–10 % of the small night thrust) — an
  unmodeled channel that belongs in the caveat list.
- **Flight-emitter honesty paragraph:** the bench cathode is thermionic
  (~5 W heater — 70× the thrust budget); flight needs a field-emission
  cathode and a mW-scale HV boost stage whose quiescent draw taxes η.
  "No tank, no feed, no discharge, no neutralizer" stays; "no complex
  hardware" gets scoped to exactly that list.

---

## Order of execution and cost

| step | depends on | cost |
|---|---|---|
| 0. rung 9 ingest + LADDER_SUMMARY update | sims done | analysis only |
| 1. figures of merit + tests | 0 | ~small module, no sims |
| 2. solar ledger + 500/550 km sweeps | 1 (needs F/P) | 2 × ~13 min orbit runs |
| 3. README restructure | 0–2 | writing |
| 4. envelope + landscape figures | 2 | plotting |
| 5. optional hardening | 3 | one ~2–3 h PIC run + docs |

Everything except Phase 5's PIC run is analysis, plotting, and writing on top
of already-committed measurements — consistent with the repo's rule that
claims cite committed artifacts, never live model state.
