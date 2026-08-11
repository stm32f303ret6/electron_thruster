# reference result — capstone.two_node_laplace

Curated snapshot of a verified run+analysis. Read only for comparison;
its presence never makes a runner skip a run. The machine-readable
record is `metrics.json` + `verdict.json` here.

## Provenance

- **stage:** `capstone.two_node_laplace`
- **verdict:** **PASS** (exit 0)
- **policy:** `capstone.two_node_laplace.v2`  sha256 `96a85dcc29dec3b5…`
- **analysis id:** `20260806T142603Z_96a85dcc`
- **git commit:** `91052aab12ea443fd58dfac12e94966035b3adbe` (dirty=False)
- **backend:** CUDA (GPU), 1 MPI rank, seed 42
- **WarpX:** 26.5  |  **Python:** 3.12.13

## Runs

- `20260806T142600Z_f44044c6`  case_sha256 `f44044c6a4428670…`

## Gates

- [PASS] `body_potential_imposed` — 0.219972 <= 1
- [PASS] `cathode_potential_imposed` — 0 <= 1
- [PASS] `maximum_principle_holds` — 0 <= 0.1
- [PASS] `matches_independent_solver` — 1.86438 <= 4
- [PASS] `per_step_rewrite_idempotent` — 0 <= 0.001
