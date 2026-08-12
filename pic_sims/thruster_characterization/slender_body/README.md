# characterization.slender_body — the geometry axis

same drive and commanded current as the anchor, but the can lengthened from Ø10 × 5.5 mm to **Ø10 × 30.5 mm** (L/r = 6, total skin 3.17 → 11.0 cm²). asks: does collection scale with area (hypothesis A, φ ≈ 4–5 V) or does the elongated wall collect like an OML cylinder (hypothesis B, tens of volts)? pre-registered 2026-08-05 in `SLENDER_BODY_PLAN.md`, before the run.

## setup

| | anchor (floating_body) | this spoke |
|---|---|---|
| `z_bot` | −5.5 mm | **−30.0 mm** |
| `cathode_standoff` | floor-tied | **4.7 mm** |
| grid | 200 × 440 | **200 × 608** (~122k cells) |
| everything else | — | identical |

the standoff is the load-bearing fix: it pins the gun gap at its short design value while the body grows around it. the first attempt (2026-08-05) inherited the floor-tied cathode, stretched the gap to 29.7 mm, exceeded the Child–Langmuir ceiling ~60× and self-scraped; it was killed at 69%. design rule: *grow the body around the gun, never stretch the gun* (`CAMPAIGN.md` §4.1, §6.5).

## how the pic works

same engine as the anchor — deck, charge pump, reservoir, observer identical (`../../ladder/capstone/2_chipsat_thruster/README.md`). only the conductor geometry differs.

## results

reference run `20260806T011847Z_5670e54c`, all 6 required gates PASS. under the exploratory policy φ and F **are** the measurement — reported, not gated:

| check | measured | target | type |
|---|---|---|---|
| escape fraction | 98.42% | ≥ 95% | required |
| current balance | 2.0% | ≤ 5% | required |
| net-force sanity | 0.014 | ≤ 1 | required |
| edge potential | 21 mV | ≤ 1 V | required |
| scrape ledger vs dumps | 2.6e-10 | ≤ 2% | required |
| beam-escape ledger vs dumps | 7.5e-10 | ≤ 2% | required |
| body float φ | **+4.38 V** (tail mean) | — | reported |
| beam thrust | **14.22 nN** | — | reported |
| exhaust KE | **159.7 eV** (KE = κ(V − φ) predicts 160.5) | — | reported |

hypothesis A confirmed; B refuted by an order of magnitude. because KE = κ(V − φ), the lower float *returns* drive energy to the beam: the slender can out-thrusts the squat anchor (13.65 → 14.22 nN) at the same current and drag bill. settle caveat and full detail: `reference_results/20260806T011847Z_5670e54c/REFERENCE.md`.

![body potential vs time](reference_results/20260806T011847Z_5670e54c/figures/phi_vs_time.png)

## provenance

executed 2026-08-06 as a variant deck through the anchor stage under the pre-registered exploratory policy `capstone.exploratory_axes.v1`; the frozen run config and manifests therefore carry `stage_id: capstone.floating_body`. this folder's `config.yaml` reproduces that deck (verified against the frozen `config_used.yaml`) under the new stage id; `acceptance.yaml` re-identifies the same gates for future runs — it is not a pre-registration for the migrated evidence. launch record: `logs/`.

## dependencies

requires `capstone.floating_body` (the anchor). spokes never depend on each other.

## cost

~6.5 GPU-h. 159k steps, dt ≈ 5.0 ps, 200 × 608 grid. CUDA build required (`/SETUP.md`).

## commands

```bash
python simulation.py
python analyze.py --run outputs/<run-id> --policy acceptance.yaml
```

## limitations

- float still rising at 800 ns (tail slope ~0.004 V/ns) — settled value plausibly 5–6 V
- single geometry point (L/r = 6), no sweep
- anchor limitations inherited: single grid/PPC/seed, reduced ion mass 400 mₑ
