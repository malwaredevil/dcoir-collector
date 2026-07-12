#!/usr/bin/env python3
"""Compatibility wrapper for the connector-safe DCOIR Review entrypoint."""

from __future__ import annotations

from pathlib import Path
import sys

_SCRIPT_DIR = Path(__file__).resolve().parent
if str(_SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPT_DIR))

from dcoir_review.entrypoint import main


if __name__ == "__main__":
    main()
