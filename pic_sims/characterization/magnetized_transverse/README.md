# characterization.magnetized_transverse: B perpendicular to the thrust axis (tier M2)

The anchor's chipsat body (capstone.floating_body, 200 V, 0.342 mA) in a
Cartesian 3D electrostatic deck with a uniform external magnetic field
**perpendicular** to the thrust axis: the flight geometry on a near-equatorial
orbit, which the RZ decks cannot represent (a transverse B breaks
axisymmetry). Tier M2 of the magnetized axis. Tier M1 (field-aligned Bz on the
RZ deck, `../magnetized_1x/`, `../magnetized_10x/`) closed the near-field
half of the question in the fallback operating mode; this stage answers it in
the operating mode the mission actually flies.

Three scenarios, one axis: `b0_control` (B = 0, the 3D control),
`transverse_1x` (Bx = 30 µT, 1× LEO), `transverse_10x` (Bx = 300 µT).

Pre-registered 2026-09-01, before any run (plan section below). Results are
appended below the plan once the cohort has run.

## Plan (pre-registered 2026-09-01, before the run)

### Why this instrument, and not the far-field control volume

The design note that preceded this stage
([`../../../future_work/M2_TRANSVERSE_B.md`](../../../future_work/M2_TRANSVERSE_B.md))
proposed a metre-scale similarity deck with a sub-cell craft and a momentum
ledger over a control volume of size L, reading its identity
`F_Lorentz/F_beam = L/r_g` as "the open quantity is L". That instrument was
not built, for a reason that is exact rather than practical:

Momentum conservation for the particles inside any box around the craft, in
steady state, reads

```
0 = (momentum injected at the source) + (force of the craft's field on the particles)
    + Σ q v × B  − (net momentum flux out through the faces) − (momentum absorbed by the craft)
```

and the force on the craft is the emission recoil plus the impacts plus the
reaction of its own field, so

```
F_craft = −(net momentum flux out) + Σ_particles q v × B        (over the box)
```

The term `Σ q v × B` is the **external** field's force on the beam and plasma
inside the box. It is Earth's field pushing electrons, its reaction is on the
source of B, and it grows with the box by construction: the beam curls more
the longer it stays inside. A control-volume ledger that reads the flux
through a surface of size L therefore measures `L/r_g` because it includes
that term, not because the craft feels it. The craft feels three things only,
all of them sheath-scale: the recoil at emission, the momentum of what lands
on it, and the electrostatic stress of the sheath on its surface. Where the
beam's momentum ends up afterwards is Earth's business: the gyro-orbit returns
the electron to +z every `T_ce`, exchanging momentum with the geomagnetic
field, never with the craft.

Two direct estimates bound the ways the far field can still reach the craft:

1. Beam return. At 1× the orbit closes 1.44 m away and comes back after
   1.19 µs with the anchor's 2° divergence spread over the 9 m circumference,
   a ~0.3 m footprint against a 10 mm craft: a 10⁻⁴ fraction, and those
   electrons arrive at 147 eV against a 17 V float, so they are not
   collected unless they hit. At 10× the footprint is 3 cm and the return
   fraction ~10 %; that case needs a 0.3 m box and is outside this stage
   (limitations).
2. Craft-scale J×B. The collected current flows through the craft over its
   5.5 mm height: `I·L·B` = 0.342 mA × 5.5 mm × 30 µT = 0.06 nN, 0.4 % of
   F_beam at 1× (4 % at 10×).

So the measurement is: the anchor body, resolved, floating self-consistently
in the anchor plasma, with B ⊥ ẑ, and a thrust ledger that separates the
craft's force from the Lorentz term the exit flux alone would misread.

### The instrument (delta from the anchor deck)

| | RZ anchor (`capstone.floating_body`) | this deck |
|---|---|---|
| geometry | RZ, r ≤ 30 mm, z ∈ [−30, 36] mm | Cartesian 3D, x,y ∈ ±32 mm, z ∈ [−30, 42] mm (same margins, snapped to 8-cell blocks) |
| cells | 0.15 mm, 200 × 440 = 88 k | 1.0 mm, 64 × 64 × 72 = 295 k (λ_D/dx = 1.97 vs 13.1) |
| body | can with 0.4 mm walls, lid hole, internal gun (two EB nodes) | the same Ø10 × 5.5 mm can, **solid**, one EB node |
| beam | thermionic-like source at the cathode, accelerated through the 4.7 mm gap | the escaped exhaust, prescribed on the lid: 0.342 mA at KE_lid = 164.5 eV (= anchor exhaust 147.5 eV + anchor float 17.0 V), r < 1.5 mm, anchor thermal spread |
| plasma, reservoir, schedule | n₀ = 1.627 × 10¹² m⁻³, kTe = 113.6 meV, mᵢ = 400 mₑ, 16 ppc; recycle shell; gun on 150 ns, end 800 ns | identical |
| external field | Bz (M1 only) | Bx = 0 / 30 µT / 300 µT |
| thrust ledger | F_beam = escaped-beam z-momentum flux; F_net = impacts | the same two, plus `F_lorentz` = Σ q v×B over every in-box particle (GPU sum each step), and `F_thrust = F_beam − F_lorentz,z`, the force on the body by momentum conservation |
| capacitance | Gauss law on the domain faces at the 1 V init solve: 0.645 pF | the same measurement on six faces (gated 0.35–1.20 pF) |

The gun is not re-modelled: the anchor measured it (κ = 0.81, 98.4 % escape).
Injecting the exhaust at the lid energy lets the sheath return
KE_∞ = KE_lid − φ self-consistently, which is how the control closes on the
anchor.

What 1 mm cells do and do not resolve: the sheath (tens of mm at 17 V, OML
capture radius 61 mm) is resolved; the body is 10 cells across; the gun is
not resolved and is not present. The Debye length is resolved at 2 cells
with the energy-conserving gather the anchor also uses.

### The validation mini-ladder

`../transverse_b_numerics/` (run first): single test electrons on this exact
grid and time step against closed forms: the gyration at 1× and 10×
(frequency to 0.2 %, radius to 0.5 %, energy to 10⁻⁶) and the E×B drift at
10× (to 1 %). The third rung of the design note's ladder is this stage's own
`b0_control`: the 3D coarse-grid solid-body deck must close on the fine RZ
anchor.

### Pre-registered predictions

`b0_control` (closure on the anchor: 16.98 V, 13.65 nN, 98.44 %, 147.5 eV):

- φ = 17 ± 4 V. The 1 mm grid, the solid body (4 % more collecting area than
  the holed can) and the snapped box (+2 mm in x,y, +6 mm in z) each move
  the float by ~1 V.
- F_beam = 13.65 ± 1.0 nN; F_lorentz = 0 to the ledger's noise (< 0.1 %).
- escape ≥ 99 % (the source sits outside the body; nothing to scrape but
  grazing lid hits); F_net/F_beam ≤ 0.02.
- C_float = 0.65 ± 0.3 pF.

`transverse_1x` (H-M2-null, the M1 bounds re-used): |Δφ| ≤ 2 V,
|ΔF_thrust|/F ≤ 5 %, |Δescape| ≤ 1 pp, Lorentz correction < 0.2 %. Grounds:
the beam deflects 0.6 mm over the 40 mm to the +z face (r_g = 1.44 m); the
thermal-electron gyroradius (27 mm) is the box size, so collection is
unmagnetized at the body scale; the Parker–Murphy ceiling (0.96 m) is far
above the OML capture radius (61 mm).

`transverse_10x` (H-M2-tax): Δφ = +20 to +60 V (φ ≈ 37–77 V),
ΔF_thrust = −5 to −25 % through the float (KE_∞ = KE_lid − φ), Lorentz
correction +2 to +8 %, escape ≥ 95 %. Grounds: the field-aligned M1 run
measured +33 V at 10×; here the collecting flux tube along ±x meets the
body's side profile (2 × 10 × 5.5 mm² plus the 2.7 mm gyro-broadening,
≈ 170 mm²) instead of its end faces (≈ 190 mm²), so the tax should be
comparable or somewhat larger; the beam deflects 18° before the +z face
(cos 18° = 0.95), which is what the exit flux misses and the Lorentz term
restores.

### Falsification

- `transverse_1x` outside the null bands: transverse firing changes the
  committed operating point at flight field. The mission table is re-opened
  and the M1 field-aligned mode becomes the primary evidence.
- `transverse_10x` with φ above 150 V for 50 ns: the run aborts as FAILED
  (choke). Transverse firing at 10× is infeasible for this body; that is a
  result, recorded as such.
- Lorentz correction outside its band in either magnetized run, or non-zero
  in the control: the ledger or the deck is wrong, not the physics; the stage
  is invalid until the numerics are fixed.

### What this stage cannot decide

- The 10× beam return (needs a ≥ 0.3 m box at this resolution).
- Electromagnetic coupling (Alfvén wings): outside an electrostatic model.
- Domain truncation (±32 mm against a 61 mm capture radius) is inherited
  from the anchor, deliberately, so the comparison is like for like.
- One grid, one ppc, one seed, 800 ns (a snapshot on the ion clock), as
  every committed run.

## Results

Pending: the cohort runs after the numerics mini-ladder (2026-09-01).

## Dependencies

Requires `capstone.floating_body` (the anchor). Run
`characterization.transverse_b_numerics` first; its PASS is the numerics
warrant for this stage.

## Cost

Measured on the reference GPU (RTX 3060): a 3D electrostatic benchmark at
this size steps at ~0.05 s bare; with the per-step observer the deck is
budgeted at ~1 h per scenario (21 780 steps at 36.7 ps), ~3 GPU-h for the
cohort. Field dumps ~20 × 19 MB per run; scrape dumps ~0.5 GB per run.

## Commands

```bash
python simulation.py --scenario b0_control        # then transverse_1x, transverse_10x
python analyze.py --runs outputs/<b0> outputs/<1x> outputs/<10x> --policy acceptance.yaml
bash campaign.sh                                   # the whole chain, sequential, logs under logs/
```

## Limitations

- 1 mm cells: the sheath is resolved, the gun is not (and is not modelled);
  the source energy is the anchor's measurement, so any error in the anchor's
  exhaust energy is inherited, not re-measured.
- The ambient species' momentum flux through the faces is not in the ledger
  (the anchor omits it too; the ambient pressure is 0.05 nN per face).
- Beam macroparticles are born 2 cells above the lid and see the sheath from
  there; `ke_predicted_eV` reports what the sheath returns from that plane.
