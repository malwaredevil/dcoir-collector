#!/usr/bin/env python3
"""Fixture-based detector checks for the LogRaw metadata policy."""
from __future__ import annotations

from event_text_query_bound_common import (
    extract_powershell_command_spans,
    powershell_command_span_avoids_count_cap_and_splatting,
    powershell_command_span_detects_count_cap,
    powershell_command_uses_count_cap_parameter,
    powershell_command_uses_splatting,
)
from event_text_query_bound_lograw_fixtures import (
    command_anchor_benign_fixtures,
    command_case_negative_fixtures,
    command_separator_benign_fixtures,
    export_colon_parameter_negative_fixtures,
    export_implicit_continuation_benign_fixtures,
    export_implicit_continuation_negative_fixtures,
    export_implicit_continuation_splat_negative_fixtures,
    export_splat_negative_fixtures,
    target_detail_colon_parameter_negative_fixtures,
    target_detail_implicit_continuation_benign_fixtures,
    target_detail_implicit_continuation_negative_fixtures,
    target_detail_implicit_continuation_splat_negative_fixtures,
    target_detail_multiline_negative_fixtures,
    target_detail_negative_fixtures,
    target_detail_parameter_prefix_negative_fixtures,
    target_detail_splat_negative_fixtures,
)


def evaluate_lograw_fixture_checks() -> dict[str, bool]:
    """Return detector truth values for negative and benign fixture families."""
    target_negative = (
        target_detail_negative_fixtures
        + target_detail_multiline_negative_fixtures
        + target_detail_parameter_prefix_negative_fixtures
        + target_detail_colon_parameter_negative_fixtures
        + target_detail_implicit_continuation_negative_fixtures
    )
    return {
        "target_detail_negative_fixtures_detect_count_cap": all(
            powershell_command_uses_count_cap_parameter(fixture) for fixture in target_negative
        ),
        "target_detail_multiline_negative_fixtures_detect_count_cap": all(
            powershell_command_uses_count_cap_parameter(fixture)
            for fixture in target_detail_multiline_negative_fixtures
        ),
        "target_detail_parameter_prefix_negative_fixtures_detect_count_cap": all(
            powershell_command_uses_count_cap_parameter(fixture)
            for fixture in target_detail_parameter_prefix_negative_fixtures
        ),
        "target_detail_colon_parameter_negative_fixtures_detect_count_cap": all(
            powershell_command_uses_count_cap_parameter(fixture)
            for fixture in target_detail_colon_parameter_negative_fixtures
        ),
        "target_detail_implicit_continuation_negative_fixtures_detect_count_cap": all(
            powershell_command_uses_count_cap_parameter(fixture)
            for fixture in target_detail_implicit_continuation_negative_fixtures
        ),
        "target_detail_implicit_continuation_benign_fixtures_avoid_false_positives": all(
            not powershell_command_uses_count_cap_parameter(fixture)
            and not powershell_command_uses_splatting(fixture)
            for fixture in target_detail_implicit_continuation_benign_fixtures
        ),
        "target_detail_splat_negative_fixtures_reject_splatting": all(
            powershell_command_uses_splatting(fixture)
            for fixture in target_detail_splat_negative_fixtures
        ),
        "target_detail_implicit_continuation_splat_negative_fixtures_reject_splatting": all(
            powershell_command_uses_splatting(fixture)
            for fixture in target_detail_implicit_continuation_splat_negative_fixtures
        ),
        "export_splat_negative_fixtures_reject_splatting": all(
            powershell_command_uses_splatting(fixture) for fixture in export_splat_negative_fixtures
        ),
        "export_implicit_continuation_negative_fixtures_detect_count_cap": all(
            powershell_command_uses_count_cap_parameter(fixture)
            for fixture in export_implicit_continuation_negative_fixtures
        ),
        "export_colon_parameter_negative_fixtures_detect_count_cap": all(
            powershell_command_uses_count_cap_parameter(fixture)
            for fixture in export_colon_parameter_negative_fixtures
        ),
        "export_implicit_continuation_benign_fixtures_avoid_false_positives": all(
            not powershell_command_uses_count_cap_parameter(fixture)
            and not powershell_command_uses_splatting(fixture)
            for fixture in export_implicit_continuation_benign_fixtures
        ),
        "export_implicit_continuation_splat_negative_fixtures_reject_splatting": all(
            powershell_command_uses_splatting(fixture)
            for fixture in export_implicit_continuation_splat_negative_fixtures
        ),
        "command_anchor_benign_fixtures_avoid_false_positives": all(
            not extract_powershell_command_spans(fixture, command)
            for fixture, command in command_anchor_benign_fixtures
        ),
        "command_separator_benign_fixtures_avoid_false_positives": all(
            powershell_command_span_avoids_count_cap_and_splatting(fixture, command)
            for fixture, command in command_separator_benign_fixtures
        ),
        "command_case_negative_fixtures_detect_count_cap": all(
            powershell_command_span_detects_count_cap(fixture, command)
            for fixture, command in command_case_negative_fixtures
        ),
    }
