# Tier M2: transverse-B momentum coupling (3D similarity deck; design only)

> **Status (2026-09-01).** Tier M2 is being executed, but not with the
> instrument below. Momentum conservation for any box around the craft gives
> `F_craft = −(net momentum flux out) + Σ q v×B` over the box; the second
> term is the geomagnetic field's force on the beam and plasma inside the
> box, grows with the box by construction, and is what a control-volume
> ledger of size L reads as `L/r_g`. It is not force on the craft, which
> feels only emission recoil, impacts, and sheath stress. The executed
> instrument is therefore the anchor body, resolved, in a Cartesian 3D deck
> with B ⊥ ẑ and a thrust ledger corrected for the in-box Lorentz term:
> `pic_sims/characterization/magnetized_transverse/` (pre-registration in
> its README) with `transverse_b_numerics/` as the validation mini-ladder
> this note asked for. The text below is preserved as the design record.


Extracted from the magnetized-axis plan (pre-registered 2026-08-08 as
`MAGNETIZED_PLAN.md`, preserved in git history) when tier M1 was unified into
the executed spokes (`pic_sims/characterization/magnetized_1x/`,
`magnetized_10x/`). Tier M1 closed the near-field half of the magnetized
question: null at 1× LEO, a collection tax at 10×. This document holds the
open half, the far-field design. It is the project's largest unexamined
question (hypothesis H1 of the 2026-08-07 external review
`OPTIMISTIC_HYPOTHESES.md`, preserved in git history) and needs its own
committed plan with numeric pre-registrations before any measurement run.

## The gap

Every committed run is electrostatic with B = 0, while the mission flies in
the LEO geomagnetic field (~3×10⁻⁵ T, essentially perpendicular to the thrust
axis on the near-equatorial orbit). B = 0 is defensible inside the simulated
volume and indefensible as a statement about the far field:

| scale | 1× LEO (3×10⁻⁵ T) | 10× (3×10⁻⁴ T) | vs deck |
|---|---|---|---|
| beam gyroradius (147.5 eV) | 1.37 m | 0.137 m | domain rmax 30 mm = r_g/45 (1×) |
| beam gyroradius (83 eV, valley) | 1.03 m | 0.103 m | |
| thermal-e gyroradius | 26.8 mm | 2.7 mm | ≈ rmax (1×); ≈ 1.4 λ_De (10×) |
| ion gyroradius (400 mₑ) | 0.45 m | 45 mm | unmagnetized (1×) |
| electron gyroperiod T_ce | 1191 ns | 119 ns | t_end 800 ns = 0.67 T_ce (1×) |
| Parker–Murphy radius (φ = 17 V, a = 5 mm) | 963 mm | 304 mm | OML capture radius ≈ 61 mm |

The governing identity (exact algebra, recorded so nobody over-reads it):
`F_beam = (I/e)·mₑv = I·r_g·B`, hence for a current system closing at scale
L, `F_Lorentz/F_beam = L/r_g`. This is a restatement of the beam momentum
flux, not independent evidence. The electrostatic result is the L = r_g
special case, and the open quantity is L, which only a far-field run
measures. Outcomes L ≈ r_g (neutral), L > r_g (upside), and effective
L < r_g (a real penalty requiring field-aligned firing) are all live; the
last is the one a reviewer will probe first.

## The instrument

The question: measure F on the source region as a function of L/r_g with
B ⊥ thrust. This is a momentum-coupling measurement, not a sheath-resolution
measurement, so it needs a different instrument than the RZ deck.

1. 3D, domain ≥ 2–4 m across the field (≥ 1.5 r_g), duration ≥ 5 T_ce ≈
   6 µs, B ⊥ ẑ (thrust along ẑ).
2. Resolve the gyro-orbit, not λ_De: dx ~ 2–4 cm. The ambient plasma must
   then be similarity-scaled (lower n so λ_De ~ dx, keeping the ratios that
   govern the answer: r_g/L_domain, beam current relative to ambient thermal
   current, v_orb·T_ce/L). Choosing that scaling correctly is the design
   work.
3. The craft is sub-cell at this resolution: no EB body. The thruster
   becomes a prescribed source/sink region; the measurement is the momentum
   ledger over control surfaces around it (the machinery the ladder's
   ledger-vs-dump gates already trust at 1e-9, re-aimed).
4. Validation mini-ladder before the measurement (the ladder discipline
   applied to the new axis):
   1. single-particle gyro-orbit vs exact r_g and T_ce on the coarse grid;
   2. E×B drift vs analytic;
   3. B = 0 beam-in-plasma momentum-ledger closure on the coarse similarity
      deck vs the fine committed anchor.
   Each is minutes of compute; each gates a numerics claim the measurement
   rides on.
5. Compute is not the obstacle: ~10⁶–10⁷ cells × thousands of steps is hours
   on the reference GPU. The obstacle is design validity. Budget 2–3 days of
   build + validation + a handful of measurement runs (B = 0 control, 1× and
   amplified transverse B).

## Falsification structure

From the identity: measure F_net/F_beam on the control volume.

- ≈ 1 → L ≈ r_g, the electrostatic results stand (retires the largest
  unexamined risk).
- > 1.1 → upside real, re-open the mission table.
- < 0.9 → field-aligned firing becomes a mission constraint, and the executed
  M1 spokes become the primary operating-mode evidence.
