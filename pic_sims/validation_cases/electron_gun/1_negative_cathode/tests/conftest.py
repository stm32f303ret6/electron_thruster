"""Put this stage's directory and validation_cases/ on sys.path so the stage's
helpers.py / analyze.py and the shared ladder_contract import cleanly."""

import sys
from pathlib import Path

STAGE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(STAGE_DIR))                 # helpers.py, analyze.py
sys.path.insert(0, str(STAGE_DIR.parents[1]))      # validation_cases/
