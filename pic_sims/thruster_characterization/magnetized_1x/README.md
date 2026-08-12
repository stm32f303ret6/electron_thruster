# characterization.magnetized_1x — field-aligned B at 1× LEO

same system as the anchor with a uniform **axial magnetic field at flight strength**, Bz = 30 µT. tier M1a of `../MAGNETIZED_PLAN.md`, which pre-registered H-M1-null before the run: at 1× LEO field the anchor's operating point does not move outside its own bands.

## setup

| | anchor (floating_body) | this spoke |
|---|---|---|
| `plasma.Bz_T` | absent (unmagnetized) | **3.0e-5** |
| everything else | — | identical |

electron gyroradius at beam energy ≫ domain; at thermal energy the ambient electrons begin to feel the field. the axial (flight, field-aligned) orientation is deliberately the *gentle* one — the transverse case is tier M2, still open.

## how the pic works

same engine as the anchor — deck, charge pump, reservoir, observer identical (`../../ladder/capstone/2_chipsat_thruster/README.md`). the Boris pusher rotates in the prescribed uniform Bz; nothing else changes.

## results

reference run `20260810T064845Z_5e785001`, all 6 required gates PASS. under the exploratory policy φ and F **are** the measurement — reported, not gated:

| check | measured | target | type |
|---|---|---|---|
| escape fraction | 98.44% | ≥ 95% | required |
| current balance | 3.2% | ≤ 5% | required |
| net-force sanity | 0.005 | ≤ 1 | required |
| edge potential | 40 mV | ≤ 1 V | required |
| scrape ledger vs dumps | 2.1e-9 | ≤ 2% | required |
| beam-escape ledger vs dumps | 1.6e-9 | ≤ 2% | required |
| body float φ | **+17.22 V** (anchor: 16.98 V) | — | reported |
| beam thrust | **13.64 nN** (anchor: 13.65 nN) | — | reported |
| exhaust KE | **147.3 eV** (anchor: 147.5 eV) | — | reported |

**H-M1-null holds** — a genuine null at flight field strength: gun optics, containment, collection and the operating point are the anchor's (the informational float/thrust regression bands vs the anchor also pass). together with the 10× companion (`../magnetized_10x/`) this closes the near-field, field-aligned half of the magnetized question. full detail: `reference_results/20260810T064845Z_5e785001/REFERENCE.md`.

![body potential vs time](reference_results/20260810T064845Z_5e785001/figures/phi_vs_time.png)

## provenance

executed 2026-08-10 as a variant deck through the anchor stage under the pre-registered exploratory policy `capstone.exploratory_axes.v1` (strictly sequential with M1b on one GPU, 12.8 h total); the frozen run config and manifests therefore carry `stage_id: capstone.floating_body`. this `config.yaml` is that same deck (git-moved, history intact) under the new stage id; `acceptance.yaml` re-identifies the same gates for future runs — it is not a pre-registration for the migrated evidence. launch record: `logs/`.

## dependencies

requires `capstone.floating_body` (the anchor). spokes never depend on each other.

## cost

~6.4 GPU-h. 159k steps, dt ≈ 5.0 ps, 200 × 440 grid. CUDA build required (`/SETUP.md`).

## commands

```bash
python simulation.py
python analyze.py --run outputs/<run-id> --policy acceptance.yaml
```

## limitations

- field-aligned geometry only — the transverse case (tier M2, beam gyroradius ~1.4 m vs the 30 mm domain) is the project's largest unexamined question (`/OPTIMISTIC_HYPOTHESES.md` H1)
- single field point at 1×; the axis is bracketed only by the 10× companion
- anchor limitations inherited: single grid/PPC/seed, reduced ion mass 400 mₑ
