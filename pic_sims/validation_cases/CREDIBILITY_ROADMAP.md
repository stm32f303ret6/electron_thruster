# Credibility roadmap — from concept-grade to publication/design-grade

**Where we are (2026-08-03):** rungs 1-8 are green and all 9 cross-stage
checks pass, but **rung 9 `capstone.mission_envelope` FAILS**, so the suite
verdict is FAIL. That failure is a result, not a regression: it is the first
rung whose gates are *pre-registered predictions*, and it falsified the
design model's collection law. **For presenting a concept the physics ladder
still suffices — but the 0-D design model must not be used for supply-margin
or choke-risk numbers until item 0.1/0.2 below is done.**

Since 2026-08-01 the repository also gained the two halves the ladder was
missing at either end: `orbit_sims/` (what the mission demands) and
`design_sims/` (what to run the thruster at). Two items below were closed by
that work and are struck through. This document is the ordered backlog for anyone who later needs
more than concept-grade: each item says what claim it unlocks, the coding
effort, and the simulation cost (CPU-build estimates from measured rates).

Discipline reminders that apply to every item (plan §9.3): tolerances are
set before runs; any changed metric or tolerance needs a new `policy_id` and
a fresh run to count as validation; convergence/seed studies are *reported
evidence* first, promoted to gates only with a policy bump.

---

## Tier 0 — NEW, and now the top priority: fix the collection law

Rung 9 measured β at three operating points and found it is **not a constant
and not a function of χ** — it is the OML-efficiency factor and tracks
`r_p/λ_D` (full OML at 0.83; barrier-limited to 40–46 % at 2.5–2.7). The
anchor point itself sits outside OML's validity window. Details:
`capstone/3_mission_envelope/README.md`.

| # | item | unlocks | coding | sim time |
|---|---|---|---|---|
| 0.1 | **Break the n_e / (r_p/λ_D) degeneracy** with 1–2 `collector.thermal`-style rungs at different `(n, Te)`. All three current points sit at Te 1320–1530 K, so `r_p/λ_D ∝ √n_e` and the two readings are indistinguishable. A collector rung measures collection against an **exact** law with no thruster in the loop — by far the cheapest way to map β. | which variable β actually tracks; a defensible revised law form | ~1–2 h per rung | **~2–3 h each** |
| 0.2 | **Revise the law form** to `β₀·(r_p/λ_D)^−q·I_the·(1+χ)`, refit `laws.yaml`, issue policy `capstone.mission_envelope.v2` with fresh predictions, re-run the pair | a design model usable for supply margin and choke risk | ~0.5 d | ~21 h |
| 0.3 | **Real-O⁺ sensitivity on the barrier** (one capstone-class run at a realistic ion mass) | the finding is *specifically* about barrier formation, the physics most sensitive to the 400 mₑ surrogate; without this the exponent is provisional | config only | ~10–20 h |
| 0.4 | **`refit_laws.py` spread guard**: refuse to average a constant whose across-record log-spread exceeds a threshold, instead of silently emitting a meaningless mean | the failure mode rung 9 just demonstrated cannot be re-introduced quietly | ~30 lines + test | none |

## Tier 1 — cheap convergence & coverage evidence (~1 day, mostly zero code)

| # | item | unlocks | coding | sim time |
|---|---|---|---|---|
| 1.1 | **PPC doubling on `collector.biased_10v`** (ppc 16→32, config variant) | "the collector fractions and sheath radius are not shot-noise artifacts" — the trend feeding the capstone | none | ~2.5–3 h |
| 1.2 | **Grid refinement on `collector.thermal`** (dx 0.15→0.075 mm, dt halved) | measured convergence against an *exact* law; validates the 13.1 cells/λ_De choice every stage inherits | none | ~2–3 h |
| 1.3 | **Seed variation on `collector.floating` + `collector.thermal`** (2 extra seeds each) | error bars on φ_f = −0.251 V and the thermal currents instead of point values | none | ~2 h total |
| 1.5 | ~~**Collector rung at a second plasma row**~~ → *partly addressed*: rung 9 exercises collection at n_e = 1.97e11 (12× below PLASMA_MAX) inside the full system. A closed-form `collector.thermal`-style rung at that row is still worth ~2–3 h and is the cheapest remaining coverage item. | `I_the(n,Te)` anchored against an exact law away from PLASMA_MAX | ~1 h (config + ladder tuple) | ~2–3 h |
| 1.4 | **Close gap G3: new `emitter.holed_anode` scenario D** at the capstone's gun operating point (200 V, ~4.7 mm-gap-equivalent, rms 2.6e5 m/s, ppc_beam 16) | the capstone's gun voltage/temperature/graininess is bracketed by a validated rung | ~1–2 h (scenario block + acceptance + ladder tuple + tests) | ~5–10 min |

Report each comparison in the stage README + a small committed table; no
gate changes needed.

## Tier 2 — capstone headline numbers (~2 overnights)

| # | item | unlocks | coding | sim time |
|---|---|---|---|---|
| 2.1 | **C6 stationarity metric** (slope + block-mean consistency over the tail), first in the capstone's `analyze.py`, report-only | an honest number for "how steady is the plateau" instead of a raw dφ/dt line | ~150–250 lines + tests | none |
| 2.2 | **Capstone long-tail run** (t_end 800 ns → ~2 µs, the ion transit clock) | φ_body/escape/F_beam as an equilibrium claim, not an 800 ns snapshot (current late dφ/dt ≈ 0.016 V/ns) | config only (needs 2.1 to interpret) | ~16 h |
| 2.3 | **Capstone PPC doubling** — run only if 1.1/1.2 show sensitivity | grid/noise robustness of the headline numbers themselves | none | ~13 h |

After 2.2 PASSes under a pre-registered updated policy, the float200 anchors
should be re-baselined to the equilibrium values (new `policy_id`, disclosed).

## Tier 3 — structural robustness fixes (code only, ~1–2 days, no runs)

Known weaknesses from the 2026-08-01 code review; none currently corrupts a
result, but each is a fail-open or stale-evidence path a hostile reviewer
could poke:

| # | item | risk it closes | coding |
|---|---|---|---|
| 3.1 | `cross_stage.py`: missing metric/config key → **ERROR**, not SKIP; suite treats any non-PASS-non-SKIP as failing | a renamed metric silently un-evaluates a cross-stage claim while the suite stays green | ~30 lines + a `test_cross_stage.py` |
| 3.2 | `run_ladder.py --analyze-only`: require explicit run IDs (or at least warn when the latest COMPLETE run predates the live `config.yaml`) | silently re-grading stale evidence as current | ~50 lines |
| 3.3 | `2_electron_gun/analyze.py`: scenario order from the frozen `config_used.yaml` set, bound by name not position | reordering `scenarios:` silently rebinds the A→B/B→C comparison gates | ~40 lines + tests |
| 3.4 | `2_electron_gun/helpers.py`: fix the dead section-key validation (unknown keys accepted, missing keys raise raw `KeyError`) | config typos passing silently (stage 1 already rejects both) | ~20 lines + tests |
| 3.5 | `ladder_contract.py`: wrap numeric coercions (`_num`, `Metric.measure`, `complete_run`, `_canonicalize`) in `ContractError` | a malformed `acceptance.yaml` bound crashing with exit 1 — the code reserved for "gate failed" | ~40 lines + tests |
| 3.6 | **C9** in `2_electron_gun`: window-match the arrival-energy ensemble to the field snapshot used as its reference | the known inconsistent-ensemble energy comparison | ~50–100 lines |

## Tier 4 — full scientific credibility (the expensive rest)

| # | item | unlocks | cost |
|---|---|---|---|
| 4.1 | **C12 convergence matrix**: grid × ppc × domain × seed for every promoted quantitative claim, all stages | "quantitative validation" label without asterisks | ~100–300 h CPU + curation |
| 4.2 | **Ion-mass scaling study**: rerun `collector.*`/`collector.floating` at mi = 1600, 6400 mₑ and fit the known √mi scalings; extrapolate to real O⁺ (~29,000 mₑ) with a documented argument. A direct real-O⁺ capstone run is ~√(29000/400) ≈ 8.5× the ion clock → ~55 h/run | real-ionosphere numbers instead of surrogate-mass numbers — the biggest physical caveat in the whole suite | ~10–20 h for the scaling rungs; ~55 h per real-mass capstone |
| 4.3 | **C8 properly**: a planar-anode sweep locating actual reflection onset (or keep the "rough scale" label forever — acceptable) | a defensible virtual-cathode threshold statement | ~1 day + ~1 h runs |
| 4.4 | Fresh validation runs under pre-registered policies for anything Tier 1–3 changed | the §9.3 discipline: calibration ≠ validation | re-run cost of the affected stages |

## Explicit non-goals

- **Checkpoint/restart** — deferred by design (plan §2); an interrupted run
  is FAILED and rerun.
- **A shared simulation framework** — physics duplication between stages is
  deliberate; do not "clean it up."
- **Preemptive Tier 4 work while the goal is a concept presentation** — run
  Tier 1 items *reactively* if a reviewer asks; they exist to be answerable
  overnight, not to be done in advance.
