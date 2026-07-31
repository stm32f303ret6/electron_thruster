# validation_cases: the verification ladder to the chipsat

Theory-anchored pre-simulations, in order of increasing physics, each gated
against closed-form references (executable gates: every `analyze_*.py` exits
0 only if all gates pass).  The ladder validates the CODE (WarpX RZ
electrostatics, EB, flux emission, scraping) and, deliberately, the
CONFIGURATION the final chipsat case will use -- grid resolution, plasma
row, ppc, emitted current, aperture geometry -- so that by the top rung
every numerical choice has already passed a gate somewhere cheaper.

```
electron_gun/                    EMITTER side (prescribed-current beams)
  1_negative_cathode             plane diode, no EB          (~3 min GPU)
  2_electron_gun                 + holed-anode plate (EB)    (~10 min GPU)
current_collection/              COLLECTOR side (ambient plasma)
  1_thermal                      sphere at 0 V, exact law    (~25-50 min GPU)
  2_biased_3v                    OML ceiling, chi = 26.4     (~1-2 h GPU)
  3_biased_10v                   sheath growth, chi = 88     (~2-4.5 h GPU)
(final) chipsat                  emitter + collector, floating body
```

## What each rung proves

| rung | new physics | analytic gate anchors | chipsat parameter validated |
|---|---|---|---|
| 1_negative_cathode | space-charge beam, flux emission | Laplace ramp (35 uV match), energy conservation 99.25 eV, 100% transmission, budget closure | prescribed-current z-normal flux emission (calibrates to ~1.0) |
| 2_electron_gun | embedded boundary, aperture interception | Child-Langmuir 507 uA scale, thermal-tail clip estimate, energy conservation through a holed plate | emit spot 0.5 mm + lid hole (the capstone's 0.8 -> 2.0 mm escape lever) |
| 1_thermal | ambient plasma, EB sphere, flux reservoir | I_th exact for any convex probe; species ratio 23.74 | plasma row, dx = 0.15 mm (13.1 cells/lambda_De), ppc = 16 |
| 2_biased_3v | attracting sheath | OML ceiling 2.847 uA (93% expected at a/lambda = 0.38) | biased-body collection physics |
| 3_biased_10v | thick sheath | OML ceiling 9.249 uA + containment | domain-sizing rule (sheath inside rmax) |

## Architecture (every case identical)

- `inputs/<case>.yaml` -- ALL parameters; no CLI arguments anywhere.
- `run_<case>.py` -- zero-argument PICMI deck; writes `outputs/diags/` and,
  only after a successful finish, copies the YAML to
  `outputs/diags/config_used.yaml` (snapshot + finished-run marker).
- `analyze_<case>.py` -- reads the SNAPSHOT (immune to later edits of
  `inputs/`), writes plots/CSV/JSON to `results/`, prints the gate table,
  exit 0/1.  Gate TOLERANCES are read from the current `inputs/` YAML:
  physics comes from the snapshot, gating policy is analysis-time.
- `animate_<case>.py` -- video to `results/`.
- current_collection cases share `cc_common.py`; electron_gun/2 runs its
  scenarios in separate WarpX processes (libwarpx cannot re-init).

## Ground rules

- Run ONE WarpX case at a time; every deck caps its AMReX GPU arena so it
  coexists with other GPU users.
- Delete `outputs/diags/` before rerunning a case (stale openPMD iterations
  mix).  electron_gun scenarios skip themselves if their snapshot exists.
- Gates compare fields AT SAMPLED CELL CENTRES (never nominal coordinates:
  a half-cell on a steep ramp dwarfs signal), gate stray currents as
  FRACTIONS of emitted (one tail macroparticle breaks an exact zero), and
  report SKIPPED gates in the verdict (a NaN must never look like a PASS).
