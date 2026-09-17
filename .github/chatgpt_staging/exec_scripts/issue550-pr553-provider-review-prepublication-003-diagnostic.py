from __future__ import annotations

import runpy
import sys
import traceback
from pathlib import Path

VALIDATOR = Path(__file__).with_name(
    "issue550-pr553-provider-review-prepublication-002.py"
)

try:
    runpy.run_path(str(VALIDATOR), run_name="__main__")
except BaseException as exc:
    frames = traceback.extract_tb(exc.__traceback__)
    validator_lines = [
        frame.lineno
        for frame in frames
        if Path(frame.filename).name == VALIDATOR.name and frame.lineno >= 480
    ]
    line = validator_lines[0] if validator_lines else 199
    sys.exit(line)

sys.exit(0)
