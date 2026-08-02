#!/usr/bin/env python3
r"""opmodel.py — the 0-D laws and the operating-point solver.

Given one mission row from the orbit CSV — ambient (n_e, Te) and a drag demand —
this answers the design question: **what cathode voltage and beam current should
the thruster run at, and can it meet the demand at all?**

THE FOUR LAWS
-------------

1. Thrust ``F[nN] = k * I[mA] * sqrt(KE[eV])``, with ``KE = ke_ledger*(V - phi)``.
   The beam is born at the cathode, which sits ``V`` below a body floating at
   ``+phi``, so it arrives at infinity having fallen through ``V - phi``;
   ``ke_ledger`` is the fraction of that it actually keeps (the beam is born two
   cells above the cathode face, so it never sees the whole gap).

2. Escape ``I_escape = f_esc * I_beam``. The rest lands back on the craft and is
   internal to the supply loop — only the escaping current charges the body.

3. Collection (**the new law; this is what carries Te**)::

       I_return(phi) = beta * I_the(n_e, Te) * (1 + e*phi/kTe)
       I_the         = e * A * n_e * sqrt(kTe / (2*pi*m_e))

   ``I_the`` is the one-sided random thermal current a body at plasma potential
   draws; ``(1 + chi)`` is the OML-style enhancement a positive body gets by
   pulling in electrons from a wider impact-parameter fan; ``beta`` absorbs the
   geometry (a can is not a sphere) and is fitted from PIC.

   The predecessor's area law had **no Te dependence at all** while the IRI data
   swings Te over 800-3400 K. That is the substantive physics change here, and
   it does not go the way intuition suggests: ``I_the`` grows as ``sqrt(Te)``
   but the ``(1 + chi)`` pull weakens as ``1/Te``, and at the ``chi ~ 150-400``
   this design runs at the second term wins. **At fixed potential the ceiling
   goes as n_e/sqrt(Te)** — hot dayside electrons are HARDER to collect per unit
   density, not easier. Only a body sitting at plasma potential (``chi -> 0``)
   sees the bare ``n_e*sqrt(Te)`` thermal flux.

   Its closed-form inverse predicts where the body floats::

       phi(I_escape) = (kTe/e) * (I_escape/(beta*I_the) - 1)

4. Emission ceiling: the planar Child-Langmuir current over the emission spot,
   used as a SCALE. The validated reference run sits at ``I/I_CL = 1.46`` (a
   non-planar geometry beats the planar bound), so the constraint is
   ``I <= gamma_CL_max * I_CL(V)`` with ``gamma_CL_max = 1.5`` rather than 1.

THE COUPLING, AND WHY THERE ARE TWO ROOTS
-----------------------------------------
``I`` and ``phi`` are coupled: more current charges the body higher, and a higher
body robs the beam of energy. Substituting law 3's inverse into law 1 gives
thrust as an explicit function of current alone::

    phi(I) = a*I - b,     a = (kTe/e)*f_esc/(beta*I_the),   b = kTe/e
    F(I)   = k*I*sqrt(ke_ledger*(V + b - a*I))

``F(0) = 0`` and ``F -> 0`` again as ``phi -> V``, so **F has an interior
maximum** and a given thrust demand generally has TWO solutions. The rising
branch is the one to fly: same thrust, less current, less power. The maximum is
closed-form::

    I* = 2*(V + b)/(3*a),    F_max = k*I* * sqrt(ke_ledger*(V + b)/3)

which is what makes "is this row feasible at all?" a question with an exact
answer rather than a search that might have missed a root.

WHAT THIS IS NOT
----------------
A surrogate for the PIC run, so a mission envelope can be searched in
milliseconds instead of GPU-days. It is a TARGETING tool: it says where to spend
the ten hours. Anything it produces that matters gets confirmed by a direct run
at that point — which is what ``pic_sims/validation_cases/capstone/
3_mission_envelope`` exists to do.

Depends on: scipy.constants only (no numpy needed for the scalar path).
"""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass

from scipy import constants as scc

E = scc.e
ME = scc.m_e
EPS0 = scc.epsilon_0
KB = scc.k


# ======================================================================
# constraints
# ======================================================================

@dataclass(frozen=True)
class Constraints:
    """The box the operating point has to live in.

    ``d_gap`` and ``emit_radius`` describe the gun, and default to the validated
    capstone geometry (cathode top at z = -4.6 mm, lid bottom at z = +0.1 mm;
    0.5 mm emission spot). They belong here rather than in laws.yaml because
    they are DESIGN choices, not measurements.
    """
    v_min: float = 100.0          # [V] hardware floor on the supply
    v_max: float = 300.0          # [V] hardware ceiling
    phi_max: float = 50.0         # [V] design limit on the float (watchdog at 100 V)
    gamma_cl_max: float = 1.5     # [-] allowed I / I_CL (reference run: 1.46)
    margin: float = 1.0           # [-] thrust demand = margin * drag
    d_gap: float = 4.7e-3         # [m] cathode top -> lid bottom
    emit_radius: float = 0.5e-3   # [m] emission-spot radius
    v_step: float = 1.0           # [V] search granularity over V

    def validate(self) -> None:
        if not (0.0 < self.v_min <= self.v_max):
            raise ValueError("need 0 < v_min <= v_max")
        if self.phi_max <= 0.0:
            raise ValueError("phi_max must be positive")
        if self.phi_max >= self.v_min:
            raise ValueError(
                "phi_max must stay below v_min, else the beam can be fully "
                "stalled inside the allowed box")
        if self.gamma_cl_max <= 0.0:
            raise ValueError("gamma_cl_max must be positive")
        if self.margin <= 0.0:
            raise ValueError("margin must be positive")
        if self.d_gap <= 0.0 or self.emit_radius <= 0.0:
            raise ValueError("gun geometry must be positive")
        if self.v_step <= 0.0:
            raise ValueError("v_step must be positive")


# ======================================================================
# the laws, as pure functions
# ======================================================================

def kTe_eV(Te_K: float) -> float:
    """Electron temperature in eV (== the volts one kTe is worth)."""
    return KB * Te_K / E


def exhaust_ke_eV(v_drive: float, phi_V: float, ke_ledger: float) -> float:
    """Mean kinetic energy of the escaping beam [eV]. Law 1's energy half."""
    return ke_ledger * (abs(v_drive) - phi_V)


def thrust_nN(i_mA: float, v_drive: float, phi_V: float, k: float,
              ke_ledger: float) -> float:
    """Law 1: thrust [nN] from `i_mA` of beam at `v_drive`, body at `phi_V`."""
    ke = exhaust_ke_eV(v_drive, phi_V, ke_ledger)
    return k * i_mA * math.sqrt(ke) if ke > 0.0 else 0.0


def current_for_thrust_mA(f_nN: float, v_drive: float, phi_V: float, k: float,
                          ke_ledger: float) -> float:
    """Inverse of :func:`thrust_nN` at FIXED phi (the uncoupled inverse)."""
    ke = exhaust_ke_eV(v_drive, phi_V, ke_ledger)
    return f_nN / (k * math.sqrt(ke)) if ke > 0.0 else float("inf")


def thrust_nN_ideal(i_mA: float, v_drive: float) -> float:
    """Ideal thrust [nN]: every electron escapes with the full gap energy.

    COMPARISON ONLY. Quoting this as a mission number is the predecessor's
    documented mistake (its summary reported the ideal slope while every written
    conclusion used the measured one).
    """
    v_e = math.sqrt(2.0 * E * abs(v_drive) / ME)
    return i_mA * 1e-3 * ME * v_e / E * 1e9


def thermal_current_A(n_e: float, Te_K: float, area_m2: float) -> float:
    """Law 3's ``I_the``: one-sided random thermal electron current [A].

    ``n*e*A*sqrt(kTe/(2*pi*m_e))`` — what a body sitting at plasma potential
    collects. Scales as ``n_e * sqrt(Te)``.
    """
    return n_e * E * area_m2 * math.sqrt(KB * Te_K / (2.0 * math.pi * ME))


def chi(phi_V: float, Te_K: float) -> float:
    """Normalised body potential ``e*phi/kTe`` — the OML enhancement parameter."""
    return phi_V / kTe_eV(Te_K)


def return_current_A(phi_V: float, n_e: float, Te_K: float, beta: float,
                     area_m2: float) -> float:
    """Law 3: ambient electron current the body collects at ``phi_V`` [A]."""
    i_the = thermal_current_A(n_e, Te_K, area_m2)
    return beta * i_the * (1.0 + chi(phi_V, Te_K))


def phi_for_escape_current_V(i_escape_A: float, n_e: float, Te_K: float,
                             beta: float, area_m2: float) -> float:
    """Law 3 inverted: where the body floats while losing ``i_escape_A`` [V].

    Steady state is a current balance — everything that leaves as beam must come
    back as collected ambient electrons — so this is the predicted float.
    """
    i_the = thermal_current_A(n_e, Te_K, area_m2)
    if i_the <= 0.0:
        return float("inf")
    return kTe_eV(Te_K) * (i_escape_A / (beta * i_the) - 1.0)


def beam_current_at_phi_A(phi_V: float, n_e: float, Te_K: float, beta: float,
                          area_m2: float, f_esc: float) -> float:
    """The EMITTED current whose steady float lands exactly on ``phi_V`` [A]."""
    return return_current_A(phi_V, n_e, Te_K, beta, area_m2) / f_esc


def child_langmuir_A(v_drive: float, d_gap: float, emit_radius: float) -> float:
    """Law 4: planar Child-Langmuir current over the emission spot [A].

    A SCALE, not a bound: the real geometry is non-planar and the validated run
    draws 1.46x this. Used only through ``gamma_cl_max``.
    """
    j = (4.0 / 9.0) * EPS0 * math.sqrt(2.0 * E / ME) * abs(v_drive) ** 1.5 / d_gap ** 2
    return j * math.pi * emit_radius ** 2


def settle_time_s(phi_V: float, i_beam_A: float, capacitance_F: float) -> float:
    """RC-style time for the float to charge to ``phi_V`` [s].

    The body is a capacitor charged by the escaping beam, so ``tau ~ C*phi/I``.
    It matters because a PIC run shorter than a few tau measures a transient, not
    an equilibrium — and tau grows as 1/n_e, so the NIGHT rows are the slow ones.
    """
    if i_beam_A <= 0.0:
        return float("inf")
    return capacitance_F * phi_V / i_beam_A


def analytic_capacitance_F(r_probe_m: float) -> float:
    """Isolated-sphere self-capacitance ``4*pi*eps0*r`` [F]."""
    return 4.0 * math.pi * EPS0 * r_probe_m


# ======================================================================
# the operating point
# ======================================================================

@dataclass(frozen=True)
class OperatingPoint:
    """One solved (V, I, phi) with everything needed to judge or freeze it."""
    # inputs echoed back
    n_e: float
    Te_K: float
    drag_N: float
    f_required_nN: float
    # the point
    v_drive_V: float
    i_beam_mA: float
    phi_V: float
    f_nN: float
    p_supply_mW: float
    exhaust_ke_eV: float
    # diagnosis
    feasible: bool
    binding: str               # "demand" | "phi_max" | "gamma_cl" | "thrust_peak"
    chi: float
    settle_time_s: float
    i_cl_mA: float
    i_over_i_cl: float
    i_the_uA: float
    f_max_nN: float            # the most this row can deliver at this V
    i_max_mA: float            # the current that delivers f_max_nN (full throttle)
    p_max_mW: float            # what full throttle costs
    deficit_nN: float          # max(0, required - delivered)

    def as_dict(self) -> dict:
        return asdict(self)

    def describe(self) -> str:
        state = "OK " if self.feasible else "SHORT"
        return (f"[{state}] V={self.v_drive_V:6.1f} V  I={self.i_beam_mA:7.4f} mA  "
                f"phi={self.phi_V:6.2f} V  F={self.f_nN:7.3f} nN "
                f"(need {self.f_required_nN:.3f})  P={self.p_supply_mW:7.2f} mW  "
                f"chi={self.chi:6.1f}  I/I_CL={self.i_over_i_cl:.2f}  "
                f"tau={self.settle_time_s*1e9:6.1f} ns  binding={self.binding}")


def _coefficients(n_e: float, Te_K: float, laws) -> tuple[float, float]:
    """``(a, b)`` of the linear float response ``phi(I_beam) = a*I - b``.

    ``a`` [V/A] is the stiffness — how many volts one amp of beam costs — and it
    scales as ``1/(n_e*sqrt(Te))``: the night ionosphere is a much stiffer spring.
    """
    b = kTe_eV(Te_K)
    i_the = thermal_current_A(n_e, Te_K, laws.area_m2)
    if i_the <= 0.0:
        return float("inf"), b
    a = b * laws.f_esc / (laws.beta * i_the)
    return a, b


def thrust_peak(v_drive: float, n_e: float, Te_K: float, laws) -> tuple[float, float]:
    """Closed-form interior maximum of ``F(I)`` at fixed V: ``(I*_A, F*_nN)``.

    ``d/dI [I*sqrt(c - a*I)] = 0`` at ``I* = 2c/(3a)`` with ``c = V + b``.
    """
    a, b = _coefficients(n_e, Te_K, laws)
    if not math.isfinite(a) or a <= 0.0:
        return 0.0, 0.0
    c = abs(v_drive) + b
    i_star = 2.0 * c / (3.0 * a)
    f_star = laws.k * (i_star * 1e3) * math.sqrt(laws.ke_ledger * c / 3.0)
    return i_star, f_star


def solve_at_voltage(n_e: float, Te_K: float, drag_N: float, v_drive: float,
                     laws, cons: Constraints) -> OperatingPoint:
    """Solve the coupled (I, phi) problem at ONE drive voltage.

    Returns the cheapest point that meets ``margin*drag`` if one exists, else the
    most thrust this row can produce at ``v_drive`` and the constraint that stops
    it going further.
    """
    a, b = _coefficients(n_e, Te_K, laws)
    f_req_nN = cons.margin * drag_N * 1e9
    i_the = thermal_current_A(n_e, Te_K, laws.area_m2)
    i_cl = child_langmuir_A(v_drive, cons.d_gap, cons.emit_radius)

    # --- the three ceilings on current -----------------------------------
    i_at_phi_max = beam_current_at_phi_A(cons.phi_max, n_e, Te_K, laws.beta,
                                         laws.area_m2, laws.f_esc)
    i_at_cl = cons.gamma_cl_max * i_cl
    i_star, f_star = thrust_peak(v_drive, n_e, Te_K, laws)

    limits = {"phi_max": i_at_phi_max, "gamma_cl": i_at_cl, "thrust_peak": i_star}
    binding = min(limits, key=lambda key: limits[key])
    i_best = limits[binding]

    def _phi(i_A: float) -> float:
        return a * i_A - b

    def _thrust_nN(i_A: float) -> float:
        return thrust_nN(i_A * 1e3, v_drive, _phi(i_A), laws.k, laws.ke_ledger)

    f_max_nN = _thrust_nN(i_best) if i_best > 0.0 else 0.0

    if f_req_nN <= f_max_nN and i_best > 0.0:
        # F is strictly increasing on (0, i_star], and i_best <= i_star, so the
        # demand has exactly one root in (0, i_best]: bisect for it.
        lo, hi = 0.0, i_best
        for _ in range(200):
            mid = 0.5 * (lo + hi)
            if _thrust_nN(mid) < f_req_nN:
                lo = mid
            else:
                hi = mid
        i_sol = 0.5 * (lo + hi)
        feasible, binding_out = True, "demand"
    else:
        i_sol = i_best
        feasible, binding_out = False, binding

    phi = _phi(i_sol)
    f_nN = _thrust_nN(i_sol)
    return OperatingPoint(
        n_e=n_e, Te_K=Te_K, drag_N=drag_N, f_required_nN=f_req_nN,
        v_drive_V=abs(v_drive), i_beam_mA=i_sol * 1e3, phi_V=phi, f_nN=f_nN,
        p_supply_mW=i_sol * abs(v_drive) * 1e3,
        exhaust_ke_eV=exhaust_ke_eV(v_drive, phi, laws.ke_ledger),
        feasible=feasible, binding=binding_out, chi=chi(phi, Te_K),
        settle_time_s=settle_time_s(phi, i_sol, laws.capacitance_F),
        i_cl_mA=i_cl * 1e3, i_over_i_cl=(i_sol / i_cl if i_cl > 0 else float("inf")),
        i_the_uA=i_the * 1e6, f_max_nN=f_max_nN, i_max_mA=i_best * 1e3,
        p_max_mW=i_best * abs(v_drive) * 1e3,
        deficit_nN=max(0.0, f_req_nN - f_nN))


def solve_operating_point(n_e: float, Te_K: float, drag_N: float, laws,
                          cons: Constraints = Constraints()) -> OperatingPoint:
    """The design answer for one mission row.

    OBJECTIVE. Minimise supply power ``P = I*V`` subject to ``F >= margin*drag``.
    At fixed thrust ``I ~ 1/sqrt(V)``, so ``P ~ sqrt(V)`` and the cheapest
    feasible point is the LOWEST feasible voltage — but the ceilings all rise
    with V (``I_CL ~ V^1.5``), so low voltage is also where feasibility runs out.
    The scan resolves that trade honestly rather than assuming which side wins.

    INFEASIBLE ROWS. Station keeping does not need continuous thrust, only
    ``<F> >= <drag>`` over an orbit. When no voltage meets the demand, this
    returns the point that maximises delivered thrust (which is always at
    ``v_max``, since every ceiling grows with V) and records the deficit, and
    :func:`orbit_summary` turns those deficits into a duty-cycle statement.
    """
    cons.validate()
    if n_e <= 0.0 or Te_K <= 0.0:
        raise ValueError(f"non-physical plasma row: n_e={n_e}, Te={Te_K}")

    n_steps = int(round((cons.v_max - cons.v_min) / cons.v_step))
    voltages = [cons.v_min + i * cons.v_step for i in range(n_steps + 1)]
    if voltages[-1] < cons.v_max:
        voltages.append(cons.v_max)

    points = [solve_at_voltage(n_e, Te_K, drag_N, v, laws, cons) for v in voltages]
    feasible = [p for p in points if p.feasible]
    if feasible:
        return min(feasible, key=lambda p: p.p_supply_mW)
    return max(points, key=lambda p: p.f_nN)


# ======================================================================
# mission-level rollup
# ======================================================================

@dataclass(frozen=True)
class OrbitSummary:
    """Whether the mission closes ON AVERAGE, which is the real requirement."""
    n_rows: int
    drag_mean_nN: float
    drag_p95_nN: float
    drag_max_nN: float
    f_max_mean_nN: float
    continuous_feasible_frac: float
    duty_cycle_required: float
    closes_on_average: bool
    power_mean_mW: float
    power_at_duty_mW: float

    def describe(self) -> str:
        verdict = ("CLOSES on orbit average" if self.closes_on_average
                   else "DOES NOT CLOSE even at 100 % duty")
        return (
            f"orbit summary over {self.n_rows} rows\n"
            f"  drag        mean {self.drag_mean_nN:.3f} nN, p95 "
            f"{self.drag_p95_nN:.3f} nN, max {self.drag_max_nN:.3f} nN\n"
            f"  deliverable mean {self.f_max_mean_nN:.3f} nN at full throttle\n"
            f"  continuous thrust meets demand on "
            f"{self.continuous_feasible_frac*100:.1f} % of rows\n"
            f"  required duty cycle {self.duty_cycle_required*100:.1f} %  ->  {verdict}\n"
            f"  supply power {self.power_mean_mW:.2f} mW at full throttle, "
            f"{self.power_at_duty_mW:.2f} mW at that duty")


def _nearest_rank(sorted_vals: list[float], pct: float) -> float:
    if not sorted_vals:
        return float("nan")
    idx = max(0, min(len(sorted_vals) - 1,
                     int(math.ceil(pct / 100.0 * len(sorted_vals))) - 1))
    return sorted_vals[idx]


def orbit_summary(rows, laws, cons: Constraints = Constraints()) -> OrbitSummary:
    """Roll a whole mission CSV up into an average-thrust feasibility statement.

    ``rows`` is any iterable of objects with ``n_e``, ``Te_K`` and ``drag_N``.
    Each row is evaluated at FULL THROTTLE (``v_max``, every ceiling respected),
    because the question is what the vehicle can deliver, not what it would
    choose to. Station keeping then needs ``<F_max> * duty >= <drag>``.
    """
    drags, f_maxes, powers = [], [], []
    n_ok = 0
    for row in rows:
        p = solve_at_voltage(row.n_e, row.Te_K, row.drag_N, cons.v_max, laws, cons)
        drags.append(row.drag_N * 1e9)
        f_maxes.append(p.f_max_nN)
        powers.append(p.p_max_mW)
        if p.f_max_nN >= cons.margin * row.drag_N * 1e9:
            n_ok += 1
    n = len(drags)
    if n == 0:
        raise ValueError("orbit_summary got no rows")
    drag_mean = sum(drags) / n
    f_mean = sum(f_maxes) / n
    duty = drag_mean / f_mean if f_mean > 0 else float("inf")
    p_mean = sum(powers) / n
    return OrbitSummary(
        n_rows=n, drag_mean_nN=drag_mean,
        drag_p95_nN=_nearest_rank(sorted(drags), 95.0),
        drag_max_nN=max(drags), f_max_mean_nN=f_mean,
        continuous_feasible_frac=n_ok / n, duty_cycle_required=duty,
        closes_on_average=bool(duty <= 1.0), power_mean_mW=p_mean,
        power_at_duty_mW=p_mean * min(duty, 1.0))


# ======================================================================
# re-anchoring: derive the constants from one PIC measurement
# ======================================================================

def anchor_constants(*, f_beam_nN: float, phi_body_V: float,
                     escape_fraction_pct: float, exhaust_ke_eV: float,
                     i_beam_A: float, v_drive_V: float, n_e: float, Te_K: float,
                     area_m2: float) -> dict:
    """Invert the laws at one measured operating point to get their constants.

    This is the whole re-anchoring: every constant below is an EXACT algebraic
    consequence of numbers that live in a committed ``metrics.json``, so nothing
    is ever hand-typed and ``refit_laws.py`` and the ladder's cross-stage check
    can both re-derive them independently and compare.
    """
    ke_ledger = exhaust_ke_eV / (abs(v_drive_V) - phi_body_V)
    i_mA = i_beam_A * 1e3
    k = f_beam_nN / (i_mA * math.sqrt(exhaust_ke_eV))
    f_esc = escape_fraction_pct / 100.0
    i_the = thermal_current_A(n_e, Te_K, area_m2)
    i_escape = f_esc * i_beam_A
    beta = i_escape / (i_the * (1.0 + chi(phi_body_V, Te_K)))
    return {
        "k": k,
        "ke_ledger": ke_ledger,
        "f_esc": f_esc,
        "beta": beta,
        "i_the_A": i_the,
        "chi": chi(phi_body_V, Te_K),
        "i_escape_A": i_escape,
    }
