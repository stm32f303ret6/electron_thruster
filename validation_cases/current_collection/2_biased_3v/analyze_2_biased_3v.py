#!/usr/bin/env python3
"""Analyze the 2_biased_3v current_collection case (thin wrapper, no arguments).

All physics lives in ../cc_common.py and inputs/2_biased_3v.yaml -- see the case
README.md for the theory targets and gates.  Exit code 0 = all gates pass.
Usage::

    python analyze_2_biased_3v.py
"""

import sys
from pathlib import Path

CASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(CASE_DIR.parent))

from cc_common import analyze_case  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(0 if analyze_case(CASE_DIR) else 1)
