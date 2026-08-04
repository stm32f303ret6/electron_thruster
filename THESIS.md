# THESIS

The repository currently proves physics but never states its thesis. The README
leads with architecture; the actual discovery — a propulsion regime nothing else
occupies — exists only in conversation.

---

## The claim

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
  plate geometry).
