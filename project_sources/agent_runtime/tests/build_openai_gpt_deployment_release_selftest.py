#!/usr/bin/env python3
"""Compatibility entrypoint for the existing OpenAI release GitHub workflow.

Run all independent responsibility suites without executing another main().
The workflow path remains unchanged until separately authorized.
"""
from __future__ import annotations

# Support direct scripts, importlib and runpy callers from other working dirs.
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))

import json

from openai_gpt_release_payload_selftest import (
    test_combined_delivery_and_determinism,
    test_cross_checkout_root_determinism,
    test_human_markdown_tracks_json_and_instructions,
    test_knowledge_drift_fails_closed,
    test_parity_failure_blocks_release,
    test_source_commit_mismatch_blocks_release,
)

from openai_gpt_release_webui_limits_selftest import (
    test_description_limit_fails_closed,
    test_instruction_limit_fails_closed,
    test_package_manifest_integer_type_drift_fails_closed,
    test_stage_target_uses_webui_safe_counts_for_non_bmp,
    test_non_bmp_description_uses_webui_safe_counting,
    test_lone_surrogate_description_fails_closed_without_crash,
)

from openai_gpt_release_paths_selftest import (
    test_unsafe_existing_delivery_root_fails_closed,
    test_existing_delivery_root_symlink_fails_closed_when_supported,
    test_copy_record_rejects_destination_escape,
    test_copy_record_rejects_symlink_source_when_supported,
    test_repo_source_resolver_rejects_symlink_component_when_supported,
    test_deterministic_zip_rejects_symlinked_delivery_file_when_supported,
    test_existing_report_output_directory_fails_closed,
    test_existing_zip_output_directory_fails_closed,
    test_output_leaf_symlink_fails_closed_when_supported,
    test_output_escape_is_rejected,
)

from openai_gpt_release_manifest_selftest import (
    test_governed_runtime_model_source_and_package_must_agree,
    test_release_source_manifest_invalid_values_fail_before_writing,
    test_release_knowledge_count_and_cross_manifest_integrity,
)


TESTS = (
    test_combined_delivery_and_determinism,
    test_governed_runtime_model_source_and_package_must_agree,
    test_release_source_manifest_invalid_values_fail_before_writing,
    test_release_knowledge_count_and_cross_manifest_integrity,
    test_cross_checkout_root_determinism,
    test_description_limit_fails_closed,
    test_instruction_limit_fails_closed,
    test_package_manifest_integer_type_drift_fails_closed,
    test_stage_target_uses_webui_safe_counts_for_non_bmp,
    test_non_bmp_description_uses_webui_safe_counting,
    test_lone_surrogate_description_fails_closed_without_crash,
    test_human_markdown_tracks_json_and_instructions,
    test_knowledge_drift_fails_closed,
    test_parity_failure_blocks_release,
    test_source_commit_mismatch_blocks_release,
    test_unsafe_existing_delivery_root_fails_closed,
    test_existing_delivery_root_symlink_fails_closed_when_supported,
    test_copy_record_rejects_destination_escape,
    test_copy_record_rejects_symlink_source_when_supported,
    test_repo_source_resolver_rejects_symlink_component_when_supported,
    test_deterministic_zip_rejects_symlinked_delivery_file_when_supported,
    test_existing_report_output_directory_fails_closed,
    test_existing_zip_output_directory_fails_closed,
    test_output_leaf_symlink_fails_closed_when_supported,
    test_output_escape_is_rejected,
)

def main() -> int:
    for test in TESTS:
        test()
    print(json.dumps({"success": True, "tests": [test.__name__ for test in TESTS]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
