# reference results — characterization.magnetized_10x (tier M1b, Bz = 300 µT)

`20260810T131955Z_0b81e70a/` is the curated snapshot of the **10× LEO
field-aligned magnetized run**: the 200 V anchor deck with exactly one change,
`plasma.Bz_T: 3.0e-4` — full production run (159,160 steps, 800 ns), GPU
build, **PASS — all 6 required gates** under policy
`capstone.exploratory_axes.v1`.

## The pre-registered hypothesis, and the answer

`MAGNETIZED_PLAN.md` recorded H-M1-tax before the run: overdriving the axial
field to 10× LEO locates the mechanism that eventually bites.

| metric | this run | unmagnetized anchor |
|---|---|---|
| φ_body (tail mean) | 48.63 V (**still climbing at 800 ns** — disclosed caveat) | 16.98 V |
| F_beam | 12.06 nN (−11 %) | 13.65 nN |
| escape fraction | 98.32 % | 98.44 % |
| exhaust KE (mean) | 115.9 eV (predicted from KE = κ(V − φ): 116.5 eV) | 147.5 eV |

**H-M1-tax confirmed, entirely through the float**: beam formation is
unharmed (escape essentially unchanged), but the magnetized skin collects
less effectively, the float rises ~+33 V, and the thrust loss follows
KE = κ(V − φ) exactly. The tax is a *collection* effect, not a gun effect.
The caveat travels with the number: the 10× float had not settled at 800 ns,
so +33 V is a lower bound on the settled tax at this field.

## Provenance

Executed 2026-08-10 as variant deck `m1b_bz_10x.yaml` through the anchor stage
via `m1_chain.sh` (strictly sequential after M1a on one GPU, 12.8 h total);
frozen config and manifest here carry `stage_id: capstone.floating_body` and
the exploratory policy id. `outputs/20260808T130307Z_0b81e70a` is an earlier
launch of the same deck with no gated result (superseded). Files:
`metrics.json`, `verdict.json`, `acceptance_used.yaml` (analysis
`20260810T193704Z_aae666a6`), figures, frozen config, run manifest. Recorded
in commit `0d12463`.
