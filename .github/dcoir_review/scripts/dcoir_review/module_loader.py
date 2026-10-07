from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, MutableMapping

LAYER_SEGMENTS: dict[str, tuple[str, ...]] = {
    'base': (
        'base/part_01_core_config_github.py',
        'base/part_01a_progress_diff.py',
        'base/part_02_redaction_core.py',
        'base/part_03_redaction_shell.py',
        'base/part_03a_redaction_command_shell.py',
        'base/part_04_debug_artifacts.py',
        'base/part_05_prompt_provider.py',
        'base/part_06_findings_comments.py',
        'base/part_06a_finding_validation.py',
        'base/part_06b_guidance_code.py',
        'base/part_07_main.py',
    ),
    'hardened': (
        'hardened/part_01_rules.py',
        'hardened/part_01a_finding_rules.py',
        'hardened/part_02_config_progress.py',
        'hardened/part_03_sentinels_prompt.py',
        'hardened/part_03a_fallback_prompt.py',
        'hardened/part_04_quality_provider.py',
        'hardened/part_04a_provider.py',
        'hardened/part_04b_provider_request.py',
        'hardened/part_05_debug_and_merge.py',
        'hardened/part_06_normalize_select.py',
        'hardened/part_07_review_body_main.py',
    ),
    'pareto_context': (
        'pareto_context/part_01_config_payload.py',
        'pareto_context/part_01a_python_call_helpers.py',
        'pareto_context/part_01b_python_binding_helpers.py',
        'pareto_context/part_02_python_path_helpers.py',
        'pareto_context/part_02a_python_urlopen_helpers.py',
        'pareto_context/part_02b_python_write_helpers.py',
        'pareto_context/part_03_python_diff_scope.py',
        'pareto_context/part_03c_file_write_helpers.py',
        'pareto_context/part_03d_file_write_scan_helpers.py',
        'pareto_context/part_04_sentinels_modes_context.py',
        'pareto_context/part_04a_ranking_context.py',
        'pareto_context/part_04b_sentinel_dispatch.py',
        'pareto_context/part_04b1_python_urlopen_scope.py',
        'pareto_context/part_04b2_python_sentinel_helpers.py',
        'pareto_context/part_04c_review_context.py',
        'pareto_context/part_05_ranking_per_file_review.py',
        'pareto_context/part_05a_hybrid_review.py',
        'pareto_context/part_06_fix_synthesis.py',
        'pareto_context/part_07a0_python_scope_bindings.py',
        'pareto_context/part_07a1_python_scope_state_helpers.py',
        'pareto_context/part_07a2_python_scope_restoration.py',
        'pareto_context/part_07a_python_scope_context.py',
        'pareto_context/part_07_deep_context_prompt.py',
        'pareto_context/part_08_review_body_main.py',
        'pareto_context/part_08a_review_body_main.py',
    ),
    'base_selftest': (
        'selftests/base_selftest/part_01.py',
        'selftests/base_selftest/part_01a.py',
        'selftests/base_selftest/part_02.py',
        'selftests/base_selftest/part_02a.py',
        'selftests/base_selftest/part_02b.py',
        'selftests/base_selftest/part_03.py',
    ),
    'hardened_selftest': (
        'selftests/hardened_selftest/part_01.py',
        'selftests/hardened_selftest/part_01a.py',
        'selftests/hardened_selftest/part_02.py',
    ),
    'pareto_context_selftest': (
        'selftests/pareto_context_selftest/part_01.py',
        'selftests/pareto_context_selftest/part_01a.py',
        'selftests/pareto_context_selftest/part_02.py',
        'selftests/pareto_context_selftest/part_03.py',
        'selftests/pareto_context_selftest/part_03a.py',
        'selftests/pareto_context_selftest/part_03b_fixtures.py',
        'selftests/pareto_context_selftest/part_03c_os_open_regressions.py',
        'selftests/pareto_context_selftest/part_04.py',
        'selftests/pareto_context_selftest/part_04a.py',
        'selftests/pareto_context_selftest/part_04b.py',
        'selftests/pareto_context_selftest/part_04c_scope_regressions.py',
        'selftests/pareto_context_selftest/part_04d_scope_statement_regressions.py',
        'selftests/pareto_context_selftest/part_05.py',
    ),
    'dcoir_review_required_runtime_patch_v14_selftest': (
        'selftests/dcoir_review_required_runtime_patch_v14_selftest/part_01.py',
        'selftests/dcoir_review_required_runtime_patch_v14_selftest/part_02.py',
    ),
    'dcoir_review_required_runtime_patch_v9_selftest': (
        'selftests/dcoir_review_required_runtime_patch_v9_selftest/part_01.py',
        'selftests/dcoir_review_required_runtime_patch_v9_selftest/part_02.py',
    ),
    'openrouter_pr_review_pareto_context_regression_selftest': (
        'selftests/openrouter_pr_review_pareto_context_regression_selftest/part_01.py',
        'selftests/openrouter_pr_review_pareto_context_regression_selftest/part_02.py',
        'selftests/openrouter_pr_review_pareto_context_regression_selftest/part_02a.py',
    ),
    'dcoir_review_runtime_patches': (
        'patches/dcoir_review_runtime_patches/part_01.py',
        'patches/dcoir_review_runtime_patches/part_01a.py',
        'patches/dcoir_review_runtime_patches/part_02.py',
        'patches/dcoir_review_runtime_patches/part_02a.py',
    ),
    'dcoir_review_strict_runtime_patches': (
        'patches/dcoir_review_strict_runtime_patches/part_01.py',
        'patches/dcoir_review_strict_runtime_patches/part_01a.py',
        'patches/dcoir_review_strict_runtime_patches/part_02.py',
        'patches/dcoir_review_strict_runtime_patches/part_02a.py',
    ),
    'dcoir_review_required_runtime_patches': (
        'patches/dcoir_review_required_runtime_patches/part_01.py',
        'patches/dcoir_review_required_runtime_patches/part_01a.py',
        'patches/dcoir_review_required_runtime_patches/part_02.py',
        'patches/dcoir_review_required_runtime_patches/part_02a.py',
    ),
    'dcoir_review.required_coverage_primitives': (
        'required_coverage_primitives_parts/part_01.py',
        'required_coverage_primitives_parts/part_01a.py',
        'required_coverage_primitives_parts/part_02.py',
    ),
    'dcoir_review.risk_sentinel_identity': (
        'risk_sentinel_identity_parts/part_01.py',
        'risk_sentinel_identity_parts/part_01a.py',
        'risk_sentinel_identity_parts/part_02.py',
    ),
    'dcoir_review.risk_sentinel_policy': (
        'risk_sentinel_policy_parts/part_01.py',
        'risk_sentinel_policy_parts/part_02.py',
    ),
    'dcoir_review.prompt_review_policy': (
        'prompt_review_policy_parts/part_01.py',
        'prompt_review_policy_parts/part_01a.py',
        'prompt_review_policy_parts/part_02.py',
    ),
    'dcoir_review.required_selection_policy': (
        'required_selection_policy_parts/part_01.py',
        'required_selection_policy_parts/part_01a.py',
    ),
    'dcoir_review.selection_pressure_policy': (
        'selection_pressure_policy_parts/part_01.py',
        'selection_pressure_policy_parts/part_01a.py',
    ),
    'dcoir_review.risk_sentinel_composition': (
        'risk_sentinel_composition_parts/part_01.py',
    ),
    'dcoir_review.risk_sentinel_state': (
        'risk_sentinel_state_parts/part_01.py',
        'risk_sentinel_state_parts/part_02.py',
    ),
    'dcoir_review.risk_sentinel_selection_support': (
        'risk_sentinel_selection_support_parts/part_01.py',
        'risk_sentinel_selection_support_parts/part_02.py',
    ),
    'dcoir_review.workflow_risk_semantics': (
        'workflow_risk_semantics_parts/part_01.py',
        'workflow_risk_semantics_parts/part_01a.py',
        'workflow_risk_semantics_parts/part_02.py',
    ),
    'dcoir_review.python_k8s_risk_semantics': (
        'python_k8s_risk_semantics_parts/part_01.py',
        'python_k8s_risk_semantics_parts/part_01a.py',
        'python_k8s_risk_semantics_parts/part_02.py',
        'python_k8s_risk_semantics_parts/part_02a.py',
    ),
    'dcoir_review.required_selection_semantics': (
        'required_selection_semantics_parts/part_01.py',
        'required_selection_semantics_parts/part_02.py',
    ),
    'dcoir_review.extended_risk_semantics': (
        'extended_risk_semantics_parts/part_01.py',
        'extended_risk_semantics_parts/part_01a.py',
        'extended_risk_semantics_parts/part_02.py',
        'extended_risk_semantics_parts/part_02a.py',
    ),
    'dcoir_review.finding_integrity_policy': (
        'finding_integrity_policy_parts/part_01.py',
        'finding_integrity_policy_parts/part_01a.py',
        'finding_integrity_policy_parts/part_02.py',
    ),
    'dcoir_review.risk_sentinel_primitives': (
        'risk_sentinel_primitives_parts/part_01.py',
        'risk_sentinel_primitives_parts/part_01a.py',
        'risk_sentinel_primitives_parts/part_01b.py',
        'risk_sentinel_primitives_parts/part_01b1.py',
        'risk_sentinel_primitives_parts/part_01c.py',
        'risk_sentinel_primitives_parts/part_02.py',
        'risk_sentinel_primitives_parts/part_02a.py',
    ),
    'dcoir_review.risk_sentinel_taxonomy': (
        'risk_sentinel_taxonomy_parts/part_01.py',
        'risk_sentinel_taxonomy_parts/part_01a.py',
        'risk_sentinel_taxonomy_parts/part_02.py',
    ),
}


@dataclass(frozen=True)
class RuntimeSegmentLoader:
    layer: str
    root: Path = Path(__file__).resolve().parent

    def segment_paths(self) -> tuple[Path, ...]:
        try:
            relatives = LAYER_SEGMENTS[self.layer]
        except KeyError as exc:
            raise KeyError(f"unknown DCOIR Review runtime layer: {self.layer}") from exc
        return tuple(self.root / relative for relative in relatives)

    def load_into(self, namespace: MutableMapping[str, Any]) -> None:
        for path in self.segment_paths():
            source = path.read_text(encoding="utf-8")
            exec(compile(source, str(path), "exec"), namespace)


def load_segments_into(namespace: MutableMapping[str, Any], layer: str) -> None:
    RuntimeSegmentLoader(layer).load_into(namespace)
