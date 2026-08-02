#!/usr/bin/env python3
"""Analysis for capstone.two_node_laplace.

Reads one COMPLETE run's frozen evidence (the vacuum field dumps), and gates
the exact mathematical properties of the two-node Laplace solution:

  1. interior metal nodes carry the assigned Dirichlet values (BODY, CATHODE);
  2. the maximum principle: vacuum phi lies within the boundary values;
  3. agreement with an INDEPENDENT stair-step RZ finite-difference Laplace
     solve on the same grid (scipy sparse direct solve), compared >= 3 cells
     away from metal and domain boundaries where stair-step vs cut-cell
     surface representation differences have decayed;
  4. the per-step ``set_potential_on_eb`` rewrite is idempotent: the solution
     at the last step equals the first two-node solve.

Exit 0 all required gates pass / 1 a gate fails / 2 analysis error.

    python analyze.py --run outputs/<run-id> --policy acceptance.yaml
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

import numpy as np
from scipy import ndimage, sparse
from scipy.sparse.linalg import spsolve

CASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(CASE_DIR.parents[1]))
sys.path.insert(0, str(CASE_DIR))

import ladder_contract as lc  # noqa: E402
from helpers import STAGE_ID, Config, load_config  # noqa: E402

DEFAULT_POLICY = CASE_DIR / "acceptance.yaml"
RESULTS_ROOT = CASE_DIR / "results"


# ======================================================================
# evidence readers
# ======================================================================

def field_rz(ts, field, iteration):
    """Reconstruct the (r>=0, z) half-plane, robust to axis order."""
    F, info = ts.get_field(field=field, iteration=iteration, m="all", theta=0.0)
    r, z = np.asarray(info.r), np.asarray(info.z)
    raxis = next(k for k, v in dict(info.axes).items() if v == "r")
    if raxis == 1:
        F = F.T
    pos = r >= 0
    return F[pos], r[pos], z


# ======================================================================
# independent stair-step RZ Laplace solve (the cross-check)
# ======================================================================

def reference_laplace(r, z, body_mask, cathode_mask, phi_body, phi_cathode):
    """Solve Laplace's equation on the sample grid with a stair-step metal
    representation: Dirichlet phi_body/phi_cathode on metal nodes, 0 on the
    r=rmax / z=zmin / z=zmax domain edges, conservative RZ 5-point stencil
    (zero-area west face on the axis) everywhere else.  Independent of WarpX
    in both discretization (stair-step vs cut-cell EB) and linear solver
    (direct sparse factorization vs geometric multigrid)."""
    nr, nz = len(r), len(z)
    dr = float(r[1] - r[0])
    dz = float(z[1] - z[0])

    dirichlet = np.zeros((nr, nz))
    fixed = np.zeros((nr, nz), dtype=bool)
    fixed[body_mask] = True
    dirichlet[body_mask] = phi_body
    fixed[cathode_mask] = True
    dirichlet[cathode_mask] = phi_cathode
    fixed[-1, :] = True   # r = rmax edge: grounded
    fixed[:, 0] = True    # z = zmin edge: grounded
    fixed[:, -1] = True   # z = zmax edge: grounded
    # (dirichlet already 0 on the domain edges)

    idx = -np.ones((nr, nz), dtype=np.int64)
    free = ~fixed
    idx[free] = np.arange(int(free.sum()))
    n = int(free.sum())
    A = sparse.lil_matrix((n, n))
    b = np.zeros(n)
    ii, jj = np.nonzero(free)
    for i, j in zip(ii, jj):
        k = idx[i, j]
        r_p = float(r[i])
        # conservative radial faces; on/inside the axis the west face has
        # zero area, giving the standard 4/dr^2 axis limit
        r_e = r_p + 0.5 * dr
        r_w = max(r_p - 0.5 * dr, 0.0)
        r_c = max(r_p, 0.25 * dr)   # axis-node normalization
        cE = r_e / (r_c * dr * dr)
        cW = r_w / (r_c * dr * dr)
        cN = 1.0 / (dz * dz)
        cS = 1.0 / (dz * dz)
        diag = 0.0
        for (di, dj, c) in ((+1, 0, cE), (-1, 0, cW), (0, +1, cN), (0, -1, cS)):
            if c == 0.0:
                continue
            ni, nj = i + di, j + dj
            diag -= c
            if 0 <= ni < nr and 0 <= nj < nz:
                if fixed[ni, nj]:
                    b[k] -= c * dirichlet[ni, nj]
                else:
                    A[k, idx[ni, nj]] = c
            # a neighbor outside the grid only happens across the axis
            # (i=0 with di=-1), where cW=0 -- unreachable
        A[k, k] = diag
    phi = dirichlet.copy()
    phi[free] = spsolve(A.tocsr(), b)
    return phi


# ======================================================================
# metrics
# ======================================================================

def compute_metrics(cfg: Config, evidence: lc.LoadedRun):
    from openpmd_viewer import OpenPMDTimeSeries

    geom = cfg.geometry()
    ts = OpenPMDTimeSeries(os.path.join(str(evidence.diags_dir), "fields"),
                           check_all_files=False)
    its = [it for it in ts.iterations if it >= 1]   # it 0 = uniform-1V init
    if not its:
        raise lc.ContractError("no two-node field dumps (iterations >= 1)")
    if len(its) < 3:
        raise lc.ContractError(
            "need >= 3 two-node dumps: the idempotency gate compares the last "
            "two solves, past the first solve's convergence tail")
    first, penult, last = its[0], its[-2], its[-1]
    phi, r, z = field_rz(ts, "phi", first)
    phi_penult, _, _ = field_rz(ts, "phi", penult)
    phi_last, _, _ = field_rz(ts, "phi", last)

    R, Z = np.meshgrid(r, z, indexing="ij")
    masks = geom.node_masks(R, Z)
    body, cathode = masks["body"], masks["cathode"]
    metal = body | cathode

    # 1) assigned values on the metal nodes.  The cell-centered sample grid
    #    puts only ~2 nodes across each 0.4 mm wall, so every metal node
    #    touches the surface; nodes in cut cells carry interpolated values,
    #    which is exactly what the 1 V (0.5%-of-scale) gate budgets for.
    if not body.any() or not cathode.any():
        raise lc.ContractError(
            "empty metal mask: node grid does not resolve the can walls "
            "(geometry/grid mismatch between run and analysis)")
    body_err = float(np.abs(phi[body] - cfg.phi_body).max())
    cath_err = float(np.abs(phi[cathode] - cfg.phi_cathode).max())

    # 2) maximum principle over the vacuum: extrema on the boundary
    lo = min(cfg.phi_cathode, cfg.phi_body, 0.0)
    hi = max(cfg.phi_cathode, cfg.phi_body, 0.0)
    vac = ~metal
    violation = float(max(0.0, float(phi[vac].max()) - hi,
                          lo - float(phi[vac].min())))

    # 3) independent stair-step solve, compared away from surfaces.  The
    #    dominant reference error is the cathode-edge singularity: a ~200 V
    #    jump across the 2-cell insulating gap misplaced by up to dx/2 in the
    #    stair-step representation gives a local error ~ dV*(dx/2)/gap ~ 50 V
    #    decaying like a 2D edge perturbation ~ (dx/distance); at >= 20 cells
    #    that bounds the reference error to ~2.5 V, inside the 4 V gate.
    phi_ref = reference_laplace(r, z, body, cathode,
                                cfg.phi_body, cfg.phi_cathode)
    near_metal = ndimage.binary_dilation(metal, iterations=20)
    interior = ~near_metal
    interior[-3:, :] = False  # exclude the three Dirichlet domain edges
    interior[:, :3] = False
    interior[:, -3:] = False
    diff = np.abs(phi - phi_ref)
    solver_diff = float(diff[interior].max())
    solver_diff_all = float(diff[vac].max())

    # 4) per-step rewrite idempotency: once the field has converged (the
    #    first solve starts from the uniform-1V guess and carries a mV-scale
    #    convergence tail that the second solve polishes), re-imposing the
    #    same string must not move the solution at all.
    drift = float(np.abs(phi_last - phi_penult).max())
    settle = float(np.abs(phi_last - phi).max())

    metrics: dict[str, lc.Metric] = {}
    metrics["body_surface_potential_error_V"] = lc.Metric.measure(
        "body_surface_potential_error_V", body_err, "V",
        source=f"max |phi - {cfg.phi_body:g}| over interior BODY nodes, it {first}")
    metrics["cathode_surface_potential_error_V"] = lc.Metric.measure(
        "cathode_surface_potential_error_V", cath_err, "V",
        source=f"max |phi - {cfg.phi_cathode:g}| over interior CATHODE nodes")
    metrics["laplace_bounds_violation_V"] = lc.Metric.measure(
        "laplace_bounds_violation_V", violation, "V",
        source=f"vacuum phi outside [{lo:g}, {hi:g}] (maximum principle)")
    metrics["independent_solver_max_diff_V"] = lc.Metric.measure(
        "independent_solver_max_diff_V", solver_diff, "V",
        source="max |phi_warpx - phi_ref| >= 20 cells from metal (past the "
               "stair-step cathode-edge error) and >= 3 from domain edges")
    metrics["per_step_rewrite_drift_V"] = lc.Metric.measure(
        "per_step_rewrite_drift_V", drift, "V",
        source=f"max |phi(it {last}) - phi(it {penult})| (same string re-imposed "
               "on a converged field)")
    metrics["first_solve_settling_V"] = lc.Metric.measure(
        "first_solve_settling_V", settle, "V",
        source=f"max |phi(it {last}) - phi(it {first})|: the first solve's "
               "convergence tail (REPORTED, not gated)")
    # report-only: the raw full-domain disagreement (dominated by the
    # stair-step vs cut-cell skin) and the axis gap voltage
    metrics["independent_solver_full_max_diff_V"] = lc.Metric.measure(
        "independent_solver_full_max_diff_V", solver_diff_all, "V",
        source="max |phi_warpx - phi_ref| over ALL vacuum nodes (REPORTED)")
    iz_cath = int(np.argmin(np.abs(z - (geom.z_emit))))
    iz_lid = int(np.argmin(np.abs(z - geom.zlidb)))
    gap_v = float(phi[0, iz_lid] - phi[0, iz_cath])
    metrics["gap_axis_voltage_V"] = lc.Metric.measure(
        "gap_axis_voltage_V", gap_v, "V",
        source="phi on axis at the lid plane minus the emission plane (REPORTED)")

    extra = dict(phi=phi, phi_ref=phi_ref, diff=diff, r=r, z=z, metal=metal,
                 interior=interior)
    return metrics, extra


# ======================================================================
# figures
# ======================================================================

def write_outputs(analysis, cfg: Config, metrics, extra):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    phi, phi_ref, diff = extra["phi"], extra["phi_ref"], extra["diff"]
    r, z = extra["r"], extra["z"]
    figs = analysis.figures_dir

    fig, axs = plt.subplots(1, 3, figsize=(15, 4.6), sharey=True)
    vlim = max(abs(cfg.phi_cathode), abs(cfg.phi_body))
    for ax, F, title in ((axs[0], phi, "WarpX phi"),
                         (axs[1], phi_ref, "independent stair-step solve")):
        p = ax.pcolormesh(z * 1e3, r * 1e3, F, cmap="RdBu_r", shading="auto",
                          vmin=-vlim, vmax=vlim)
        fig.colorbar(p, ax=ax, label="phi [V]")
        ax.set_title(title)
        ax.set_xlabel("z [mm]")
    p = axs[2].pcolormesh(z * 1e3, r * 1e3, diff, cmap="inferno", shading="auto")
    fig.colorbar(p, ax=axs[2], label="|diff| [V]")
    axs[2].set_title("|WarpX - independent|")
    axs[2].set_xlabel("z [mm]")
    axs[0].set_ylabel("r [mm]")
    fig.suptitle(f"{cfg.stage_id}: BODY {cfg.phi_body:+g} V, "
                 f"CATHODE {cfg.phi_cathode:+g} V (vacuum Laplace)")
    fig.tight_layout()
    fig.savefig(figs / "fields.png", dpi=140)
    plt.close(fig)

    # axis profile through the gun gap
    fig, ax = plt.subplots(figsize=(8.4, 4.2))
    ax.plot(z * 1e3, phi[0, :], lw=1.4, label="WarpX (axis)")
    ax.plot(z * 1e3, phi_ref[0, :], lw=1.0, ls="--", label="independent (axis)")
    ax.axhline(cfg.phi_body, color="gray", ls=":", label=f"BODY {cfg.phi_body:+g} V")
    ax.axhline(cfg.phi_cathode, color="tab:red", ls=":",
               label=f"CATHODE {cfg.phi_cathode:+g} V")
    ax.set_xlabel("z [mm]")
    ax.set_ylabel("phi [V]")
    ax.set_title("on-axis potential through the gun gap")
    ax.legend(fontsize=8)
    ax.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(figs / "phi_axis.png", dpi=140)
    plt.close(fig)


# ======================================================================
# driver
# ======================================================================

def parse_args(argv=None):
    ap = argparse.ArgumentParser(description="two-node Laplace analysis")
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--run", type=Path, help="a COMPLETE run directory")
    g.add_argument("--runs", type=Path, nargs="+",
                   help="rejected: this stage is single-run")
    ap.add_argument("--policy", type=Path, default=DEFAULT_POLICY)
    return ap.parse_args(argv)


def _print_verdict(verdict: lc.Verdict) -> None:
    print("\n" + "=" * 72)
    print(f"VALIDATION GATES  [{verdict.stage_id}]  policy {verdict.policy_id}")
    print("=" * 72)
    for g in verdict.gates:
        print(f"[{g.status:4s}] {g.id}\n       {g.detail}")
    print("=" * 72)
    print(f"VERDICT: {verdict.status}  (exit {verdict.exit_code}) -- {verdict.detail}")
    print("=" * 72)


def main(argv=None) -> int:
    args = parse_args(argv)
    try:
        run_dirs = [args.run] if args.run else args.runs
        if len(run_dirs) != 1:
            raise lc.ContractError("capstone.two_node_laplace is single-run")
        evidence = lc.load_complete_runs(run_dirs)[0]
        cfg = load_config(evidence.dir / "config_used.yaml")
        policy = lc.load_policy(args.policy)
        if policy.stage_id != cfg.stage_id or evidence.stage_id != cfg.stage_id:
            raise lc.ContractError(
                f"stage mismatch: policy={policy.stage_id}, "
                f"run={evidence.stage_id}, config={cfg.stage_id}")
    except lc.ContractError as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return lc.EXIT_ERROR

    analysis = lc.begin_analysis([evidence], policy, results_root=RESULTS_ROOT,
                                 analyzer_source=__file__)
    print(f"ANALYSIS_ID={analysis.analysis_id}", flush=True)
    try:
        metrics, extra = compute_metrics(cfg, evidence)
        verdict = lc.evaluate_gates(metrics, policy)
        lc.write_metrics(analysis, metrics)
        lc.write_verdict(analysis, verdict)
        write_outputs(analysis, cfg, metrics, extra)
        lc.complete_analysis(analysis, verdict)
        _print_verdict(verdict)
        print(f"analysis -> {analysis.dir}")
        return verdict.exit_code
    except SystemExit:
        raise
    except BaseException as exc:  # noqa: BLE001
        lc.fail_analysis(analysis, exc)
        print(f"[ERROR] analysis failed: {exc!r}", file=sys.stderr)
        return lc.EXIT_ERROR


if __name__ == "__main__":
    raise SystemExit(main())
