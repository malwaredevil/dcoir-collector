from __future__ import annotations

from pathlib import Path

from lib.gemini_bundle_validation_common import (
    AGENT_DIR,
    markdown_heading_or_label_count,
    rel_posix,
)
from lib.gemini_prime_agent_chunks import (
    PrimeChunkPlanError,
    assemble,
    load_chunk_plan,
    sha256_text,
)


def validate_topology(
    manifest: dict,
    source_root: Path,
    checks: dict[str, object],
    errors: list[str],
    warnings: list[str],
) -> tuple[dict, str | None, list[str]]:
    topology = manifest.get('topology', {})
    prime_rel = topology.get('prime_agent_file')
    sub_rel_list = list(topology.get('sub_agent_files', []))
    prime_source_mode = manifest.get('prime_agent_source_mode')
    prime_runtime_mode = manifest.get('prime_agent_runtime_mode')
    runtime_generated_files = list(manifest.get('runtime_generated_files', []))
    source_only_files = set(manifest.get('source_only_files', []))
    source_only_dirs = set(manifest.get('source_only_dirs', []))

    checks['topology_source'] = topology.get('topology_source_of_truth', 'missing')
    checks['manifest_prime_agent_file'] = prime_rel
    checks['manifest_sub_agent_files'] = sub_rel_list
    checks['manifest_sub_agent_count'] = len(sub_rel_list)
    checks['prime_agent_source_mode'] = prime_source_mode
    checks['prime_agent_runtime_mode'] = prime_runtime_mode
    checks['runtime_generated_files'] = runtime_generated_files
    checks['source_only_files'] = sorted(source_only_files)
    checks['source_only_dirs'] = sorted(source_only_dirs)

    discovered_prime = sorted(rel_posix(p, source_root) for p in (source_root / AGENT_DIR).glob('Prime_Agent_*.txt') if p.is_file())
    discovered_sub = sorted(rel_posix(p, source_root) for p in (source_root / AGENT_DIR).glob('Sub_Agent_*.txt') if p.is_file())
    checks['discovered_prime_files'] = discovered_prime
    checks['discovered_sub_agent_files'] = discovered_sub
    checks['discovered_sub_agent_count'] = len(discovered_sub)

    if prime_source_mode == 'chunked_reassembled' and prime_runtime_mode == 'generated_from_chunks':
        allowed_prime = discovered_prime in ([], [prime_rel])
        if not allowed_prime:
            errors.append('chunked prime agent mode allows zero or one generated canonical prime file only')
        if prime_rel not in runtime_generated_files:
            errors.append('runtime_generated_files must include manifest topology prime_agent_file in chunked mode')
    else:
        allowed_prime = bool(prime_rel and discovered_prime == [prime_rel])
        if prime_rel and discovered_prime != [prime_rel]:
            errors.append('prime agent file discovered in source tree does not match manifest topology')
    if sorted(sub_rel_list) != discovered_sub:
        errors.append('discovered sub-agent files do not exactly match manifest topology')
    checks['topology_exact_match'] = bool(prime_rel and allowed_prime and sorted(sub_rel_list) == discovered_sub)

    if prime_source_mode == 'chunked_reassembled':
        validate_chunked_prime_agent(manifest, source_root, prime_rel, checks, errors)
    elif prime_source_mode not in (None, 'single_file'):
        warnings.append('unrecognized prime_agent_source_mode: ' + str(prime_source_mode))

    return topology, prime_rel, sub_rel_list


def validate_chunked_prime_agent(
    manifest: dict,
    source_root: Path,
    prime_rel: str | None,
    checks: dict[str, object],
    errors: list[str],
) -> None:
    chunk_manifest_rel = manifest.get('prime_agent_chunk_manifest')
    checks['prime_agent_chunk_manifest'] = chunk_manifest_rel
    # The reassembler and this validator share one chunk-plan owner, so the
    # binding, containment and sha256 integrity rules cannot drift apart.
    try:
        plan = load_chunk_plan(manifest, source_root)
        assembled = assemble(plan)
    except PrimeChunkPlanError as exc:
        checks['prime_agent_chunk_integrity'] = False
        errors.append(f'prime agent chunk reassembly failed: {exc}')
        return
    checks['prime_agent_chunk_integrity'] = True
    checks['prime_agent_chunk_count'] = len(plan.chunks)
    checks['prime_agent_reassembled_sha256'] = sha256_text(assembled)

    canonical_path = source_root / prime_rel if prime_rel else None
    canonical_exists = bool(canonical_path and canonical_path.is_file())
    checks['prime_agent_generated_canonical_exists'] = canonical_exists
    if canonical_exists:
        canonical = canonical_path.read_text(encoding='utf-8', errors='replace')
        checks['prime_agent_chunk_reassembly_matches_canonical'] = assembled == canonical
        if assembled != canonical:
            errors.append('prime agent chunk reassembly does not match canonical prime agent file')
    if assembled.count('```') % 2 != 0:
        errors.append('reassembled prime agent has unbalanced markdown code fences')
    if 'Prime_Agent_Chunks_Manifest' in assembled or 'prime_agent_chunks/' in assembled:
        errors.append('reassembled prime agent appears to contain source-only chunk metadata')
    name_markers = markdown_heading_or_label_count(assembled, 'Agent name')
    description_markers = markdown_heading_or_label_count(assembled, 'Agent description')
    checks['prime_agent_agent_name_marker_count'] = name_markers
    checks['prime_agent_agent_description_marker_count'] = description_markers
    if name_markers != 1 or description_markers != 1:
        errors.append('reassembled prime agent must contain exactly one Agent name and one Agent description block')
