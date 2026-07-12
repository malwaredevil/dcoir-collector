from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, MutableMapping

LAYER_SEGMENTS: dict[str, tuple[str, ...]] = {
    'base': (
        'base/part_01_core_config_github.py',
        'base/part_02_redaction_core.py',
        'base/part_03_redaction_shell.py',
        'base/part_04_debug_artifacts.py',
        'base/part_05_prompt_provider.py',
        'base/part_06_findings_comments.py',
        'base/part_07_main.py',
    ),
    'hardened': (
        'hardened/part_01_rules.py',
        'hardened/part_02_config_progress.py',
        'hardened/part_03_sentinels_prompt.py',
        'hardened/part_04_quality_provider.py',
        'hardened/part_05_debug_and_merge.py',
        'hardened/part_06_normalize_select.py',
        'hardened/part_07_review_body_main.py',
    ),
    'pareto_context': (
        'pareto_context/part_01_config_payload.py',
        'pareto_context/part_02_python_path_helpers.py',
        'pareto_context/part_03_python_diff_scope.py',
        'pareto_context/part_04_sentinels_modes_context.py',
        'pareto_context/part_05_ranking_per_file_review.py',
        'pareto_context/part_06_fix_synthesis.py',
        'pareto_context/part_07_deep_context_prompt.py',
        'pareto_context/part_08_review_body_main.py',
        'pareto_context/part_08a_review_body_main.py',
    ),
    'base_selftest': (
        'selftests/base_selftest/part_01.py',
        'selftests/base_selftest/part_02.py',
        'selftests/base_selftest/part_02a.py',
        'selftests/base_selftest/part_02b.py',
        'selftests/base_selftest/part_03.py',
    ),
    'hardened_selftest': (
        'selftests/hardened_selftest/part_01.py',
        'selftests/hardened_selftest/part_02.py',
    ),
    'pareto_context_selftest': (
        'selftests/pareto_context_selftest/part_01.py',
        'selftests/pareto_context_selftest/part_02.py',
        'selftests/pareto_context_selftest/part_03.py',
        'selftests/pareto_context_selftest/part_04.py',
        'selftests/pareto_context_selftest/part_05.py',
    ),
    'dcoir_review_runtime_patches': (
        'patches/dcoir_review_runtime_patches/part_01.py',
        'patches/dcoir_review_runtime_patches/part_02.py',
    ),
    'dcoir_review_strict_runtime_patches': (
        'patches/dcoir_review_strict_runtime_patches/part_01.py',
        'patches/dcoir_review_strict_runtime_patches/part_02.py',
    ),
    'dcoir_review_required_runtime_patches': (
        'patches/dcoir_review_required_runtime_patches/part_01.py',
        'patches/dcoir_review_required_runtime_patches/part_02.py',
    ),
    'dcoir_review_required_runtime_patch_v2': (
        'patches/dcoir_review_required_runtime_patch_v2/part_01.py',
        'patches/dcoir_review_required_runtime_patch_v2/part_02.py',
    ),
    'dcoir_review_required_runtime_patch_v3': (
        'patches/dcoir_review_required_runtime_patch_v3/part_01.py',
        'patches/dcoir_review_required_runtime_patch_v3/part_02.py',
    ),
    'dcoir_review_required_runtime_patch_v4_apply': (
        'patches/dcoir_review_required_runtime_patch_v4_apply/part_01.py',
    ),
    'dcoir_review_required_runtime_patch_v5_apply': (
        'patches/dcoir_review_required_runtime_patch_v5_apply/part_01.py',
    ),
    'dcoir_review_required_runtime_patch_v6': (
        'patches/dcoir_review_required_runtime_patch_v6/part_01.py',
        'patches/dcoir_review_required_runtime_patch_v6/part_02.py',
    ),
    'dcoir_review_required_runtime_patch_v7': (
        'patches/dcoir_review_required_runtime_patch_v7/part_01.py',
    ),
    'dcoir_review_required_runtime_patch_v8': (
        'patches/dcoir_review_required_runtime_patch_v8/part_01.py',
    ),
    'dcoir_review_required_runtime_patch_v9': (
        'patches/dcoir_review_required_runtime_patch_v9/part_01.py',
    ),
    'dcoir_review_required_runtime_patch_v10': (
        'patches/dcoir_review_required_runtime_patch_v10/part_01.py',
        'patches/dcoir_review_required_runtime_patch_v10/part_02.py',
    ),
    'dcoir_review_required_runtime_patch_v11': (
        'patches/dcoir_review_required_runtime_patch_v11/part_01.py',
        'patches/dcoir_review_required_runtime_patch_v11/part_02.py',
    ),
    'dcoir_review_required_runtime_patch_v12': (
        'patches/dcoir_review_required_runtime_patch_v12/part_01.py',
        'patches/dcoir_review_required_runtime_patch_v12/part_02.py',
    ),
    'dcoir_review_required_runtime_patch_v13': (
        'patches/dcoir_review_required_runtime_patch_v13/part_01.py',
        'patches/dcoir_review_required_runtime_patch_v13/part_01a.py',
        'patches/dcoir_review_required_runtime_patch_v13/part_02.py',
    ),
    'dcoir_review_required_runtime_patch_v15': (
        'patches/dcoir_review_required_runtime_patch_v15/part_01.py',
    ),
    'dcoir_review_required_runtime_patch_v14': (
        'patches/dcoir_review_required_runtime_patch_v14/part_01.py',
        'patches/dcoir_review_required_runtime_patch_v14/part_02.py',
    ),
    'dcoir_review_required_runtime_patch_v16': (
        'patches/dcoir_review_required_runtime_patch_v16/part_01.py',
        'patches/dcoir_review_required_runtime_patch_v16/part_02.py',
    ),
    'dcoir_review_required_runtime_patch_v17': (
        'patches/dcoir_review_required_runtime_patch_v17/part_01.py',
        'patches/dcoir_review_required_runtime_patch_v17/part_02.py',
    ),
    'dcoir_review_required_runtime_patch_v18': (
        'patches/dcoir_review_required_runtime_patch_v18/part_01.py',
    ),
    'dcoir_review_required_runtime_patch_v4': (
        'patches/dcoir_review_required_runtime_patch_v4/part_01.py',
        'patches/dcoir_review_required_runtime_patch_v4/part_02.py',
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
