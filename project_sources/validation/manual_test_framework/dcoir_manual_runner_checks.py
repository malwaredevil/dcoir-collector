#!/usr/bin/env python3
"""Compatibility facade for manual collector test checks."""
from __future__ import annotations

from dcoir_manual_runner_checks_part_01 import (
    run_help_tests,
    classify_collect_note,
    run_validator,
    run_enrich_lifecycle,
    find_first_glob,
    safe_read_text,
    record_t2_pathway_note,
    run_negative_cases,
    compare_admin_nonadmin,
    run_full_regression,
    recheck_package,
)
from dcoir_manual_runner_checks_part_02 import (
    run_collect,
    run_review_surfaces,
    cleanup_transient_framework_artifacts,
    run_cleanup,
    final_signoff,
)
