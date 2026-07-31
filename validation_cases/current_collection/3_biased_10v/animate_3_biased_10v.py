#!/usr/bin/env python3
"""Animate the 3_biased_10v current_collection case (thin wrapper, no arguments).

All physics lives in ../cc_common.py and inputs/3_biased_10v.yaml -- see the case
README.md for the theory targets and gates.  Usage::

    python animate_3_biased_10v.py
"""

import sys
from pathlib import Path

CASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(CASE_DIR.parent))

from cc_common import animate_case  # noqa: E402

if __name__ == "__main__":
    animate_case(CASE_DIR)
