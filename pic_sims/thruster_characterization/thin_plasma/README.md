# characterization.thin_plasma — the density axis (n0/3)

same system as the anchor in a **3× thinner ionosphere**. asks: do the collection law's fitted exponents (α, β) hold as r_probe/λ_D drops 2.5 → 1.5? pre-registered 2026-08-06 in `THIN_PLASMA_PLAN.md` with per-α float predictions (α = 1 → 53.4 V, 0.893 → 60.9 V, 0.82 → 68.0 V, 0.5 → 160.4 V), then **unchained before launch by scope decision** (the n-linear term was already validated ±1% at `collector.thermal`, and the settle limit would blur a 53–68 V discrimination); relaunched 2026-08-08 as a gross-breakdown detector.

## setup

| | anchor (floating_body) | this spoke |
|---|---|---|
| `plasma.n0` | 1.627e12 m⁻³ | **5.4233e11 m⁻³** (n0/3) |
| `rmax` | 30 mm | **40.8 mm** (containment for the √3× larger λ_D) |
| gpu arena | — | enlarged (disclosed numerics) |
| everything else | — | identical |

the deck as committed now carries the pre-registered **2.4 µs continuation** (`t_end` 800 ns → 2.4 µs, `max_steps` 480k, `phi_ceiling` 100 → 180 V — see `THIN_PLASMA_PLAN.md` §CONTINUATION; run `20260811T213635Z_acc8f8f9` in flight). the results below are the executed 800 ns reference.

## how the pic works

same engine as the anchor — deck, charge pump, reservoir, observer identical (`../../ladder/capstone/2_chipsat_thruster/README.md`). only the plasma density (and the containment radius it demands) differs. the `sheath_and_plume_contained` gate is what proves the rmax enlargement sufficed.

## results

reference run `20260808T165839Z_41b114e2`, all 6 required gates PASS. under the exploratory policy φ and F **are** the measurement — reported, not gated:

| check | measured | target | type |
|---|---|---|---|
| escape fraction | 98.39% | ≥ 95% | required |
| current balance | 4.9% | ≤ 5% | required |
| net-force sanity | 0.026 | ≤ 1 | required |
| edge potential | 103 mV | ≤ 1 V | required |
| scrape ledger vs dumps | 3.9e-9 | ≤ 2% | required |
| beam-escape ledger vs dumps | 5.1e-10 | ≤ 2% | required |
| body float φ | **+29.47 V** (tail mean, **unsettled**) | — | reported |
| beam thrust | **13.04 nN** | — | reported |
| exhaust KE | **135.1 eV** (KE = κ(V − φ) predicts 135.6) | — | reported |

device **healthy at n0/3**: no gross breakdown of the collection law. the float is unsettled at 800 ns (run-end above the tail mean), so the α discrimination was **not achieved**; the recorded hard bound is **φ_settled > 31.6 V**. the in-flight 2.4 µs continuation exists to close exactly this gap. full detail: `reference_results/20260808T165839Z_41b114e2/REFERENCE.md`.

![body potential vs time](reference_results/20260808T165839Z_41b114e2/figures/phi_vs_time.png)

## provenance

executed 2026-08-08 as a variant deck through the anchor stage under the pre-registered exploratory policy `capstone.exploratory_axes.v1`; the frozen run config and manifests therefore carry `stage_id: capstone.floating_body`. this `config.yaml` is that same deck (git-moved, history intact) under the new stage id; `acceptance.yaml` re-identifies the same gates for future runs — it is not a pre-registration for the migrated evidence. launch record: `logs/`.

## dependencies

requires `capstone.floating_body` (the anchor). spokes never depend on each other.

## cost

~8.4 GPU-h for the 800 ns reference (159k steps, enlarged domain); the 2.4 µs continuation is ~3× that. CUDA build required (`/SETUP.md`).

## commands

```bash
python simulation.py
python analyze.py --run outputs/<run-id> --policy acceptance.yaml
```

## limitations

- float unsettled at 800 ns — only a hard lower bound on φ_settled; α not discriminated (continuation in flight)
- single density point (n0/3), no sweep down to CubeSat-regime r/λ_D
- anchor limitations inherited: single grid/PPC/seed, reduced ion mass 400 mₑ
