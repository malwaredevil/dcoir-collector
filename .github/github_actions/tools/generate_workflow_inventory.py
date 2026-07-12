#!/usr/bin/env python3
"""Compatibility wrapper for the issue #194 workflow inventory generator.

The canonical implementation is `build_workflow_inventory.py`. This wrapper
keeps the more obvious "generate" command name available without creating a
second inventory format.
"""
from __future__ import annotations

import sys

from build_workflow_inventory import main


if __name__ == "__main__":
    sys.exit(main())
