#!/usr/bin/env python3
"""Compatibility facade for the DCOIR manual test framework runner."""
from __future__ import annotations

import sys

from dcoir_manual_runner_checks import *
from dcoir_manual_runner_context import *
from dcoir_manual_runner_flow import launch_admin_phase, main, top_level_failure
from dcoir_manual_runner_package import *


if __name__ == "__main__":
    sys.exit(main())