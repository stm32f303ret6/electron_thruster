# PLAN — the magnetized axis (pre-registered 2026-08-08)

**Status: tier M1 PLANNED, committed before its runs launched. Tier M2 is a
design, not a scheduled run.**

## The gap

Every committed run is electrostatic with **B = 0**, while the mission flies
in the LEO geomagnetic field (~3×10⁻⁵ T; near-horizontal and northward on
the near-equatorial orbit, i.e. **perpendicular to the thrust axis** for
essentially the whole mission). B = 0 is defensible *inside the simulated
volume* and indefensible as a statement about the far field:

| scale | 1× LEO (3×10⁻⁵ T) | 10× (3×10⁻⁴ T) | vs deck |
|---|---|---|---|
| beam gyroradius (147.5 eV) | 1.37 m | 0.137 m | domain rmax 30 mm = r_g/45 (1×) |
| beam gyroradius (83 eV, valley) | 1.03 m | 0.103 m | |
| thermal-e gyroradius | **26.8 mm** | **2.7 mm** | ≈ rmax (1×); ≈ 1.4 λ_De (10×) |
| ion gyroradius (400 mₑ) | 0.45 m | 45 mm | unmagnetized (1×) |
| electron gyroperiod T_ce | 1191 ns | 119 ns | t_end 800 ns = 0.67 T_ce (1×) |
| Parker–Murphy radius (φ = 17 V, a = 5 mm) | 963 mm | 304 mm | OML capture radius ≈ 61 mm |

Two distinct physics questions hide in "what does B do", and they need two
different instruments:

1. **Near field (source scale):** does the committed operating point —
   collection, float, escape, thrust production — survive magnetization?
   Answerable on the existing RZ deck (tier M1, this plan's runs).
2. **Far field (gyro scale):** where does the emitted momentum end up — what
   force couples back to the craft once the exhaust gyrates and the return
   current closes through the plasma? **Not answerable in RZ at 30 mm**; a
   transverse B breaks axisymmetry and the relevant scale is r_g ≈ 1.4 m
   (tier M2, design below).

**The governing identity** (exact algebra, recorded here so nobody
over-reads it): `F_beam = (I/e)·mₑv = I·r_g·B`, hence for a current system
closing at scale L, `F_Lorentz/F_beam = L/r_g`. This is a *restatement* of
the beam momentum flux, not independent evidence — the electrostatic result
is the L = r_g special case, and the open quantity is **L**, which only a
far-field run measures. Outcomes L ≈ r_g (neutral), L > r_g (upside), and
effective L < r_g (a real penalty requiring field-aligned firing) are all
live; the last is the one a reviewer will probe first.

---

## Tier M1 — field-aligned runs on the committed deck (RZ, cheap)

The only external B compatible with the RZ deck is **axial** — which is
exactly the **field-aligned-firing configuration**, the fallback operating
mode if the far-field answer ever comes back unfavorable. Two variant runs
of the 200 V anchor (`capstone.floating_body` deck, exploratory policy,
committed configs untouched — the `plasma.Bz_T` optional key is
baseline-preserving like `geometry.cathode_standoff`):

| run | Bz | what it probes |
|---|---|---|
| M1a | 3×10⁻⁵ T (1× LEO) | the flight condition, field-aligned |
| M1b | 3×10⁻⁴ T (10×) | amplified: thermal-e gyroradius pushed to sheath scale (2.7 mm ≈ 1.4 λ_De) |

### Pre-registered hypotheses

**H-M1-null (expected):** every anchor observable inside its exploratory
trust gates and close to the B = 0 anchor — |Δφ| ≤ 2 V, |ΔF|/F ≤ 5 %,
Δescape ≤ 1 pp — at **both** field strengths. Grounds: (i) the beam is
axially field-aligned and r_g ≥ 0.10 m ≫ every device scale, so beam optics
and escape cannot be B-limited; (ii) the Parker–Murphy ceiling (963 / 304 mm)
sits far above the OML capture radius (61 mm), so magnetized collection is
not flux-starved even at 10×; (iii) ions stay unmagnetized at 1×.

**H-M1-tax (the alternative):** at 10×, cross-field electron transport
stiffens collection once r_g,e ~ λ_De: φ rises by > 2 V at fixed emission
(the collection law's effective βA falls), KE = κ(V−φ) and thrust fall
correspondingly. Direction pre-registered, magnitude not.

**What M1 cannot decide, stated up front:** the far-field coupling. Even at
10×, domain/r_g,beam ≈ 0.22 — the exhaust leaves the box long before it
gyrates. A null here closes the *near-field* half of the magnetized question
and establishes the field-aligned mode; it licenses no claim about
transverse-B thrust.

### Acceptance and cost

Policy: `capstone.exploratory_axes.v1` (φ/thrust are reported comparisons
against the anchor; trust gates required, tolerances unchanged). Runs are
`--config` variants per the variant-run convention (`SETUP.md`); each run
freezes its own `config_used.yaml` + case hash. Cost: 2 × ~6.3 h ≈ **13 h**
on the reference GPU, sequential.

---

## Tier M2 — transverse-B momentum coupling (3D similarity deck; DESIGN ONLY)

The question: measure F on the source region as a function of L/r_g with
**B ⊥ thrust**. This is a momentum-coupling measurement, not a
sheath-resolution measurement, and it needs a different instrument:

- **3D**, domain ≥ 2–4 m across the field (≥ 1.5 r_g), duration ≥ 5 T_ce ≈
  6 µs, B ⊥ ẑ (thrust along ẑ).
- **Resolve the gyro-orbit, not λ_De**: dx ~ 2–4 cm. The ambient plasma must
  then be *similarity-scaled* (lower n so λ_De ~ dx, keeping the ratios that
  govern the answer: r_g/L_domain, beam current relative to ambient thermal
  current, v_orb·T_ce/L). Choosing that scaling honestly is the design work.
- **The craft is sub-cell at this resolution**: no EB body. The thruster
  becomes a prescribed source/sink region; the measurement is the momentum
  ledger over control surfaces around it (the machinery the ladder's
  ledger-vs-dump gates already trust at 1e-9, re-aimed).
- **Validation mini-ladder before the measurement** (the ladder discipline
  applied to the new axis): (1) single-particle gyro-orbit vs exact r_g and
  T_ce on the coarse grid; (2) E×B drift vs analytic; (3) B = 0 beam-in-
  plasma momentum-ledger closure on the coarse similarity deck vs the fine
  committed anchor. Each is minutes of compute; each gates a numerics claim
  the measurement rides on.
- Compute is NOT the obstacle: ~10⁶–10⁷ cells × thousands of steps is hours
  on the reference GPU. The obstacle is design validity; budget **2–3 days**
  of build + validation + a handful of measurement runs (B = 0 control,
  1× and amplified transverse B).

Falsification structure (from the identity): measure F_net/F_beam on the
control volume. ≈ 1 → L ≈ r_g, electrostatic results stand (retires the
largest unexamined risk); > 1.1 → upside real, re-open the mission table;
< 0.9 → field-aligned firing becomes a mission constraint and the M1 runs
above become the primary operating-mode evidence.

---

## Order of work

1. M1a + M1b (this plan; ~13 GPU-hours, machinery already committed).
2. M2 validation mini-ladder + similarity design (needs its own committed
   plan with numeric pre-registrations before any measurement run).
3. M2 measurement runs.
