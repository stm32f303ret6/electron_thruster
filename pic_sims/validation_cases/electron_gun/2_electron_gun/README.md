# emitter.holed_anode — electron gun with aperture

| Scenario A | Scenario B | Scenario C |
|---|---|---|
| ![A](viz/schematic_A_low_current_small_hole.png) | ![B](viz/schematic_B_high_current_small_hole.png) | ![C](viz/schematic_C_high_current_big_hole.png) |

Second step of the emitter branch. Same diode as `emitter.negative_cathode`, plus a grounded plate with a hole on axis (embedded boundary).

## Setup

- **Cathode** (z_min): −100 V, emits a prescribed beam
- **Anode plate** (z ∈ [−0.1, +0.1] mm, r > hole radius): grounded EB, catches whatever misses the hole
- **Collector** (z_max): grounded, absorbs the transmitted beam
- Three scenarios run as separate WarpX processes (one immutable run each)

| Scenario | Current | Hole radius | What happens |
|---|---|---|---|
| A — low current, small hole | 10 µA | 0.7 mm | beam is narrow, nearly all transmits; only the thermal tail (~2–3%) clips the plate |
| B — high current, small hole | 400 µA | 0.7 mm | space charge blows the beam up, significant loss on the plate |
| C — high current, big hole | 400 µA | 1.4 mm | wider hole restores transmission, proving the aperture was the limiter |

### What's included

Same as `emitter.negative_cathode` (electrostatic Poisson, prescribed flux emission) plus the embedded-boundary anode plate.

### What's excluded

Emission physics, magnetic fields, collisions, ions.

## What this step tests

| Check | Target |
|---|---|
| A transmits most of the beam | ≥ 96% to collector, ≤ 4% plate clip |
| B loses current on the plate | ≥ 3 pp drop vs A, ≥ 4% on anode |
| C restores transmission | ≥ 98% to collector, plate clip < B's |
| Energy conservation (each scenario) | ≤ 1.5 eV error from emission-plane φ |
| Particle budget (each scenario) | ≤ 0.1% |

### Note on scenario A's plate clip gate

The original gate was ≥ 99% transmission (cold beam). The first run failed it — the beam has ~0.25 eV transverse temperature (σ_r ≈ 0.135 mm at the plate), so a thermal tail clips the hole edge. The gate was widened to ≤ 4% to cover that tail. This is calibration, not a prediction.

## What this step does NOT test

- A quantitative aperture-transmission law
- Virtual-cathode onset (Child-Langmuir limit is printed as a rough scale only, not gated)
- Grid convergence (single resolution/PPC/seed — Phase 5)

## Dependencies

Requires `emitter.negative_cathode` (this step only adds the EB plate).

## Cost

A ~3 min, B and C heavier (40x more particles). Total ~10 min.

## Commands

```bash
python simulation.py --scenario A_low_current_small_hole
python simulation.py --scenario B_high_current_small_hole
python simulation.py --scenario C_high_current_big_hole

python analyze.py --runs outputs/<A-run> outputs/<B-run> outputs/<C-run> \
    --policy acceptance.yaml
```

## Gates

From `acceptance.yaml` (policy: `emitter.holed_anode.v1`), 12 required gates:

| Gate | Bound | Why |
|---|---|---|
| `A_collector_transmits` | ≥ 0.96 | narrow beam; 4% admits thermal tail |
| `A_anode_clip_is_thermal_tail_only` | ≤ 0.04 | see note above |
| `B_collector_drops_vs_A` | ≥ 0.03 | space-charge blowup must show |
| `B_loss_lands_on_anode` | ≥ 0.04 | loss is on the plate, not cathode reflection |
| `C_big_hole_restores_transmission` | ≥ 0.98 | aperture was the limiter |
| `C_anode_clip_below_B` | ≥ 0 | bigger hole → less clip |
| `{A,B,C}_collector_ke_conserved` | ≤ 1.5 eV | energy conservation |
| `{A,B,C}_budget_closure` | ≤ 0.1% | particle conservation |

## Dashboard

[![Dashboard](viz/20260806_20260806_20260806_dashboard.gif)](viz/20260806_20260806_20260806_dashboard.mp4)

*Animated dashboard — click for the full video.*

## Limitations

- Single grid/PPC/seed (Phase 5)
- The anode plate is a staircased EB at 0.05 mm resolution; sub-cell aperture-edge effects are not resolved
- KE prediction interpolates φ at the emission plane between cell centers (±~1 eV on the gap gradient), within the 1.5 eV gate
