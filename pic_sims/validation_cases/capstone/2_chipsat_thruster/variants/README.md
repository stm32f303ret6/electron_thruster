# Variant decks — deck → run mapping

Variants run through this stage's `simulation.py` under the exploratory policy
`capstone.exploratory_axes.v1`. Run directories are named
`<timestamp>_<config-hash>`; this table is the lookup. Full campaign context:
`../../README.md` (capstone index).

| deck | axis | run id (under `../outputs`, `../results`) | verdict |
|---|---|---|---|
| *(pre-`variants/`; frozen `config_used.yaml` only)* | slender body, L/r = 6 | `20260806T011847Z_5670e54c` | PASS 2026-08-06, promoted to `../reference_results/` |
| `thin_plasma.yaml` | density, n0/3 | `20260808T165839Z_41b114e2` | PASS 2026-08-09 |
| `m1a_bz_1x.yaml` | Bz 30 µT (1× LEO) | `20260810T064845Z_5e785001` | PASS 2026-08-10 (null) |
| `m1b_bz_10x.yaml` | Bz 300 µT (10×) | `20260810T131955Z_0b81e70a` | PASS 2026-08-10 (collection tax) |

Superseded (no gated result): `../outputs/20260808T130303Z_5e785001`,
`../outputs/20260808T130307Z_0b81e70a` — earlier launches of the M1 decks.
