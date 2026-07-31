#!/usr/bin/env python3
"""Run the 2_biased_3v current_collection case (thin wrapper, no arguments).

All physics lives in ../cc_common.py and inputs/2_biased_3v.yaml -- see the case
README.md for the theory targets and gates.  Usage::

    python run_2_biased_3v.py
"""

import sys
from pathlib import Path

CASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(CASE_DIR.parent))

from cc_common import run_case  # noqa: E402

if __name__ == "__main__":
    run_case(CASE_DIR)
