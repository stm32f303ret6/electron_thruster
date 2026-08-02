"""Analysis math + policy wiring on synthetic fixtures (no WarpX/openPMD).

The reference RZ Laplace solver is validated on manufactured harmonic
solutions (linear-in-z is exact for a second-order stencil), and the gate
wiring is checked fail-closed against acceptance.yaml."""

from pathlib import Path

import numpy as np
import pytest

import analyze
import ladder_contract as lc

STAGE_DIR = Path(__file__).resolve().parents[1]
POLICY = STAGE_DIR / "acceptance.yaml"


def _jacobi_reference(r, z, fixed, dirichlet, sweeps=20000):
    """Independently hand-written Jacobi relaxation of the conservative RZ
    Laplace stencil (zero-area west face on the axis), used to cross-check
    the sparse-matrix assembly in analyze.reference_laplace."""
    nr, nz = len(r), len(z)
    dr, dz = float(r[1] - r[0]), float(z[1] - z[0])
    phi = dirichlet.copy()
    for _ in range(sweeps):
        new = phi.copy()
        for i in range(nr):
            for j in range(1, nz - 1):
                if fixed[i, j]:
                    continue
                r_p = max(float(r[i]), 0.25 * dr)
                r_e = float(r[i]) + 0.5 * dr
                r_w = max(float(r[i]) - 0.5 * dr, 0.0)
                cE = r_e / (r_p * dr * dr)
                cW = r_w / (r_p * dr * dr)
                cN = cS = 1.0 / (dz * dz)
                num = cN * phi[i, j + 1] + cS * phi[i, j - 1]
                den = cN + cS + cE
                if i + 1 < nr:
                    num += cE * phi[i + 1, j]
                if cW > 0.0:
                    num += cW * phi[i - 1, j]
                    den += cW
                new[i, j] = num / den
        if np.abs(new - phi).max() < 1e-13:
            phi = new
            break
        phi = new
    return phi


def test_reference_solver_matches_independent_jacobi():
    """A charged disk inside the grounded box: the sparse direct solve must
    agree with a hand-written Jacobi relaxation of the same PDE."""
    nr, nz = 10, 12
    r = np.linspace(0.0, 1.0, nr)
    z = np.linspace(-1.0, 1.0, nz)
    body = np.zeros((nr, nz), dtype=bool)
    body[:4, 5:7] = True     # a disk on the axis at mid-height
    cathode = np.zeros((nr, nz), dtype=bool)

    phi = analyze.reference_laplace(r, z, body, cathode,
                                    phi_body=10.0, phi_cathode=0.0)

    fixed = body.copy()
    fixed[-1, :] = fixed[:, 0] = fixed[:, -1] = True
    dirichlet = np.where(body, 10.0, 0.0)
    ref = _jacobi_reference(r, z, fixed, dirichlet)
    assert np.abs(phi - ref).max() < 1e-8


def test_reference_solver_axial_symmetry():
    """A disk centered at z=0 in a z-symmetric grounded box must give a
    z-symmetric potential (catches stencil/indexing asymmetries)."""
    nr, nz = 10, 13   # odd nz: a symmetric node layout about z=0
    r = np.linspace(0.0, 1.0, nr)
    z = np.linspace(-1.2, 1.2, nz)
    body = np.zeros((nr, nz), dtype=bool)
    body[:3, 6] = True       # single-plane disk at exactly z=0
    cathode = np.zeros((nr, nz), dtype=bool)
    phi = analyze.reference_laplace(r, z, body, cathode,
                                    phi_body=5.0, phi_cathode=0.0)
    assert np.allclose(phi, phi[:, ::-1], atol=1e-10)


def test_reference_solver_uniform_dirichlet_is_flat():
    """All boundaries at V -> phi = V everywhere (no source, no gradients)."""
    nr, nz = 10, 10
    r = np.linspace(0.0, 1.0, nr)
    z = np.linspace(0.0, 1.0, nz)
    body = np.zeros((nr, nz), dtype=bool)
    cathode = np.zeros((nr, nz), dtype=bool)
    # enclose the domain: mark every edge node as BODY at 5 V
    body[0, :] = body[-1, :] = body[:, 0] = body[:, -1] = True
    phi = analyze.reference_laplace(r, z, body, cathode,
                                    phi_body=5.0, phi_cathode=-1.0)
    assert np.allclose(phi, 5.0, atol=1e-9)


def _metrics(**over):
    base = dict(body_surface_potential_error_V=0.05,
                cathode_surface_potential_error_V=0.05,
                laplace_bounds_violation_V=0.0,
                independent_solver_max_diff_V=1.0,
                per_step_rewrite_drift_V=0.0)
    base.update(over)
    return {k: lc.Metric.measure(k, v, "V") for k, v in base.items()}


def test_clean_solution_passes_policy():
    verdict = lc.evaluate_gates(_metrics(), lc.load_policy(POLICY))
    assert verdict.status == lc.V_PASS, verdict.detail


def test_wrong_surface_potential_fails():
    # e.g. a sign error or region misclassification shifts a node by volts
    verdict = lc.evaluate_gates(_metrics(cathode_surface_potential_error_V=50.0),
                                lc.load_policy(POLICY))
    assert verdict.status == lc.V_FAIL


def test_maximum_principle_violation_fails():
    verdict = lc.evaluate_gates(_metrics(laplace_bounds_violation_V=2.0),
                                lc.load_policy(POLICY))
    assert verdict.status == lc.V_FAIL


def test_solver_disagreement_fails():
    verdict = lc.evaluate_gates(_metrics(independent_solver_max_diff_V=25.0),
                                lc.load_policy(POLICY))
    assert verdict.status == lc.V_FAIL


def test_rewrite_drift_fails():
    verdict = lc.evaluate_gates(_metrics(per_step_rewrite_drift_V=0.5),
                                lc.load_policy(POLICY))
    assert verdict.status == lc.V_FAIL


def test_missing_metric_is_error_exit2():
    m = _metrics()
    del m["independent_solver_max_diff_V"]
    verdict = lc.evaluate_gates(m, lc.load_policy(POLICY))
    assert verdict.status == lc.V_ERROR and verdict.exit_code == 2


def test_nonfinite_metric_is_error_exit2():
    verdict = lc.evaluate_gates(_metrics(laplace_bounds_violation_V=float("nan")),
                                lc.load_policy(POLICY))
    assert verdict.status == lc.V_ERROR and verdict.exit_code == 2
