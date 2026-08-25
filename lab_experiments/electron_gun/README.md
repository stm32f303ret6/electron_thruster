# Electron gun lab experiment: a negative cathode as emitter and accelerator

Bench test of the electrode topology used by the thruster. A cathode at a net
negative potential emits electrons and pushes them away by electrostatic
repulsion onto a grounded collector. It is the hardware version of ladder
step 1, [`emitter.negative_cathode`](../../pic_sims/ladder/LADDER_SUMMARY.md)
(−100 V plane cathode, grounded collector, vacuum gap), run at −56 V in rough
vacuum on a table.

Result: chamber at 4–5 Pa, cathode at about −56 V, the grounded collector
draws a steady 87 mA. The only current path is electrons crossing the gap, so
a non-zero reading means the cathode is emitting and accelerating electrons
onto the collector.

## Principle and circuit

![Circuit diagram: filament cathode between −50 V and −62 V, grounded collector plate in series with an ammeter to earth](assets/diagram.png)

1. One filament terminal is at −50 V, the other at −62 V, both referenced to
   mains earth.
2. The 12 V across the filament heats it. It emits electrons thermionically
   [1–3].
3. The filament sits between −50 and −62 V with respect to earth (about −56 V
   at the midpoint). This negative bias pushes the emitted electrons toward
   the least negative surface in the chamber, the collector plate at 0 V.
4. Collected electrons return to earth through the ammeter, so the meter
   reads the current that crossed the gap. The collector stays at 0 V because
   it is earthed.

Supply wiring. Two transformer (linear) supplies with isolated floating
commons, one at −50 V and one at −12 V:

1. Tie the −50 V output to the common of the −12 V supply.
2. Tie the common of the −50 V supply to mains earth, the same earth the
   collector's ammeter returns to.
3. The filament terminals are now at −50 V and −62 V with respect to earth.

## Apparatus

| part | implementation |
|---|---|
| cathode | filament of a W5W automotive bulb (12 V, 5 W [8]), glass envelope removed to expose the filament to vacuum |
| collector | copper plate, 4 × 4 cm, 5 mm thick |
| cathode–collector mount | 3D-printed holder; the bulb base press-fits in, two bolts fasten it to the plate (STL: [`assets/w5w_holder.stl`](assets/w5w_holder.stl)) |
| vacuum pump | two-stage rotary-vane pump (HVAC-service type, rated 50 micron ≈ 6.7 Pa) [7] |
| vacuum chamber | thick-walled glass tumbler, inverted on an acrylic base plate (3 cm thick) with a rubber gasket |
| plumbing | pump connected directly to the base plate through a brass tee, no hoses, to minimise leak paths; a second tee carries a vent valve and the vacuum gauge |
| vacuum gauge | Testo 552i digital vacuum probe (Bluetooth, read on the Testo Smart app) |
| feedthroughs | four 1 mm wire electrodes passed through the acrylic base into the chamber |
| ammeter | UNI-T UT89X multimeter on the mA range, in series between collector and earth |
| supplies | two isolated transformer supplies (−50 V and −12 V), separate floating commons |

Thermionic emission is used here because it is the cheapest way to free
electrons from a metal at home. The thruster does not depend on a heated
emitter. The part of this experiment that carries over is the
acceleration-by-repulsion role of the negative cathode.

## Procedure

1. Pump down. The chamber reaches its base pressure of 4–5 Pa after about
   10 minutes (the gauge screenshot below reads 4.3 Pa).
2. Switch on both supplies. The filament heats and starts emitting.
3. Read the ammeter. The collector current rises to a steady 87 mA (the meter
   shows −087.0 mA; the sign is the probe orientation).

## Results: photos and video

Full bench: vacuum pump with the acrylic plate and glass chamber on top,
Testo gauge, supplies, and multimeter:

![Full setup: rotary-vane pump, acrylic plate with inverted glass tumbler chamber, transformer supplies, multimeter](assets/setup.png)

![Second view of the bench: pump, both multimeters, rectifier boards and transformer supplies](assets/setup2.png)

Cathode–collector assembly: the exposed W5W filament in its 3D-printed
holder, bolted to the copper collector plate (note the heat-tint rings on the
copper facing the filament):

<img src="assets/prototype.png" alt="W5W filament in a 3D-printed holder bolted to the 4x4 cm copper collector plate" width="480">

Base pressure, read on the Testo Smart app:

<img src="assets/vacuum.png" alt="Testo 552i reading 4.3 Pa" width="300">

Collector current. The ammeter settles at −087.0 mA once the filament is hot
([full video, 32 s, MP4](assets/current_measurement.mp4)):

<img src="assets/current_measurement_preview.gif" alt="Multimeter showing a steady collector current of 87.0 mA" width="300">

## What this shows

A single net-negative electrode emits electrons and accelerates them across a
gap onto a grounded collector, with the current returning through earth. This
is the configuration checked numerically in step 1 of the
[PIC validation ladder](../../pic_sims/ladder/LADDER_SUMMARY.md).

## What this does not show

1. 4–5 Pa is rough vacuum, not the high vacuum of the PIC decks. The electron
   mean free path at this pressure is about a millimetre, so the gap is
   collisional. Part of the 87 mA is probably gas amplification
   (electron-impact ionisation of the residual gas) rather than thermionic
   beam current [6]. The number is evidence that acceleration happens, not a
   space-charge-limited diode measurement [4, 5].
2. The test is qualitative. It checks "steady current present vs. absent",
   not an I–V curve against theory.
3. Control runs are still to do:
   - filament heated, bias removed (filament floating near 0 V): expect about
     0 collector current. Rules out leakage paths and shows the −56 V bias
     drives collection.
   - bias applied, filament cold: expect 0. Rules out field emission or
     breakdown as the source.
   - sweep the bias magnitude and record the I–V curve.

## Relation to the rest of the repository

This folder sits outside the `orbit_sims → pic_sims` data flow. It reads
nothing from and writes nothing into the other trees. Its only purpose is to
show the negative-cathode principle on real hardware built by this project.

## References

1. O. W. Richardson, "On the Negative Radiation from Hot Platinum," *Proc.
   Cambridge Philos. Soc.* **11**, 286–295 (1901).
2. S. Dushman, "Electron Emission from Metals as a Function of Temperature,"
   *Phys. Rev.* **21**, 623–636 (1923).
3. C. Herring and M. H. Nichols, "Thermionic Emission," *Rev. Mod. Phys.*
   **21**, 185–270 (1949).
4. C. D. Child, "Discharge from Hot CaO," *Phys. Rev. (Series I)* **32**,
   492–511 (1911).
5. I. Langmuir, "The Effect of Space Charge and Residual Gases on Thermionic
   Currents in High Vacuum," *Phys. Rev.* **2**, 450–486 (1913).
6. M. A. Lieberman and A. J. Lichtenberg, *Principles of Plasma Discharges
   and Materials Processing*, 2nd ed., Wiley (2005). Mean free path and
   electron-impact ionisation of low-pressure gases.
7. J. F. O'Hanlon, *A User's Guide to Vacuum Technology*, 3rd ed., Wiley
   (2003). Rotary-vane pumps and rough-vacuum practice.
8. UN ECE Regulation No. 37, specification of the W5W filament lamp
   (12 V, 5 W).
