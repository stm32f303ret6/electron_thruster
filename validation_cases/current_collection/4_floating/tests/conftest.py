import sys
from pathlib import Path

STAGE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(STAGE_DIR.parents[1]))   # validation_cases/ (ladder_contract)
sys.path.insert(0, str(STAGE_DIR))              # this stage's helpers/analyze
