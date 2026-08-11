"""Put this stage's directory and the shared plumbing root (pic_sims/) on sys.path."""

import sys
from pathlib import Path

STAGE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(STAGE_DIR))
sys.path.insert(0, str(STAGE_DIR.parents[2] / "pic_sims"))  # shared plumbing (ladder_contract)