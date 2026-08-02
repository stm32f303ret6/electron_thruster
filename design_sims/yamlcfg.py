#!/usr/bin/env python3
r"""yamlcfg.py — YAML scenario loading shared by both simulation halves.

Two things live here because getting either one wrong is expensive and silent:

1. **The YAML 1.1 unsigned-exponent trap.** PyYAML implements YAML 1.1, whose
   float grammar requires a SIGNED exponent. `1.627e12` therefore parses as a
   STRING while `0.15e-3` parses as a float. A density that silently became a
   string is the kind of bug that surfaces six hours into a run.

2. **Strict merging.** An unknown key is a hard error. A config typo that
   silently does nothing costs a whole run to discover; a crash costs a second.

Stdlib + PyYAML only, so it imports in both conda environments.
"""

import copy
import re

try:
    import yaml
except ImportError as exc:  # pragma: no cover
    raise SystemExit(
        "yamlcfg needs PyYAML. Activate the project env or `pip install pyyaml`."
    ) from exc

_INT_RE = re.compile(r"^[-+]?\d+$")
_FLOAT_RE = re.compile(r"^[-+]?(\d+\.?\d*|\.\d+)([eE][-+]?\d+)?$")


def coerce_numbers(obj):
    """Recursively turn numeric-looking strings into int/float.

    Leaves real strings, bools and None untouched. See trap 1 above.
    """
    if isinstance(obj, dict):
        return {k: coerce_numbers(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [coerce_numbers(v) for v in obj]
    if isinstance(obj, str):
        if _INT_RE.match(obj):
            return int(obj)
        if _FLOAT_RE.match(obj):
            return float(obj)
    return obj


def deep_merge(base, override, path=""):
    """Recursively overlay `override` onto a copy of `base` (dicts only).

    Raises SystemExit naming the offending key path if `override` introduces a
    key `base` does not define. See trap 2 above.
    """
    out = copy.deepcopy(base)
    for k, v in (override or {}).items():
        where = f"{path}.{k}" if path else k
        if k not in out:
            raise SystemExit(
                f"config: unknown key '{where}' (typo? not in DEFAULTS). "
                f"Known keys here: {sorted(out)}")
        if isinstance(out[k], dict) and isinstance(v, dict):
            out[k] = deep_merge(out[k], v, where)
        else:
            out[k] = v
    return out


def _check_removed(user, removed):
    """Reject keys that once existed but were deliberately removed.

    `removed` maps a dotted path ('solar.endon_projection') to the message
    explaining the migration. Without this, a renamed key would die in
    deep_merge with a generic "typo?" -- wrong diagnosis for a semantic change.
    """
    for dotted, msg in (removed or {}).items():
        node = user
        for part in dotted.split("."):
            if not (isinstance(node, dict) and part in node):
                break
            node = node[part]
        else:
            raise SystemExit(f"config: '{dotted}' was removed. {msg}")


def load_merged(path, defaults, removed=None):
    """Read a scenario YAML and merge it over `defaults`. Returns the merged dict."""
    with open(path) as f:
        user = yaml.safe_load(f) or {}
    user = coerce_numbers(user)
    _check_removed(user, removed)
    return deep_merge(defaults, user)


def dump(obj, path):
    """Write the merged config verbatim beside the results, for reproducibility."""
    with open(path, "w") as f:
        yaml.safe_dump(obj, f, default_flow_style=False, sort_keys=False)
