"""Publication hygiene: this repository is self-contained.

Every number a reader can ask about must resolve to committed evidence in
this repo (reference_results/ + the model calibration) or to published
literature.  Names of external/unpublished projects must therefore never
appear in tracked files: a citation a reader cannot follow is worse than
no citation.  This guard makes regressions a test failure instead of a
review finding.
"""

import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]

# Names of pre-repo/unpublished projects that must not be referenced.
BANNED = (
    "electron_contactor",
    "electron_gun_probe",
    "electron_thruster/",   # path-style reference to the precursor tree
)

# Temporary exceptions, each with the action that retires it.  Empty since
# the collector.biased_3v.v2 re-gate run was promoted (2026-08-08).
ALLOWLIST: set[str] = set()

# This guard's own definition of the banned strings is not a violation.
SELF = "pic_sims/validation_cases/tests/test_publication_hygiene.py"


def _tracked_files() -> list[str]:
    out = subprocess.run(["git", "ls-files"], cwd=REPO, check=True,
                         capture_output=True, text=True).stdout
    return [line for line in out.splitlines() if line]


def test_no_external_project_references_in_tracked_files():
    offenders: list[str] = []
    for rel in _tracked_files():
        if rel in ALLOWLIST or rel == SELF:
            continue
        path = REPO / rel
        try:
            text = path.read_text(errors="ignore")
        except (OSError, IsADirectoryError):
            continue
        for name in BANNED:
            if name in text:
                offenders.append(f"{rel}: contains {name!r}")
                break
    assert not offenders, (
        "external project references in tracked files:\n  "
        + "\n  ".join(offenders))


def test_allowlist_entries_still_exist():
    """An allowlist entry for a deleted file is stale -- remove it."""
    for rel in ALLOWLIST:
        assert (REPO / rel).exists(), f"stale allowlist entry: {rel}"
