"""Single owner of the chunked Prime agent reassembly contract.

Both the reassembler (which writes the runtime-generated Prime file) and the
bundle validator (which checks it) use this module, so they apply the same
manifest/topology binding, path containment and sha256 integrity rules.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

from lib.gemini_bundle_path_safety import UnsafePathError, resolve_contained_path


class PrimeChunkPlanError(ValueError):
    """Raised when the chunk plan is unbound, unsafe, unreadable or fails integrity."""


@dataclass(frozen=True)
class PrimeChunk:
    rel: str
    path: Path
    sha256: str | None


@dataclass(frozen=True)
class PrimeChunkPlan:
    chunk_manifest_rel: str
    target_rel: str
    target_path: Path
    chunks: tuple[PrimeChunk, ...]
    expected_sha256: str | None


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


def _contained(source_root: Path, value: object, label: str) -> Path:
    try:
        return resolve_contained_path(source_root, value, label)
    except UnsafePathError as exc:
        raise PrimeChunkPlanError(str(exc)) from exc


def _read_text(path: Path, label: str) -> str:
    try:
        return path.read_text(encoding='utf-8')
    except (OSError, UnicodeDecodeError) as exc:
        raise PrimeChunkPlanError(f'{label} could not be read: {type(exc).__name__}') from exc


def load_chunk_plan(bundle_manifest: dict, source_root: Path) -> PrimeChunkPlan:
    """Bind the chunk manifest to the bundle manifest and topology, or fail closed."""
    chunk_manifest_rel = bundle_manifest.get('prime_agent_chunk_manifest')
    if not chunk_manifest_rel:
        raise PrimeChunkPlanError(
            'prime_agent_chunk_manifest is required when prime_agent_source_mode=chunked_reassembled'
        )
    topology = bundle_manifest.get('topology')
    if not isinstance(topology, dict):
        raise PrimeChunkPlanError(
            'Bundle topology is required when prime_agent_source_mode=chunked_reassembled'
        )
    topology_manifest_rel = topology.get('prime_agent_chunk_manifest')
    if topology_manifest_rel != chunk_manifest_rel:
        raise PrimeChunkPlanError(
            'Prime chunk manifest disagreement between bundle runtime and topology: '
            f'{chunk_manifest_rel!r} != {topology_manifest_rel!r}'
        )

    chunk_manifest_path = _contained(source_root, chunk_manifest_rel, 'prime_agent_chunk_manifest')
    try:
        chunk_manifest = json.loads(_read_text(chunk_manifest_path, 'prime_agent_chunk_manifest'))
    except json.JSONDecodeError as exc:
        raise PrimeChunkPlanError(
            f'prime_agent_chunk_manifest could not be read: {type(exc).__name__}'
        ) from exc
    if not isinstance(chunk_manifest, dict):
        raise PrimeChunkPlanError('prime_agent_chunk_manifest must contain a JSON object')

    # The only file reassembly may write is the declared runtime-generated Prime
    # agent; anything else would overwrite governed bundle source.
    target_rel = chunk_manifest.get('generated_prime_agent_file')
    if target_rel != topology.get('prime_agent_file'):
        raise PrimeChunkPlanError(
            'generated_prime_agent_file must match topology.prime_agent_file: '
            f'{target_rel!r} != {topology.get("prime_agent_file")!r}'
        )
    runtime_generated_files = bundle_manifest.get('runtime_generated_files')
    if not isinstance(runtime_generated_files, list) or target_rel not in runtime_generated_files:
        raise PrimeChunkPlanError(
            f'generated_prime_agent_file must be listed in runtime_generated_files: {target_rel!r}'
        )
    target_path = _contained(source_root, target_rel, 'generated_prime_agent_file')

    entries = chunk_manifest.get('chunks', [])
    if not isinstance(entries, list) or not entries:
        raise PrimeChunkPlanError('Prime agent chunk manifest has no chunks')
    chunk_rels = [entry.get('path') if isinstance(entry, dict) else None for entry in entries]
    if any(not isinstance(rel, str) or not rel for rel in chunk_rels):
        raise PrimeChunkPlanError('Prime agent chunk manifest contains an invalid chunk path')
    if topology.get('prime_agent_chunk_sources') != chunk_rels:
        raise PrimeChunkPlanError(
            'Prime chunk source disagreement between selected manifest and bundle topology'
        )
    chunks = tuple(
        PrimeChunk(rel, _contained(source_root, rel, 'prime agent chunk path'), entry.get('sha256'))
        for rel, entry in zip(chunk_rels, entries)
    )

    reassembly = chunk_manifest.get('reassembly')
    expected_sha = reassembly.get('expected_sha256') if isinstance(reassembly, dict) else None
    return PrimeChunkPlan(chunk_manifest_rel, target_rel, target_path, chunks, expected_sha)


def assemble(plan: PrimeChunkPlan) -> str:
    """Concatenate the chunks in order after verifying every declared sha256."""
    missing = [chunk.rel for chunk in plan.chunks if not chunk.path.exists()]
    if missing:
        raise PrimeChunkPlanError('Missing prime agent chunks: ' + ', '.join(missing))
    parts = []
    for chunk in plan.chunks:
        text = _read_text(chunk.path, f'Prime agent chunk {chunk.rel}')
        actual = sha256_text(text)
        if chunk.sha256 and actual != chunk.sha256:
            raise PrimeChunkPlanError(
                f'Chunk sha256 mismatch for {chunk.rel}: expected {chunk.sha256}, got {actual}'
            )
        parts.append(text)
    assembled = ''.join(parts)
    assembled_sha = sha256_text(assembled)
    if plan.expected_sha256 and assembled_sha != plan.expected_sha256:
        raise PrimeChunkPlanError(
            'Reassembled prime agent sha256 mismatch: '
            f'expected {plan.expected_sha256}, got {assembled_sha}'
        )
    return assembled
