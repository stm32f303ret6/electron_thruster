# collector.biased_10v — sphere at +10 V (χ = eV/kTe = 88.0)

A strong attracting bias, and the **sheath-containment stressor** of the
collector branch. Read this one folder and you have the whole model.

## Physical system

The 0.75 mm sphere is held at **+10 V** in the chipsat capstone plasma:

```
I_OML = I_th · (1 + χ) = 0.10393 µA · 89.0 = 9.249 µA
```

The demonstration here is **sheath growth**: the perturbed region expands to
several Debye lengths (watch `sheath.png`), and the collected current sits
**below** the +3 V case's fraction of the OML ceiling — barrier deepening grows
with χ (the contactor study saw the OML fraction fall from 38%→16% as 10 V→100 V
at a fat probe). The domain is the **largest of the three** (11 λ_De) because a
sheath clipped by the boundary fakes extra current.

### Physics / boundary conditions

Same as `collector.biased_3v` (two-species RZ electrostatics, EB probe, flux
reservoir) with the probe at +10 V and a larger domain.

## What this stage proves / does not prove

**Proves** (`evidence_kind: numerical_sanity`): the electron current stays within
`[0.80, 1.05]` of the OML ceiling (floor relaxed vs +3 V for the deeper barrier),
the flux reservoir stays intact, and — the gate to watch — the **thick sheath is
contained** inside the domain (`edge_phi_max_V ≤ 0.5 V`).

**Does not prove**: a quantitative sheath-collection law, ion physics (repelled),
or grid/domain convergence. In particular the containment gate here uses the max
|φ| a few cells inside the boundary; a **connected-sheath-edge + clearance**
containment metric is a Phase 5 refinement (plan C5/§10.5).

## Upstream dependencies

Requires **`collector.biased_3v`** (this stage deepens the bias and enlarges the
domain).

## Run cost

~2–4.5 h on an RTX 3060 GPU (150000 steps × 20 ps = 3.0 µs). The heaviest rung;
infeasible on CPU.

## Commands

```bash
conda activate warpx-cpu-mpich-dev
python simulation.py
python analyze.py --run outputs/<run-id> --policy acceptance.yaml
python animate.py --run outputs/<run-id>               # optional
PYTHONNOUSERSITE=1 python -m pytest tests/ -q
```

## Gate definitions and tolerance rationale

`acceptance.yaml` (`policy_id: collector.biased_10v.v1`):

| Gate (metric) | Bound | Rationale |
|---|---|---|
| `electron_current_over_oml` | [0.80, 1.05] | deeper barrier than +3 V → wider floor |
| `far_density_e_over_n0` | \|·−1\| ≤ 0.06 | flux reservoir; looser at this domain size |
| `quasineutrality` | ≤ 0.02 | far-shell \|n_e−n_i\|/n0 |
| `edge_phi_max_V` | ≤ 0.5 V | **THE gate to watch** — thick sheath containment |

Changing any tolerance requires a new `policy_id`; every verdict records this
file's SHA-256.

## Known numerical limitations

- The **+4% drift** the current shows through its declared steady window is not
  yet gated by a stationarity check — that (plan C6) and a connected-sheath-edge
  containment metric (plan §10.5) are Phase 5 corrections.
- OML is only a **ceiling**; the band is a numerical-sanity check.
- EB faceting, RZ radial-face flux quirk, t = 0 spike as in the other collector
  rungs; single grid/PPC/seed (Phase 5).

The machine-readable record is `results/<run-id>/<analysis-id>/metrics.json` +
`verdict.json`.
