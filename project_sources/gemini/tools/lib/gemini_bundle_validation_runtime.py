from __future__ import annotations

import json
import re
from pathlib import Path

from lib.gemini_bundle_validation_common import (
    AGENT_DIR,
    ATTACHMENT_MAP,
    QUICK_START,
    RUNTIME_GOVERNANCE_LEAK_PATTERNS,
    VISIBILITY_CHECKS,
    gather_text,
    rel_posix,
)


def validate_runtime_surfaces(
    source_root: Path,
    repo_root: Path,
    topology: dict,
    prime_rel: str | None,
    sub_rel_list: list[str],
    knowledge_sources: list[str],
    checks: dict[str, object],
    errors: list[str],
    warnings: list[str],
) -> None:
    validate_attachment_map(source_root, knowledge_sources, checks, errors)
    validate_runtime_governance_leaks(source_root, topology, prime_rel, sub_rel_list, checks, errors)
    validate_visibility_markers(source_root, repo_root, knowledge_sources, checks, warnings)


def validate_attachment_map(
    source_root: Path,
    knowledge_sources: list[str],
    checks: dict[str, object],
    errors: list[str],
) -> None:
    attachment_map_path = source_root / ATTACHMENT_MAP
    attachment_map_text = attachment_map_path.read_text(encoding='utf-8', errors='ignore').lower() if attachment_map_path.exists() else ''
    map_missing_titles = [Path(rel).stem.lower() for rel in knowledge_sources if Path(rel).stem.lower() not in attachment_map_text]
    checks['attachment_map_mentions_all_knowledge_source_files'] = len(map_missing_titles) == 0
    checks['attachment_map_missing_titles'] = map_missing_titles
    if map_missing_titles:
        errors.append('attachment map does not mention every manifest-listed knowledge source file')


def validate_runtime_governance_leaks(
    source_root: Path,
    topology: dict,
    prime_rel: str | None,
    sub_rel_list: list[str],
    checks: dict[str, object],
    errors: list[str],
) -> None:
    runtime_source_rels = []
    if prime_rel:
        runtime_source_rels.append(prime_rel)
    runtime_source_rels.extend(sub_rel_list)
    runtime_source_rels.append(topology.get('generated_index_file', ''))
    runtime_source_rels.append(topology.get('quick_start_file', QUICK_START))
    runtime_source_rels.append(ATTACHMENT_MAP)
    runtime_source_paths = [source_root / rel for rel in runtime_source_rels if rel]
    runtime_governance_leaks = []
    for path in runtime_source_paths:
        if not path.exists() or not path.is_file():
            continue
        text = path.read_text(encoding='utf-8', errors='ignore')
        for name, pattern in RUNTIME_GOVERNANCE_LEAK_PATTERNS.items():
            if re.search(pattern, text):
                runtime_governance_leaks.append({
                    'file': rel_posix(path, source_root),
                    'pattern': name,
                })
    checks['runtime_governance_leak_check'] = len(runtime_governance_leaks) == 0
    checks['runtime_governance_leaks'] = runtime_governance_leaks
    if runtime_governance_leaks:
        errors.append('runtime-facing Gemini files contain builder/governance source references: ' + json.dumps(runtime_governance_leaks, sort_keys=True))


def validate_visibility_markers(
    source_root: Path,
    repo_root: Path,
    knowledge_sources: list[str],
    checks: dict[str, object],
    warnings: list[str],
) -> None:
    combined_paths = list((source_root / AGENT_DIR).glob('*.txt')) + [source_root / QUICK_START] + [repo_root / rel for rel in knowledge_sources]
    combined = gather_text(combined_paths).lower()
    for key, needles in VISIBILITY_CHECKS.items():
        present = all(needle in combined for needle in needles)
        checks[key] = present
        if not present:
            warnings.append(f'visibility check did not find all markers for {key}: {needles}')
