import sys
from pathlib import Path

STAGE_DIR = Path(__file__).resolve().parents[1]
_pic_root = STAGE_DIR  # walk up to pic_sims/ (ladder_contract, shared plumbing)
while not (_pic_root / "ladder_contract.py").is_file():
    _pic_root = _pic_root.parent
sys.path.insert(0, str(_pic_root))
sys.path.insert(0, str(STAGE_DIR))              # this stage's helpers/analyze
