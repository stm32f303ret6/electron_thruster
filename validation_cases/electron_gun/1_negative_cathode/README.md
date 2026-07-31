# negative_cathode validation case

A two-plate axisymmetric (RZ) **plane diode**: a full-width **-100 V cathode**
on the left boundary (z = -2 mm) emits a prescribed **10 uA** electron beam
that flies rightward (+z) to a grounded **collector** (z = +2 mm).
Electrostatic PIC with self-consistent space charge; the emitted current is
prescribed (no thermionic/field-emission model).

The physics this case validates: when the emitting electrode is the device's
most negative potential, no interior trap can exist (Laplace puts the
potential minimum on an electrode), so the full current arrives at the
collector with KE = e*|v_cathode| ~ 100 eV.  At 10 uA the beam is ~9% of the
Child-Langmuir limit, so no virtual cathode forms.

Adapted from the `cathode` mode of `electron_two_plate/inputs_two_plate_rz.py`
with three simplifications: emission direction inverted (left -> right), the
two 5 uA species merged into one 10 uA species, and the measured RZ flux
calibration factor (1.00014 -- a 0.014% over-emission, below the run's own
statistical noise) dropped.

## Layout

```
electron_gun/1_negative_cathode/
├── inputs/negative_cathode.yaml   # ALL parameters (no CLI arguments anywhere)
├── run_negative_cathode.py        # WarpX PICMI deck -> outputs/diags/
├── analyze_negative_cathode.py    # plots/CSVs/summary -> results/
├── animate_negative_cathode.py    # density+KE video   -> results/
├── outputs/diags/                 # openPMD fields/particles/scrape, reducedfiles,
│                                  #   config_used.yaml (snapshot of the config the
│                                  #   run actually used; written on successful
│                                  #   finish -- analysis reads THIS copy)
└── results/                       # PNG/CSV/JSON/mp4
```

## Run

```bash
conda activate warpx-cpu-mpich-dev
python run_negative_cathode.py       # ~3 min (4000 steps, 40x80 grid)
python analyze_negative_cathode.py
python animate_negative_cathode.py
```

Edit `inputs/negative_cathode.yaml` to change anything.  Delete
`outputs/diags/` before rerunning -- stale openPMD iterations mix with new
ones.

## Validation gates (evaluated by `analyze_negative_cathode.py`, exit 0/1)

| gate | reference | tolerance |
|------|-----------|-----------|
| collector steady current   | emitted 10.0 uA (analytic: cathode is the global minimum, so 100% transmission) | 0.5% |
| collector mean arrival KE  | analytic `e*[phi(coll) - phi_ramp(emit_z)] + 2kT_launch` = 99.25 eV | 0.5 eV |
| cathode / radial-wall hits | fraction of emitted weight (never "exact 0": one thermal-tail macroparticle breaks that) | <= 1e-4 each |
| vacuum phi(t=0) on axis    | Laplace linear ramp evaluated **at the sampled cell centres** | 0.01 V |
| space-charge dip at z~0    | 0.092 V (**regression** value from the validated run; rough 1D estimate brackets 0.04-0.09 V) | 0.04 V |
| particle-budget closure    | emitted = absorbed + in-domain | <0.1% |

Two porting lessons baked into these gates:

1. The openPMD z-axis holds **cell centres**, so there is no sample at z = 0;
   the nearest is z = +-0.025 mm.  On the 25 V/mm background ramp that
   half-cell offset is worth 1.25 V -- 13x the space-charge signal.  The parent
   run (cathode at z_max) reads -50.7 V at its sampled point; this mirrored
   case reads **-49.4 V** at its own.  Both are the same physics: ramp at the
   sampled z minus the same 0.09 V beam depression.  Never gate on an absolute
   mid-gap potential whose reference came from a differently-oriented run;
   gate on the analytic ramp at the sampled z and on the vacuum-minus-beam
   difference instead.
2. The collector KE is below 100 eV for an analytic reason, not an error: the
   source plane sits one cell inside the gap, so electrons only fall through
   `phi(coll) - phi_ramp(z_min + dz)` = 98.75 V, plus the flux-weighted
   Maxwellian launch energy `2*kT_launch` ~ 0.5 eV -> 99.25 eV.

(The parent electron_two_plate reference run measured 9.9966 uA / 99.28 eV /
closure -0.01%; this case is its mirror with one merged species and no
calibration factor, so agreement is expected at the ~0.1% level, not bit-exact.)
