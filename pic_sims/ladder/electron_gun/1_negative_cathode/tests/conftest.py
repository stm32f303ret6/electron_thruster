"""Put this stage's directory and the shared plumbing root (pic_sims/)  on sys.path so the stage's
helpers.py / analyze.py and the shared ladder_contract import cleanly."""

import sys
from pathlib import Path

STAGE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(STAGE_DIR))                 # helpers.py, analyze.py
_pic_root = STAGE_DIR  # walk up to pic_sims/ (ladder_contract, shared plumbing)
while not (_pic_root / "ladder_contract.py").is_file():
    _pic_root = _pic_root.parent
sys.path.insert(0, str(_pic_root))
