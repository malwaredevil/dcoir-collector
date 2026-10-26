#!/usr/bin/env python3
"""Compatibility entrypoint for existing issue-428 GitHub Actions job."""
from __future__ import annotations

# Preserve direct, importlib and runpy use from any working directory.
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from openai_gpt_release_version_selftest import main

if __name__ == "__main__":
    raise SystemExit(main())
