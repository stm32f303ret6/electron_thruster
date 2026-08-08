# capstone.floating_body — the chipsat electron thruster

the full chipsat electron thruster in ambient plasma — the capstone the whole ladder builds to. emitter + collector in one self-consistent system: the body floats while the gun fires, and the thruster only works if it floats to a benign potential. thrust is gated directly.

[![dashboard](viz/20260806T011847Z_5670e54c_dashboard.gif)](viz/20260806T011847Z_5670e54c_dashboard.mp4)

*animated dashboard — click for the full video.*

## setup

![schematic](viz/schematic_2_chipsat_thruster.png)

- **can**: conducting body, floats electrically in ionospheric plasma
- **plasma**: n0 = 1.627e12 m⁻³, kTe = 113.6 meV, dx = 0.15 mm, ppc = 16
- **beam**: prescribed 0.342 mA, spot r < 0.5 mm, on at 150 ns
- **cathode**: 200 V below body, on at 100 ns
- **grid**: 200 × 440 cells

![equivalent circuit](viz/circuit_2_chipsat_thruster.png)

*the current loop: supply lifts electrons out of cathode → beam carries them to space → ionosphere returns them to the floating body.*

a **reservoir** re-injects every EB-collected ambient particle into the outer radial shell (r > 22.5 mm, every 25 steps).

![potential map](viz/potential_map_2_chipsat_thruster.png)

*self-consistent φ(r,z) from baseline run — shows: (1) φ decays to ≈0 inside domain (containment), (2) two-node pump applied correctly, (3) body floats benignly while 200 V drops inside the can.*

## how the pic works

- **plasma load + refill**: bulk maxwellian fill at t = 0, flux injection from open faces, reservoir re-injects EB-collected ambient particles into outer shell every 25 steps
- **beam emission**: prescribed 0.342 mA surface-flux source above cathode, on at 150 ns
- **field solve**: electrostatic poisson (multigrid) every step, two-node EB (BODY, CATHODE)
- **EB scraping**: per-step observer classifies scraped particles by electrode and species
- **charge pump**: C from uniform-1 V init solve; every step $dQ = e\,(\text{beam} + \text{escape}) - e\,(\text{amb}_\text{e}) + e\,(\text{amb}_\text{i})$ → $\varphi_{\text{body}} = \varphi_0 + Q/C$, CATHODE = body − 200 V via `set_potential_on_eb`
- **measurement**: F_beam = z-momentum of escaped beam; currents and fates logged to `contactor_log.csv` every 100 steps
- **watchdogs**: non-finite φ_body or φ_body > 100 V sustained 50 ns → FAILED

## what this step tests

| check | target | type |
|---|---|---|
| escape fraction | ≥ 95% (anchor 98.5%) | regression |
| beam thrust | 13.6 ± 2.04 nN | regression |
| body float | +16 ± 4 V | regression |
| current balance | ≤ 5% | theory |
| momentum sanity | \|F_net\| ≤ F_beam | theory |
| edge potential | ≤ 1 V | containment |
| scrape consistency (ambient) | ≤ 2% | ledger vs dump |
| scrape consistency (beam escape) | ≤ 2% | ledger vs dump |

regression anchors read from validated float200 run — disclosed calibration.

## results

reference run `20260801T142601Z_2f822a95`, all 8 gates PASS:

| metric | measured | anchor |
|---|---|---|
| escape | 98.44% | ~98.5% |
| thrust | 13.65 nN | 13.6 nN |
| φ_body | +16.98 V | +16 V |
| exhaust KE | 147.5 eV | ~146 eV |

## dependencies

`emitter.holed_anode` + `collector.biased_10v`. config hash-verified against `collector.thermal`.

## cost

~6 h. 159k steps, dt ≈ 5.0 ps, 200 × 440 grid, ~3 M macroparticles.

## commands

```bash
python simulation.py
python analyze.py --run outputs/<run-id> --policy acceptance.yaml
python animate.py --run outputs/<run-id>
```

## limitations

- 800 ns is finite-time equilibrium; ion-clock tail still moving
- ppc_beam = 16 (emitter steps validated at 128)
- single grid/PPC/seed; EB staircase at 0.15 mm; reduced ion mass 400 mₑ
