# PLAN — capstone.slender_body (geometry axis; pre-registered 2026-08-05)

**Status: PLANNED, not scheduled.** GPU is occupied by the 200 V convergence
pair; this stage and the night-density stage are the two targeted follow-on
measurements identified by the minimal model (see `model/MODEL.md` §6 and
paper §Application). Recorded now so the hypotheses predate the run.

## What it measures

All committed runs share one squat-can geometry (Ø10 × 5.9 mm). Drag buys
the ram silhouette; collection and solar power buy the skin — so slender
bodies are the up-mass scaling path (paper §"The geometry lever"). But the
collection exponent is geometry-dependent by theory (OML: sphere α = 1,
long cylinder α = 0.5; the can measured 0.82–0.89, between the limits), so
the fitted law must not be extrapolated to slender bodies. One run opens
the axis.

**Deck:** the `2_chipsat_thruster` machinery with the can lengthened to
Ø10 × 30 mm (L/r = 6), at the SAME drive and demand as the committed 200 V
anchor (`cathode_offset: -200 V`, `i_beam: 0.342e-3`, same plasma row,
seed 42). Identical demand makes the run a clean A/B against the anchor:
the only physics change is where and how the return current is collected.

## Pre-registered competing hypotheses (recorded before the run)

Total skin area grows 3.24× (3.4 → 11.0 cm²). At fixed escaped current
(~0.337 mA), where does the float settle?

| hypothesis | form | predicted φ |
|---|---|---|
| A — area-only scaling | can's fitted α ≈ 0.89 holds; enhancement demand drops 3.24× | **≈ 4–5 V** |
| B — cylinder-limit lateral | lateral wall collects at α ≈ 0.5; caps at can-like α | **tens of volts**, possibly above the 50 V benign gate |

The hypotheses differ by nearly an order of magnitude in φ — strongly
discriminable by a single gated run. Hypothesis B failing benignly would
itself be a design-critical finding: it would mean slender bodies pay a
charging tax the area argument hides, and the wall-budget trade (solar vs
bare collector) tightens. Exact numeric predictions for both hypotheses
should be generated with the model's geometry-split variant at scheduling
time and appended here before launch.

## Config sketch (delta from `2_chipsat_thruster/config.yaml`)

```yaml
# stage_id: capstone.slender_body
geometry:
  z_bot: -30.0e-3          # can floor: Ø10 x 30.5 mm slender can (was -5.0e-3)
  # all other geometry, electrical, beam, plasma, reservoir keys inherited
compute:
  gpu_arena_bytes: 9000000000   # domain grows to ~200 x 615 cells (Lz ~92 mm)
```

Everything else — dx 0.15 mm, CFL dt, ppc 16, t_end 800 ns, diag cadence,
choke detector — inherited unchanged. Estimated cost ~2–2.5× the reference
run ≈ **12–15 h** on the RTX 3060.

## What it opens

- The geometry-split collection law in `model/minimal_model.py`
  (`I = β_cap·A_cap·(1+χ)^α_cap + β_lat·A_lat·(1+χ)^α_lat`), letting the
  model sweep aspect ratio the way it now sweeps voltage.
- Slender-body mission rows (rod/plate designs at 400–500 km) move from
  flagged extrapolation to measured envelope.
- The r ≲ λ_D end of the axis connects to bare-tether collection
  (Sanmartín 1993), bridging the device to flown physics.

## Acceptance

Same gate family as the frontier stages (escape ≥ 95 %, benign float,
current balance, momentum bound, sheath containment, ledger-vs-dump), plus
the hypothesis discrimination reported as a finding, not a gate — a
hypothesis-B float above 50 V is a valid, publishable outcome.

---

## AMENDMENT — 2026-08-05: first attempt invalid by design flaw, killed

The naive config sketch above (`z_bot: -30 mm`, all else inherited) was run
as `2_chipsat_thruster` variant `20260805T190609Z_f59e228b` and **killed at
69 % by operator decision**. The flaw: the deck ties the cathode disk to the
can floor, so lengthening the can stretched the **gun gap** from 4.7 mm to
~30 mm. Child–Langmuir scales as 1/d², putting the commanded 0.342 mA at
~60× the long gap's space-charge ceiling: the beam blew open over the drift
and self-scraped.

Interim ledger at 532 ns (informal — run has no COMPLETE manifest, NOT
citable evidence): beam fate 91.1 % body / 7.9 % escape / 0.0 % cathode;
F_beam ≈ 1.19 nN; φ ≈ 0.3 V. **The A/B collection hypotheses were never
tested** (nothing escaped, so the float never rose); they remain open.

What the attempt establishes as a design rule (derivable from the measured
emission-ceiling law, no citation of the dead run needed): **a slender body
must keep the cathode–aperture gap at its short design value and grow the
body around the gun** — the emitter cannot sit at the far end of a long can.

Corrected stage requirement before rerun: a cathode-standoff parameter in
the stage geometry (cathode z decoupled from `z_bot`, held 4.7 mm below the
lid), committed to git before the production run so provenance stays clean.
The pre-registered hypotheses and acceptance above carry over unchanged.
