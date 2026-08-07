#!/usr/bin/env python3
"""The literal validation ladder: a visible, hand-maintained stage list.

Keeping membership explicit (rather than globbing directories) means drift
becomes an error the tests catch, not a silent surprise.  ``run_ladder.py`` and
the repository tests read STAGES; nothing here imports a stage's WarpX code.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

VALIDATION_ROOT = Path(__file__).resolve().parent


@dataclass(frozen=True)
class Stage:
    id: str
    directory: Path
    requires: tuple[str, ...] = ()
    scenarios: tuple[str, ...] = ()   # empty means single-run stage

    @property
    def path(self) -> Path:
        return VALIDATION_ROOT / self.directory


STAGES: tuple[Stage, ...] = (
    Stage("emitter.negative_cathode",
          Path("electron_gun/1_negative_cathode")),
    Stage("emitter.holed_anode",
          Path("electron_gun/2_electron_gun"),
          requires=("emitter.negative_cathode",),
          scenarios=("A_low_current_small_hole",
                     "B_high_current_small_hole",
                     "C_high_current_big_hole")),
    # The gun along the voltage axis: closes the emitter branch's voltage gap
    # (beam formation was validated only at 100 V while the capstones drive
    # 200-300 V -- VALIDATION_GAPS.md G3) and demonstrates over-ceiling
    # current limiting at the fixed-thrust throttle command (UCURVE_PLAN.md).
    Stage("emitter.voltage_bracket",
          Path("electron_gun/3_voltage_bracket"),
          requires=("emitter.holed_anode",),
          scenarios=("A_200v_anchor_drive",
                     "B_300v_ceiling_drive",
                     "C_ucurve_overperveance")),
    Stage("collector.thermal",
          Path("current_collection/1_thermal")),
    Stage("collector.biased_3v",
          Path("current_collection/2_biased_3v"),
          requires=("collector.thermal",)),
    Stage("collector.biased_10v",
          Path("current_collection/3_biased_10v"),
          requires=("collector.biased_3v",)),
    Stage("collector.floating",
          Path("current_collection/4_floating"),
          requires=("collector.thermal",)),
    Stage("capstone.two_node_laplace",
          Path("capstone/1_two_node_laplace")),
    Stage("capstone.floating_body",
          Path("capstone/2_chipsat_thruster"),
          requires=("emitter.holed_anode", "collector.biased_10v",
                    "collector.floating", "capstone.two_node_laplace")),
    Stage("capstone.high_thrust",
          Path("capstone/3_high_thrust"),
          requires=("capstone.floating_body",)),
    Stage("capstone.low_power",
          Path("capstone/4_low_power"),
          requires=("capstone.floating_body",)),
    # The fixed-thrust throttle curve (pre-registered: capstone/UCURVE_PLAN.md).
    # The committed frontier holds perveance fixed and measures the envelope
    # boundary; these three stages hold the DEMAND fixed (the 200 V anchor's
    # 13.65 nN) and measure the cost surface inside it -- valley location,
    # left arm, and the no-go wall under the flight rule's voltage floor.
    Stage("capstone.ucurve_valley",
          Path("capstone/5_ucurve_valley"),
          requires=("capstone.floating_body",)),
    Stage("capstone.ucurve_left_arm",
          Path("capstone/6_ucurve_left_arm"),
          requires=("capstone.floating_body",)),
    Stage("capstone.ucurve_floor",
          Path("capstone/7_ucurve_floor"),
          requires=("capstone.floating_body",)),
)

# Fast lookups used by the runner and the tests.
STAGE_BY_ID: dict[str, Stage] = {s.id: s for s in STAGES}


def topological_order(stage_ids: list[str] | None = None) -> list[Stage]:
    """Return the requested stages (default: all) in dependency order.

    Raises ValueError on an unknown id, a missing dependency, or a cycle.
    """
    wanted = list(STAGE_BY_ID) if stage_ids is None else list(stage_ids)
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
