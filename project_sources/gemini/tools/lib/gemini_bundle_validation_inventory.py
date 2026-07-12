from __future__ import annotations

from pathlib import Path

from lib.gemini_bundle_validation_common import (
    DEFAULT_GENERATED_KNOWLEDGE_DIR,
    MANIFEST_NAME,
    generated_attachment_name,
)


def validate_required_files(
    manifest: dict,
    source_root: Path,
    checks: dict[str, object],
    errors: list[str],
) -> list[str]:
    required_files = manifest.get('required_files', [])
    source_required_files = list(manifest.get('source_required_files', []))
    missing_files = [rel for rel in required_files if not (source_root / rel).exists()]
    missing_source_required_files = [rel for rel in source_required_files if not (source_root / rel).exists()]
    checks['required_files_present'] = len(missing_files) == 0
    checks['missing_required_files'] = missing_files
    checks['source_required_files'] = source_required_files
    checks['source_required_files_present'] = len(missing_source_required_files) == 0
    checks['missing_source_required_files'] = missing_source_required_files
    if missing_files:
        errors.append('missing required source-root files: ' + ', '.join(missing_files))
    if missing_source_required_files:
        errors.append('missing source-required source-root files: ' + ', '.join(missing_source_required_files))
    return required_files


def validate_knowledge_inventory(
    manifest: dict,
    source_root: Path,
    repo_root: Path,
    required_files: list[str],
    checks: dict[str, object],
    errors: list[str],
) -> list[str]:
    generated_dir = manifest.get('generated_knowledge_attachment_dir', DEFAULT_GENERATED_KNOWLEDGE_DIR)
    knowledge_sources = sorted(manifest.get('knowledge_attachment_sources', []))
    discovered_sources = sorted(
        p.relative_to(repo_root).as_posix()
        for p in (repo_root / 'knowledge').glob('Knowledge - *.md')
        if p.is_file()
    )
    missing_sources = [rel for rel in knowledge_sources if not (repo_root / rel).exists()]
    unlisted_sources = [rel for rel in discovered_sources if rel not in knowledge_sources]
    stale_sources = [rel for rel in knowledge_sources if rel not in discovered_sources]
    knowledge_inventory_exact_match = not missing_sources and not unlisted_sources and not stale_sources
    checks['knowledge_manifest_source_field'] = 'knowledge_attachment_sources'
    checks['knowledge_manifest_source_count'] = len(knowledge_sources)
    checks['knowledge_discovered_source_count'] = len(discovered_sources)
    checks['knowledge_attachment_sources'] = knowledge_sources
    checks['discovered_knowledge_sources'] = discovered_sources
    checks['knowledge_source_inventory_exact_match'] = knowledge_inventory_exact_match
    checks['knowledge_inventory_authority_check'] = {
        'success': knowledge_inventory_exact_match,
        'manifest_field': 'knowledge_attachment_sources',
        'expected_glob': 'knowledge/Knowledge - *.md',
        'missing_knowledge_sources': missing_sources,
        'unlisted_knowledge_sources': unlisted_sources,
        'stale_manifest_knowledge_sources': stale_sources,
    }
    checks['missing_knowledge_sources'] = missing_sources
    checks['unlisted_knowledge_sources'] = unlisted_sources
    checks['stale_manifest_knowledge_sources'] = stale_sources
    if not knowledge_inventory_exact_match:
        errors.append('gemini knowledge-set authority check failed: manifest knowledge_attachment_sources must exactly match knowledge/Knowledge - *.md inventory')

    generated_dupes = [rel for rel in required_files if rel.startswith(f'{generated_dir}/Knowledge - ')]
    source_duplicate_files = sorted(
        p.relative_to(source_root).as_posix()
        for p in (source_root / generated_dir).glob('Knowledge - *.md.txt')
        if p.is_file()
    )
    checks['expected_generated_knowledge_attachments'] = sorted(f'{generated_dir}/{generated_attachment_name(rel)}' for rel in knowledge_sources)
    checks['manifest_has_no_generated_knowledge_duplicates'] = len(generated_dupes) == 0
    checks['source_tree_has_no_generated_knowledge_duplicates'] = len(source_duplicate_files) == 0
    checks['generated_knowledge_duplicates_in_manifest'] = generated_dupes
    checks['generated_knowledge_duplicates_in_source_tree'] = source_duplicate_files
    if generated_dupes:
        errors.append('manifest required_files still lists generated Knowledge attachment copies')
    if source_duplicate_files:
        errors.append('bundle_source still contains generated Knowledge attachment copies; delete them and let compile generate them from knowledge/')
    return knowledge_sources


def validate_operator_file_suffixes(
    source_root: Path,
    required_files: list[str],
    checks: dict[str, object],
    warnings: list[str],
) -> None:
    operator_files = [source_root / rel for rel in required_files if rel != MANIFEST_NAME]
    non_txt = [p.relative_to(source_root).as_posix() for p in operator_files if p.exists() and p.suffix != '.txt']
    checks['operator_facing_txt_suffixes'] = len(non_txt) == 0
    checks['non_txt_operator_files'] = non_txt
    if non_txt:
        warnings.append('some operator-facing files do not end with .txt: ' + ', '.join(non_txt))
