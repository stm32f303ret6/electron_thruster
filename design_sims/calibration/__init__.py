#!/usr/bin/env python3
r"""calibration/ — the PIC-measured constants the design side consumes.

THIS PACKAGE IS A LOADER, AND ITS OWN DIRECTORY IS THE LEDGER:

    calibration/laws.yaml      constants fitted ACROSS runs (only refit_laws.py writes it)
    calibration/runs/*.yaml    one promoted PIC measurement each (only promote.py writes these)

so a new PIC result is a `promote.py` invocation, not a hand edit of Python.

THE PROVENANCE RULE, ENFORCED HERE. Every constant in laws.yaml must carry an
``anchored_to`` path that resolves inside this repository plus the SHA-256 of the
file it names. A constant without that is rejected at load time with a
:class:`ProvenanceError` — not warned about, not defaulted. The predecessor's
laws.yaml said it out loud and then shipped anyway:

    "An entry without provenance is an assumption wearing a measurement's
     clothes."

Every constant it declared was anchored to a run that had been deleted. This
loader makes that state unloadable.

Depends on: PyYAML (+ the sibling yamlcfg for the YAML-1.1 float trap).
Imports in either conda environment.
"""

from __future__ import annotations

import hashlib
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

import yaml

CALIB_DIR = Path(__file__).resolve().parent
DESIGN_ROOT = CALIB_DIR.parent
REPO_ROOT = DESIGN_ROOT.parent

sys.path.insert(0, str(DESIGN_ROOT))
from yamlcfg import coerce_numbers  # noqa: E402


class ProvenanceError(ValueError):
    """A calibration entry that cannot prove where its number came from."""


#: Every constant laws.yaml must define, and the group it lives in.
REQUIRED_CONSTANTS: dict[str, tuple[str, ...]] = {
    "thrust": ("k", "k_ideal", "ke_ledger"),
    "beam": ("f_esc",),
    "collection": ("beta", "area_m2"),
    "body": ("capacitance_F",),
}

#: Constants that are REPORTED but never used to gate anything. `k_ideal` is
#: analytic, not measured, so it is the one entry exempt from the anchor rule.
ANALYTIC_CONSTANTS = frozenset({("thrust", "k_ideal")})


def sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def load_yaml(path: Path | str) -> dict:
    """Load a calibration YAML, coercing the YAML-1.1 unsigned-exponent trap.

    PyYAML implements YAML 1.1, whose float grammar requires a SIGNED exponent,
    so ``1.627e12`` parses as a STRING while ``1.627e+12`` parses as a float.
    Loading these files with a bare ``yaml.safe_load`` silently turns every
    density into text and the first arithmetic on it dies.
    """
    raw = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    return coerce_numbers(raw)


@dataclass(frozen=True)
class Anchor:
    """Where one constant's value came from, and proof the file still says so."""
    constant: str
    anchored_to: str          # repo-relative path
    metric: str               # which metric in that file
    sha256: str               # sha of the anchor file as recorded in laws.yaml

    def resolve(self, repo_root: Path = REPO_ROOT) -> Path:
        return repo_root / self.anchored_to

    def verify(self, repo_root: Path = REPO_ROOT) -> None:
        path = self.resolve(repo_root)
        if not path.is_file():
            raise ProvenanceError(
                f"constant '{self.constant}' is anchored to {self.anchored_to}, "
                f"which does not exist. A constant whose evidence has been "
                f"deleted is an assumption wearing a measurement's clothes.")
        actual = sha256_of(path)
        if actual != self.sha256:
            raise ProvenanceError(
                f"constant '{self.constant}': {self.anchored_to} has changed "
                f"(sha256 {actual[:12]}... != recorded {self.sha256[:12]}...). "
                f"Re-promote and re-fit; do not edit laws.yaml by hand.")


@dataclass(frozen=True)
class Laws:
    """The loaded constants, flat and typed, plus their anchors.

    Units are the ones the formulas below use, and they are NOT all SI:
      k             nN / (mA * sqrt(eV))    thrust-law coefficient
      ke_ledger     -                       fraction of (V - phi) the beam keeps
      f_esc         -                       escaping fraction of the emitted beam
      beta          -                       return-law collection efficiency
      area_m2       m^2                     the can's conducting hull area
      capacitance_F F                       float-node self-capacitance
    """
    k: float
    k_ideal: float
    ke_ledger: float
    f_esc: float
    beta: float
    area_m2: float
    capacitance_F: float
    anchors: tuple[Anchor, ...] = ()
    sha256: str = ""
    path: str = ""

    def describe(self) -> str:
        lines = [
            f"laws.yaml @ {self.sha256[:12]}  ({self.path})",
            f"  thrust      F[nN] = {self.k:.4f} * I[mA] * sqrt(KE),  "
            f"KE = {self.ke_ledger:.4f} * (V - phi)   [ideal k = {self.k_ideal:.4f}]",
            f"  escape      f_esc = {self.f_esc:.4f}",
            f"  collection  I_ret = {self.beta:.4f} * I_the(n,Te) * (1 + e*phi/kTe),  "
            f"A = {self.area_m2*1e4:.4f} cm^2",
            f"  body        C = {self.capacitance_F*1e12:.4f} pF (advisory: settle time)",
        ]
        for a in self.anchors:
            lines.append(f"    {a.constant:<24s} <- {a.metric} @ {a.anchored_to}")
        return "\n".join(lines)


def _anchors_from(raw: Mapping[str, Any], prov_raw: Mapping[str, Any]) -> tuple[Anchor, ...]:
    """Build and verify one Anchor per required constant.

    A constant is anchored by a per-group ``provenance`` block:

        thrust:
          k: 3.2864
          provenance:
            k: {anchored_to: ..., metric: ..., sha256: ...}

    ``prov_raw`` is the SAME document loaded WITHOUT numeric coercion. A sha256
    is a hex string that can legally be all digits, and coercing it to an int
    would silently drop its leading zeros — so provenance is read from the
    uncoerced copy while the constants come from the coerced one.
    """
    out: list[Anchor] = []
    for group, names in REQUIRED_CONSTANTS.items():
        block = raw.get(group)
        if not isinstance(block, Mapping):
            raise ProvenanceError(f"laws.yaml has no '{group}' group")
        prov_block = prov_raw.get(group)
        prov = (prov_block.get("provenance") if isinstance(prov_block, Mapping)
                else None) or {}
        for name in names:
            if name not in block:
                raise ProvenanceError(f"laws.yaml: {group}.{name} is missing")
            if (group, name) in ANALYTIC_CONSTANTS:
                continue
            entry = prov.get(name)
            if not isinstance(entry, Mapping):
                raise ProvenanceError(
                    f"laws.yaml: {group}.{name} has no provenance entry. Every "
                    f"constant must name the in-tree artifact it was measured "
                    f"from; refit_laws.py writes these.")
            for key in ("anchored_to", "metric", "sha256"):
                value = entry.get(key)
                if value is None or str(value).strip() == "":
                    raise ProvenanceError(
                        f"laws.yaml: {group}.{name} provenance is missing '{key}'")
            out.append(Anchor(constant=f"{group}.{name}",
                              anchored_to=str(entry["anchored_to"]),
                              metric=str(entry["metric"]),
                              sha256=str(entry["sha256"])))
    return tuple(out)


def load_laws(path: Path | str | None = None, *, verify: bool = True,
              repo_root: Path | None = None) -> Laws:
    """Load laws.yaml, refusing any constant that cannot prove its origin.

    ``verify=False`` skips only the on-disk sha/existence check (useful in unit
    tests that build a laws file from scratch); the structural requirement that
    every constant carries a provenance entry is NOT optional.
    """
    path = Path(path) if path is not None else CALIB_DIR / "laws.yaml"
    if not path.is_file():
        raise ProvenanceError(
            f"no calibration laws at {path}. Run promote.py then refit_laws.py; "
            f"laws.yaml is generated, never hand-written.")
    text = path.read_text(encoding="utf-8")
    prov_raw = yaml.safe_load(text) or {}     # uncoerced: shas stay strings
    raw = coerce_numbers(prov_raw)
    anchors = _anchors_from(raw, prov_raw)
    if verify:
        root = repo_root if repo_root is not None else REPO_ROOT
        for a in anchors:
            a.verify(root)
    return Laws(
        k=float(raw["thrust"]["k"]),
        k_ideal=float(raw["thrust"]["k_ideal"]),
        ke_ledger=float(raw["thrust"]["ke_ledger"]),
        f_esc=float(raw["beam"]["f_esc"]),
        beta=float(raw["collection"]["beta"]),
        area_m2=float(raw["collection"]["area_m2"]),
        capacitance_F=float(raw["body"]["capacitance_F"]),
        anchors=anchors, sha256=sha256_of(path), path=str(path))


def load_runs(runs_dir: Path | str | None = None) -> dict[str, dict]:
    """Every promoted measurement record, keyed by file stem."""
    d = Path(runs_dir) if runs_dir is not None else CALIB_DIR / "runs"
    if not d.is_dir():
        return {}
    return {p.stem: load_yaml(p) for p in sorted(d.glob("*.yaml"))}


if __name__ == "__main__":
    print(load_laws().describe())
    for name, rec in sorted(load_runs().items()):
        m = rec.get("measured", {})
        print(f"  run [{rec.get('status', '?')}] {name}: "
              f"phi {m.get('phi_body_V', float('nan')):+.2f} V, "
              f"F {m.get('f_beam_nN', float('nan')):.2f} nN, "
              f"escape {m.get('escape_pct', float('nan')):.2f} %")
