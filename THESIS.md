# THESIS

The claim stated for a physics reviewer — with the agreed wording guardrails
and the anticipated objections answered from measured, committed evidence.

---

## The claim

> Drag compensation for small spacecraft at 450–600 km requires continuous
> thrust in the nanonewton range — a few nN for the centimetre-class bodies
> measured here, a few hundred nN for a CubeSat flying end-on. No flight
> propulsion system can supply it: the smallest controllable flight EP
> (precision electrosprays/FEEP, ~5–30 µN) sits orders of magnitude above the
> demand, in kilogram-scale packages that claim a large share of a CubeSat's
> mass budget. This device fills that slot with ion-thruster-class energy
> conversion (~73 %), zero propellant and zero net mass flux, at 10–100 mW
> for the measured Ø10 mm anchor and 0.9–3.4 W for a 3U CubeSat — a demand
> modest enough for body-mounted power — using no tank, no feed system, no
> discharge chamber, and no neutralizer, because the ionosphere is the
> propellant reservoir and the spacecraft surface is the return electrode.
> The measured size-cancellation result makes the feasibility condition
> scale-free: a kilogram-class CubeSat in end-on flight inherits the mission
> corridor unchanged. Its thrust-per-watt is ~200× below an ion thruster's,
> which is precisely why it only owns the nN regime — and why nothing else
> does.

### Wording guardrails (agreed, do not regress)

- **Energy efficiency, not thrust-per-watt.** η ≈ 0.73 is jet-power /
  electrical-power. F/P is ~0.2 µN/W, ~200× below gridded ion. Never let the
  README imply parity on F/P; state both numbers side by side.
- **"Continuous" means no total-impulse limit, argued via the system floor,
  not propellant mass.** At nN scale, 5 years of thrust is ~5 N·s ≈ 0.3 g of
  electrospray propellant — propellant *mass* is not the argument. The argument
  is the dry-system floor: tank + feed + valves + PPU is ~0.3–1 kg — a
  substantial fraction of a kilogram-class CubeSat before the first
  newton-second; this concept's floor is a cathode, a boost converter,
  and the spacecraft skin.
- **The nuance on "no ion thruster goes that low":** gridded ion/Hall bottom
  out ~mN; LISA-Pathfinder-class colloids/FEEP reach 5–30 µN with ~0.1 µN
  resolution — still orders of magnitude above the nN-class demand of the
  measured bodies and well above an end-on CubeSat's few-hundred-nN demand,
  in kg-class packages. State it that way so the claim is armored.
- **The efficiency-indifference boundary is real and must be stated:** the
  F/P penalty is invisible at nN (mW), noticeable at µN (~10 W for CubeSat
  drag — disqualifying), decisive at mN. The handoff — electron thruster below
  ~0.1 µN, electrospray at µN, ion/Hall at mN — is part of the claim, not a
  concession.
- **Altitude honesty:** at 400 km / solar max the demand leaves the tested
  envelope — the axial pose needs ~304 V (above the 300 V ceiling) at
  ~120–200 mW mean, and the lateral pose fits the envelope only with a
  redesign of the thrust axis. The unconditional claim lives at ~450–600 km;
  400 km is a design target (higher voltage, emitter placement, slender or
  plate geometry). Supplying the power is mission design, not part of the
  device claim.

## Anticipated reviewer objections (with measured answers)

### "Collected ambient electrons deposit momentum that cancels the gun's thrust."

Raised by an external reader 2026-08-05, before submission. The quantity is
*measured*, not argued: the per-step ledger separates `F_beam` (reaction
thrust of the escaping beam) from `F_net` (z-momentum deposited by ALL
species landing on the craft — collected ambient e⁻, ambient ions, returning
beam). 300 V run `20260804T154756Z_b854dcbe`, steady tail:

- F_beam = 30.2 nN, all-impact F_net = 0.3 nN → **a 1 % correction**, bounded
  by the required pre-registered gate `momentum_sanity_bound`
  (|F_net|/|F_beam| ≤ 1, measured 0.0098); ledger cross-checked against
  independent openPMD particle dumps at the 1e-9 level.
- Physics ceiling even *without* isotropy: at current balance the collected
  current equals the escaping current, but arrivals carry ~eφ ≈ 36 eV vs
  210 eV exhaust → per-electron momentum ratio √(36/210) ≈ 0.41. Cancellation
  cannot exceed ~41 % even if every collected electron arrived directly
  astern; isotropic arrival (the objection's own premise) takes it to the
  measured 1 %.
- Charging is emergent, not prescribed: φ_body floats (+36 V at 300 V drive),
  gated ≤ 50 V with a 100 V choke-abort; collection physics was validated on
  dedicated ladder steps (thermal → biased → floating) against OML/sheath
  theory before any thrust claim.
- Gaps that travel with this answer (disclose proactively): plasma at rest —
  no mesothermal ram (electron-influx anisotropy ~v_orb/v_th,e ≈ 5 %;
  ram-ion pressure belongs to the drag side of the budget); reduced ion mass
  (400 mₑ); 800 ns tail vs ion-timescale settling.
- Planned hardening: the **full-return null fixture** (zero escape must read
  zero net thrust) turns this objection into a figure — the falsification
  test of the momentum diagnostic itself.

### "An electrodynamic tether does the same thing far more efficiently."

Concede F/P at km scale — Lorentz force pays no exhaust-energy cost. The
claim breaks at the scales considered here: a centimetre-class body or a 3U
CubeSat vs a deployed, gravity-gradient
stabilized conductor 3–6 orders of magnitude longer than the spacecraft,
plus libration control, meteoroid survivability, and thrust constrained to
the IL×B direction. And a bare EDT's endpoints still require the same
electron collection/emission contactor physics this device *is*. The thesis
claims a no-deployables, no-propellant device at a scale where no tether
closes — the efficiency-indifference boundary (guardrail above) applies to
tethers exactly as it does to ion thrusters.
