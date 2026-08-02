# capstone.two_node_laplace — the capstone's two-node EB in vacuum

Closes **VALIDATION_GAPS.md G1** (the piecewise two-node embedded boundary had
no ladder rung beneath the capstone): the chipsat's conducting-can geometry,
solved in **vacuum** with both electrical nodes pinned — BODY at the
capstone's observed floating equilibrium (+16 V), CATHODE at
`phi_body + cathode_offset = −184 V` — through the **same piecewise potential
string and the same `set_potential_on_eb` per-step rewrite** the capstone's
charge pump uses.

## Physical system

The capstone's can (see `../2_chipsat_thruster/README.md` for the labelled
cross-section), on the capstone's exact grid (200×440, dx = 0.15 mm), with
zero particles and zero space charge.  Every solve is then **Laplace's
equation**, whose exact mathematical properties become gates.

## What this stage proves

- The piecewise EB Dirichlet mechanism imposes the assigned values on the
  right regions (a sign error, region misclassification, or body/cathode swap
  shifts a surface by up to 200 V — far outside the 1 V gate).
- The solved field is a genuine Laplace solution: the **maximum principle**
  holds (all vacuum potential within the boundary values — valid here,
  unlike the space-charge stages, because there is truly no charge).
- The solution matches an **independent stair-step RZ finite-difference
  solve** (scipy sparse direct factorization — different EB representation,
  different linear solver) away from the surface skin.
- Re-imposing the same potential string every step (the capstone's per-step
  pump mechanism) is **idempotent** — it cannot drift a static solution.

## What it does NOT prove

- Nothing about plasma, beam, scraping, or the charge pump's dQ accounting
  (that is `collector.floating` and the capstone itself).
- Cut-cell field accuracy *at* the surface beyond the 1 V surface-value gate
  (the independent solver is stair-step, so the comparison excludes the
  3-cell skin; the full-domain difference is reported, not gated).
- Time-dependent behaviour of `set_potential_on_eb` under a *changing*
  potential (the capstone rewrites with new values every step; here the
  values are static).

## Gates (`acceptance.yaml`, policy `capstone.two_node_laplace.v2`)

| gate (metric) | bound | observed (verified run) | provenance |
|---|---|---|---|
| `body_surface_potential_error_V` | ≤ 1.0 V | 0.22 V | assigned Dirichlet value (exact; 0.5 % of scale for cut cells) |
| `cathode_surface_potential_error_V` | ≤ 1.0 V | 0.0 V | assigned Dirichlet value |
| `laplace_bounds_violation_V` | ≤ 0.1 V | 0.0 V | maximum principle (exact) |
| `independent_solver_max_diff_V` | ≤ 4.0 V | 1.86 V | cathode-edge stair-step error ~ ΔV·(dx/2)/gap decaying ~ dx/d: ~2.5 V bound at ≥ 20 cells |
| `per_step_rewrite_drift_V` | ≤ 1 mV | 0.0 V | consecutive converged solves are bit-identical |

Reported, never gated: the full-domain solver difference (dominated by the
stair-step cathode-edge skin), the first solve's convergence settling
(~6.4 mV — the second solve polishes the tail of the first, which starts
from the uniform-1 V calibration guess), and the on-axis gap voltage.

**Calibration disclosure (plan §9.3):** the first run
(`20260801T225210Z_f44044c6`) was judged under policy v1, which gated the
solver comparison at ≥ 3 cells and defined rewrite drift as first-vs-last
dump; it FAILed both, exposing two methodology errors in the *analysis*
(the cathode-edge singularity dominates the stair-step reference within
~20 cells, and first-vs-last captures first-solve convergence, not rewrite
drift).  v2 fixed the methodology — no tolerance was loosened — and the
verified reference comes from a fresh run judged under v2.

## Dependencies and cost

No upstream dependencies (a leaf rung).  `capstone.floating_body` requires
this stage.  Cost: seconds — five Laplace solves on a 200×440 grid, no
particles.

## Commands

```bash
conda activate warpx-cpu-mpich-dev
python simulation.py                                      # -> outputs/<run-id>
python analyze.py --run outputs/<run-id> --policy acceptance.yaml
PYTHONNOUSERSITE=1 python -m pytest tests/ -q             # unit tests (no WarpX)
```

## Known numerical limitations

- The independent solver represents the EB as a stair-step node
  classification, so the WarpX-vs-reference comparison is only meaningful a
  few cells away from surfaces; agreement inside the skin is not evidence
  either way.
- The `emit_radius` config key is unused here (no beam) but kept so the
  geometry section hash-matches the capstone's exactly (the cross-stage check
  `two_node_matches_capstone_geometry` depends on it).
