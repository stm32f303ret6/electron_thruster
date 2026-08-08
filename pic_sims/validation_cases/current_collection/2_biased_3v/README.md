# collector.biased_3v — sphere at +3 V

same sphere and plasma as `thermal`, biased to +3 V. an attracting sheath forms; electron current checked against the OML ceiling.

[![dashboard](viz/20260806T142605Z_1a87cbce_dashboard.gif)](viz/20260806T142605Z_1a87cbce_dashboard.mp4)

*animated dashboard — click for the full video.*

## setup

![schematic](viz/schematic_2_biased_3v.png)

- **sphere**: 0.75 mm radius (a/λ_De = 0.38), held at +3 V
- **plasma**: same as `thermal`
- **domain**: enlarged to 7.3 λ_De to hold the sheath

### OML theory

$$I_{OML} = I_{th}\,(1 + \chi), \qquad \chi = \frac{eV}{kT_e} = 26.4$$

$$I_{OML} = 0.10393\ \mu\mathrm{A} \times 27.40 = 2.847\ \mu\mathrm{A}$$

OML is a ceiling (mott-smith & langmuir 1926), attained as a/λ_De → 0. at finite radius the fraction falls below it (laframboise 1966). measured: 85% of ceiling. gate is [0.85, 1.05].

## how the pic works

same deck as `thermal` — only config differs (bias +3 V, larger domain, dt = 30 ps):

- bulk maxwellian fill at t = 0, flux injection from three open faces
- electrostatic poisson every step; +3 V sphere against 0 V walls
- EB collection + scrape buffer; last-40% steady window

## what this step tests

| check | target |
|---|---|
| electron current vs OML ceiling | [0.85, 1.05] of $I_{OML}$ |
| far-field density | ≤ 5% off n0 |
| quasineutrality | ≤ 2% |
| edge potential | ≤ 0.5 V |

## results

reference run `20260806T142605Z_1a87cbce`, all gates PASS:

| metric | measured | gate |
|---|---|---|
| I_e / I_OML | 0.852 | [0.85, 1.05] |
| far density vs n0 | 3.0% off | ≤ 5% |
| quasineutrality | 0.19% | ≤ 2% |
| edge potential | 2.5 mV | ≤ 0.5 V |

## dependencies

requires `collector.thermal`.

## cost

~1–2 h. 100k steps × 30 ps = 3.0 µs.

## commands

```bash
python simulation.py
python analyze.py --run outputs/<run-id> --policy acceptance.yaml
python animate.py --run outputs/<run-id>
```

## validates for capstone

OML electron collection at moderate bias — the capstone body floats positive and collects ambient electrons the same way.

## limitations

- OML is a ceiling, not an equality at this a/λ_De — the band is a sanity check
- ion current is start-up biased (reported, not gated)
- EB faceting, RZ flux quirk, t = 0 spike same as `thermal`
- single grid/PPC/seed (phase 5)
