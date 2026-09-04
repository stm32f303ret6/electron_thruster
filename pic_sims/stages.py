#!/usr/bin/env python3
"""The literal stage registry: a visible, hand-maintained stage list.

Two groups share one contract and one runner:

- ``ladder``: the concept-validation ladder -- rungs that must pass in
  dependency order, from the bare cathode up to the chipsat anchor
  (``capstone.floating_body``).  ``run_ladder.py`` runs this group by default.
- ``characterization``: thruster-characterization spokes off the anchor
  (voltage, geometry, density, magnetic field).  Each depends only on the
  anchor, never on another spoke, and runs only when named via ``--stages``.

Keeping membership explicit (rather than globbing directories) means drift
becomes an error the tests catch, not a silent surprise.  ``run_ladder.py`` and
the repository tests read STAGES; nothing here imports a stage's WarpX code.

Stage ids are frozen once evidence is committed: every manifest and verdict
embeds them, so folders may move but ids never change.  That is why the two
voltage spokes moved to ``characterization/`` keep their historical
``capstone.*`` ids.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

PIC_ROOT = Path(__file__).resolve().parent
# Historical alias (pre-2026-08-11 layout put everything under
# validation_cases/); kept so older scripts fail loudly nowhere.
VALIDATION_ROOT = PIC_ROOT


@dataclass(frozen=True)
class Stage:
    id: str
    directory: Path
    requires: tuple[str, ...] = ()
    scenarios: tuple[str, ...] = ()   # empty means single-run stage
    group: str = "ladder"             # "ladder" | "characterization"

    @property
    def path(self) -> Path:
        return PIC_ROOT / self.directory


STAGES: tuple[Stage, ...] = (
    Stage("emitter.negative_cathode",
          Path("ladder/electron_gun/1_negative_cathode")),
    Stage("emitter.holed_anode",
          Path("ladder/electron_gun/2_electron_gun"),
          requires=("emitter.negative_cathode",),
          scenarios=("A_low_current_small_hole",
                     "B_high_current_small_hole",
                     "C_high_current_big_hole")),
    # The gun along the voltage axis: closes the emitter branch's voltage gap
    # (beam formation was validated only at 100 V while the capstones drive
    # 200-300 V -- VALIDATION_GAPS.md G3).  Its scenario C measured that the
    # planar-I_CL scale is conservative here (0.9999 transmission at 133.5%
    # of the scale; the v1 limiting expectation is a recorded refutation),
    # locating the fixed-thrust throttle stages' escape tax inside the can
    # (future_work/UCURVE_PLAN.md).
    Stage("emitter.voltage_bracket",
          Path("ladder/electron_gun/3_voltage_bracket"),
          requires=("emitter.holed_anode",),
          scenarios=("A_200v_anchor_drive",
                     "B_300v_ceiling_drive",
                     "C_ucurve_overperveance")),
    Stage("collector.thermal",
          Path("ladder/current_collection/1_thermal")),
    Stage("collector.biased_3v",
          Path("ladder/current_collection/2_biased_3v"),
          requires=("collector.thermal",)),
    Stage("collector.biased_10v",
          Path("ladder/current_collection/3_biased_10v"),
          requires=("collector.biased_3v",)),
    Stage("collector.floating",
          Path("ladder/current_collection/4_floating"),
          requires=("collector.thermal",)),
    Stage("capstone.two_node_laplace",
          Path("ladder/capstone/1_two_node_laplace")),
    Stage("capstone.floating_body",
          Path("ladder/capstone/2_chipsat_thruster"),
          requires=("emitter.holed_anode", "collector.biased_10v",
                    "collector.floating", "capstone.two_node_laplace")),

    # ---- thruster-characterization spokes (hub-and-spoke off the anchor) ----
    # capstone.high_thrust / capstone.low_power keep their pre-move ids: the
    # committed manifests embed them.
    Stage("capstone.high_thrust",
          Path("characterization/high_thrust"),
          requires=("capstone.floating_body",),
          group="characterization"),
    Stage("capstone.low_power",
          Path("characterization/low_power"),
          requires=("capstone.floating_body",),
          group="characterization"),
    # The four axis spokes below were first run as variant decks through the
    # anchor stage under the exploratory policy capstone.exploratory_axes.v1
    # (their migrated evidence keeps stage_id capstone.floating_body); these
    # registry entries gate FUTURE runs under the ids below.
    Stage("characterization.slender_body",
          Path("characterization/slender_body"),
          requires=("capstone.floating_body",),
          group="characterization"),
    Stage("characterization.thin_plasma",
          Path("characterization/thin_plasma"),
          requires=("capstone.floating_body",),
          group="characterization"),
    Stage("characterization.magnetized_1x",
          Path("characterization/magnetized_1x"),
          requires=("capstone.floating_body",),
          group="characterization"),
    Stage("characterization.magnetized_10x",
          Path("characterization/magnetized_10x"),
          requires=("capstone.floating_body",),
          group="characterization"),
    # 350 V envelope extension toward the 400 km demand (V_min = 304 V);
    # pre-registered 2026-08-17, no committed run yet.
    Stage("characterization.350V_400km",
          Path("characterization/350V_400km"),
          requires=("capstone.floating_body",),
          group="characterization"),
    # The slender body at the same 350 V operating point -- the fourth
    # corner of the 2x2 voltage-x-geometry factorial (deliberately two
    # axes off the anchor; both single-axis legs are measured -- see the
    # spoke README).  Pre-registered 2026-08-17, no committed run yet.
    Stage("characterization.350V_400km_slender",
          Path("characterization/350V_400km_slender"),
          requires=("capstone.floating_body",),
          group="characterization"),
    # Tier M2 of the magnetized axis (B perpendicular to the thrust axis, the
    # flight geometry) -- a Cartesian 3D deck with the anchor body resolved.
    # Pre-registered 2026-09-01.  transverse_b_numerics is the validation
    # mini-ladder the measurement rides on (single test electrons on the
    # measurement grid vs closed forms); run it first.  Both depend only on
    # the anchor per the spoke rule; the numerics->measurement order is a
    # documented convention (magnetized_transverse/README.md).
    Stage("characterization.transverse_b_numerics",
          Path("characterization/transverse_b_numerics"),
          requires=("capstone.floating_body",),
          scenarios=("gyro_1x", "gyro_10x", "exb_10x"),
          group="characterization"),
    Stage("characterization.magnetized_transverse",
          Path("characterization/magnetized_transverse"),
          requires=("capstone.floating_body",),
          scenarios=("b0_control", "transverse_1x", "transverse_10x"),
          group="characterization"),
    # The fixed-thrust throttle stages (geometry-specific controller work)
    # were moved out of the concept-feasibility ladder to
    # future_work/ucurve_pic_stages/ -- power consumption in the concept
    # argument is now the analytical model (model/mission_model.py --closed-form).
)

# Fast lookups used by the runner and the tests.
STAGE_BY_ID: dict[str, Stage] = {s.id: s for s in STAGES}
LADDER_STAGE_IDS: tuple[str, ...] = tuple(
    s.id for s in STAGES if s.group == "ladder")


def topological_order(stage_ids: list[str] | None = None) -> list[Stage]:
    """Return the requested stages (default: the ladder group) in dependency
    order.

    Raises ValueError on an unknown id, a missing dependency, or a cycle.
    """
    wanted = (list(LADDER_STAGE_IDS) if stage_ids is None
              else list(stage_ids))
    for sid in wanted:
        if sid not in STAGE_BY_ID:
            raise ValueError(f"unknown stage id: {sid}")

    ordered: list[Stage] = []
    placed: set[str] = set()
    visiting: set[str] = set()

    def visit(sid: str) -> None:
        if sid in placed:
            return
        if sid in visiting:
            raise ValueError(f"dependency cycle involving {sid}")
        visiting.add(sid)
        stage = STAGE_BY_ID[sid]
        for dep in stage.requires:
            if dep not in STAGE_BY_ID:
                raise ValueError(f"stage {sid} requires unknown stage {dep}")
            visit(dep)
        visiting.discard(sid)
        placed.add(sid)
        ordered.append(stage)

    for sid in wanted:
        visit(sid)
    return ordered
