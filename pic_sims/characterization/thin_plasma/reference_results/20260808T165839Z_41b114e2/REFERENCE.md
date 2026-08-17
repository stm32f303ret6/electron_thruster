# reference results — characterization.thin_plasma (density axis, n0/3)

`20260808T165839Z_41b114e2/` is the curated snapshot of the **thin-plasma
run**: the 200 V anchor deck with `plasma.n0 → n0/3` (5.4233×10¹¹ m⁻³) and the
two disclosed numerics changes (rmax 30→40 mm containment, larger GPU arena) —
full production run (159,160 steps, 800 ns), GPU build, **PASS — all 6
required gates** under policy `capstone.exploratory_axes.v1`.

## The pre-registered question, and what the run did and did not answer

`THIN_PLASMA_PLAN.md` (2026-08-06) recorded per-α float predictions before
any launch: α = 1 → 53.4 V, 0.893 → 60.9 V, 0.82 → 68.0 V, 0.5 → 160.4 V.
The plan's amendment then unchained the run by scope decision (the n-linear
term was already validated ±1 % at `collector.thermal`; the settle limit
would blur a 53–68 V discrimination), reframing it as a **gross-breakdown
detector**. It was launched in that role on 2026-08-08.

| metric | value |
|---|---|
| escape fraction | 98.39 % |
| F_beam | 13.04 nN |
| φ_body (tail mean) | 29.47 V — **unsettled**, still climbing at 800 ns |
| φ_settled hard bound | **> 31.6 V** |
| exhaust KE (mean) | 135.1 eV (predicted from KE = κ(V − φ): 135.6 eV) |

**Answered:** the device is healthy at n0/3 — beam formation, containment,
and the current-balance/ledger trust gates all hold; no gross breakdown of
the collection law. **Not answered:** the α discrimination — the float is
unsettled, so 29.47 V is a lower-bound trajectory point, not a settled
measurement against the 53–68 V predictions.

## Provenance

Executed as a variant deck through the anchor stage (then
`capstone/2_chipsat_thruster`) before this folder existed; the frozen
`config_used.yaml` and `run_manifests.json` here carry
`stage_id: capstone.floating_body` and the exploratory policy id — the honest
record of how it ran. Files: `metrics.json`, `verdict.json`,
`acceptance_used.yaml` (analysis `20260809T012347Z_aae666a6`), figures, frozen
config, run manifest. Recorded in commit `b1232e9`.
