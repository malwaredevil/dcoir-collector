from __future__ import annotations

import json
from pathlib import Path

from lib.gemini_bundle_validation_common import (
    AGENT_DIR,
    markdown_heading_or_label_count,
    rel_posix,
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
        validate_chunked_prime_agent(manifest, source_root, topology, prime_rel, checks, errors)
    elif prime_source_mode not in (None, 'single_file'):
        warnings.append('unrecognized prime_agent_source_mode: ' + str(prime_source_mode))

    return topology, prime_rel, sub_rel_list


def validate_chunked_prime_agent(
    manifest: dict,
    source_root: Path,
    topology: dict,
    prime_rel: str | None,
    checks: dict[str, object],
    errors: list[str],
) -> None:
    chunk_manifest_rel = manifest.get('prime_agent_chunk_manifest')
    checks['prime_agent_chunk_manifest'] = chunk_manifest_rel
    if not chunk_manifest_rel:
        errors.append('prime_agent_chunk_manifest is required when prime_agent_source_mode=chunked_reassembled')
        return

    chunk_manifest_path = source_root / chunk_manifest_rel
    checks['prime_agent_chunk_manifest_exists'] = chunk_manifest_path.exists()
    if not chunk_manifest_path.exists():
        errors.append('prime agent chunk manifest is missing: ' + chunk_manifest_rel)
        return

    chunk_manifest = json.loads(chunk_manifest_path.read_text(encoding='utf-8'))
    chunk_entries = list(chunk_manifest.get('chunks', []))
    chunk_sources = [entry.get('path') for entry in chunk_entries]
    topology_chunk_sources = list(topology.get('prime_agent_chunk_sources', []))
    checks['prime_agent_chunk_count'] = len(chunk_entries)
    checks['prime_agent_chunk_sources_match_topology'] = chunk_sources == topology_chunk_sources
    if chunk_sources != topology_chunk_sources:
        errors.append('prime agent chunk sources do not match manifest topology prime_agent_chunk_sources')

    missing_chunks = [rel for rel in chunk_sources if not rel or not (source_root / rel).exists()]
    checks['missing_prime_agent_chunks'] = missing_chunks
    if missing_chunks:
        errors.append('missing prime agent chunks: ' + ', '.join(missing_chunks))

    assembled = ''.join((source_root / rel).read_text(encoding='utf-8') for rel in chunk_sources if rel and (source_root / rel).exists())
    canonical_path = source_root / prime_rel if prime_rel else None
    canonical_exists = bool(canonical_path and canonical_path.exists())
    checks['prime_agent_generated_canonical_exists'] = canonical_exists
    if canonical_exists:
        canonical = canonical_path.read_text(encoding='utf-8')
        checks['prime_agent_chunk_reassembly_matches_canonical'] = assembled == canonical
        if assembled != canonical:
            errors.append('prime agent chunk reassembly does not match canonical prime agent file')
    else:
        checks['prime_agent_chunk_reassembly_matches_canonical'] = True
        checks['prime_agent_chunk_reassembly_sha256_only'] = True
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
