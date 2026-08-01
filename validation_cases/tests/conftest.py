"""Put validation_cases/ on sys.path so `import ladder_contract` works when the
root tests are run from anywhere (pytest rootdir, the repo root, or CI)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
