"""Put design_sims/ on sys.path so the flat modules import from any cwd."""

import sys
from pathlib import Path

DESIGN_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(DESIGN_ROOT))
