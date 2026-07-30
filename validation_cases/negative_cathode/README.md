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
negative_cathode/
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

## Expected numbers (from the electron_two_plate reference run, mirrored)

| quantity                   | expected  | tolerance |
|----------------------------|-----------|-----------|
| collector steady current   | ~10.0 uA (~100% of emitted) | ~0.1% |
| collector mean arrival KE  | ~99.3 eV  | ~0.5 eV |
| cathode / radial-wall hits | 0         | exact |
| on-axis phi(z~0) at t_end  | ~+50.7 V shifted, i.e. ~-50.7 V | ~1 V |
| particle-budget closure    | 0         | <0.1% |

(The reference run emitted right -> left with two 5 uA species and the
calibration factor on; this case is its mirror with one species and no
factor, so agreement is expected at the ~0.1% level, not bit-exact.)
