# current_collection validation cases

A conducting **sphere** (embedded boundary) at fixed bias in the ionospheric
plasma of the electron_contactor **chipsat capstone** (n0 = 1.627e12 m^-3,
Te = 1318.8 K -> kTe = 113.6 meV, Ti = 936.2 K, reduced ion mass 400 m_e).
The ambient plasma is maintained by one-sided Maxwellian **flux injection**
from the three open faces on top of a bulk fill at t = 0 (the legacy
run_probe.py recipe, ported into the YAML architecture; the legacy scripts
are deleted -- their 5 mm probe sat at a/lambda_De = 2.5, the regime where
OML *must not* hold, so they could not validate what these cases validate).

## Why these cases also validate the chipsat configuration

Every numerical choice the chipsat case rides on is used here unchanged and
gated against closed-form theory:

| chipsat parameter | value | gated here by |
|---|---|---|
| plasma n0/Te/Ti/mi | capstone PLASMA_MAX row | thermal-flux + OML currents |
| cell size dx | 0.15 mm = **13.1 cells/lambda_De** | far-field density gate (5%) |
| ppc | 16/species | shot noise inside the 5% current gate |
| flux-reservoir injection | same recipe | far-field density + quasineutrality |
| domain sizing vs sheath | rmax >> sheath | edge-|phi| containment gate |

The sphere radius 0.75 mm (5 cells) puts a/lambda_De = **0.382** -- the same
sub-Debye point where the electron_contactor OML study measured 93% of the
OML ceiling, giving a cross-code reference for the biased gates.

## The ladder

| case | bias | key theory | main gates |
|---|---|---|---|
| `1_thermal`   | 0 V  | I_th = n*e*<v>/4 * 4*pi*a^2, **exact for any convex probe** (no field -> straight orbits); I_th_e = 0.10393 uA, I_e/I_i = sqrt((mi/me)(Te/Ti)) = 23.74 | I_e 5%, I_i 10%, ratio 8%, density 5% |
| `2_biased_3v` | +3 V | OML ceiling I_th*(1+chi), chi = 26.4 -> 2.847 uA | I_e/I_OML in [0.85, 1.05] |
| `3_biased_10v`| +10 V| chi = 88.0 -> 9.249 uA; **sheath growth** demo | I_e/I_OML in [0.80, 1.05]; edge containment |

Cross-case expectations (checked by reading the three summaries together):
`I_e/I_pred` falls monotonically 0V -> 3V -> 10V (barrier deepening grows
with chi), and the sheath radius (|phi| = kTe/e surface) grows with bias.

## Ion-clock caveat (why ions are gated loosely or not at all)

Collected **electron** current equilibrates on the electron transit/plasma
clock (~0.06 us here); **ion** current and sheath structure on the ion clock
(sqrt(mi/me) = 20x slower).  At positive bias the ions should be Boltzmann-
suppressed to ~zero, but ions already inside the domain at t = 0 never had
to climb the barrier, so the measured trickle starts biased HIGH and decays
on the ion clock -- reported, never gated.  Attracted species converge fast;
repelled species are slow AND start high.

## Run order and cost (RTX 3060, rough)

```bash
conda activate warpx-cpu-mpich-dev
cd 1_thermal    && python run_1_thermal.py    && python analyze_1_thermal.py     # ~25-50 min
cd 2_biased_3v  && python run_2_biased_3v.py  && python analyze_2_biased_3v.py   # ~1-2 h
cd 3_biased_10v && python run_3_biased_10v.py && python analyze_3_biased_10v.py  # ~2-4.5 h
```

Run ONE case at a time (each caps its GPU arena at 2 GB, but they contend).
Delete `outputs/diags/` before rerunning a case -- stale openPMD iterations
mix with new ones.  There is no checkpointing: a killed run restarts from
zero (accepted for these <5 h cases).

## Known risks (documented up front)

- **RZ radial-face flux over-emission**: the r = rmax injection face has a
  known WarpX over-emission quirk (z-normal faces calibrate to ~1.0).  The
  far-field density gate is the arbiter: if it reads hot, calibrate the
  radial flux before trusting current gates.
- **EB faceting**: at 5 cells per sphere radius the staircased EB area sits
  ~1-2% below 4*pi*a^2 (the collection_toy convergence lesson); this bias is
  inside the 5% electron gate and pushes ratios slightly LOW, not high.
- **t = 0 spike**: bulk particles born inside the sphere are scraped in the
  first steps; the steady window (last 40%) excludes the transient.
