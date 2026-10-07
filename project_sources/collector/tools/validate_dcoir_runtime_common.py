#!/usr/bin/env python3
"""Shared helpers for DCOIR collector runtime-package validation."""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Dict, List

from powershell_lexical_mask import mask_powershell_non_code

MANIFEST_NAME = 'Collector_Runtime_Package_Manifest.json'
FUNCTION_PATTERN = re.compile(r'^\s*function\s+([-A-Za-z0-9_]+)\b', re.MULTILINE)


def load_manifest(source_dir: Path) -> Dict:
    return json.loads((source_dir / 'project_sources' / 'collector' / 'manifests' / MANIFEST_NAME).read_text(encoding='utf-8'))


def normalize_function_name(name: str) -> str:
    return name.casefold()


def read_text(path: Path) -> str:
    return path.read_text(encoding='utf-8', errors='ignore') if path.exists() else ''


def load_manifest_source_texts(source_dir: Path, manifest: Dict) -> Dict[str, str]:
    rels = [manifest['collector_wrapper_source']] + manifest.get('collector_part_files', [])
    return {rel: read_text(source_dir / rel) for rel in rels if (source_dir / rel).exists()}


def get_combined_source_text(source_text_by_rel: Dict[str, str]) -> str:
    return '\n'.join(source_text_by_rel.values())


def find_function_definitions(source_dir: Path, manifest: Dict) -> Dict[str, List[Dict[str, object]]]:
    definitions: Dict[str, List[Dict[str, object]]] = {}
    for load_order, rel in enumerate([manifest['collector_wrapper_source']] + manifest.get('collector_part_files', [])):
        text = read_text(source_dir / rel)
        for line_number, line in enumerate(text.splitlines(), 1):
            match = re.match(r'^\s*function\s+([-A-Za-z0-9_]+)\b', line)
            if not match:
                continue
            name = match.group(1)
            normalized = normalize_function_name(name)
            definitions.setdefault(normalized, []).append({
                'name': name,
                'normalized_name': normalized,
                'path': rel,
                'line': line_number,
                'load_order': load_order,
            })
    return definitions


def extract_function_body(text: str, function_name: str) -> str:
    match = re.search(r'^\s*function\s+' + re.escape(function_name) + r'\b', text, re.MULTILINE)
    if not match:
        return ''
    brace_start = text.find('{', match.end())
    if brace_start == -1:
        return ''
    depth = 0
    for index in range(brace_start, len(text)):
        char = text[index]
        if char == '{':
            depth += 1
        elif char == '}':
            depth -= 1
            if depth == 0:
                return text[brace_start:index + 1]
    return text[brace_start:]


def find_convert_to_json_calls(rel: str, text: str) -> List[Dict[str, object]]:
    clean_text = mask_powershell_non_code(text)
    command_pattern = re.compile(r'(?<![-.\w])(?:[-A-Za-z0-9_.]+\\)?ConvertTo-Json\b', re.IGNORECASE)
    return [
        {'path': rel, 'line': line_number, 'text': line.strip()}
        for line_number, line in enumerate(clean_text.splitlines(), 1)
        if command_pattern.search(line)
    ]


def build_dot_source_lines_for_functions(source_dir: Path, manifest: Dict, function_names: List[str]) -> str:
    targets = {normalize_function_name(name) for name in function_names}
    rels: List[str] = []
    for rel in manifest.get('collector_part_files', []):
        text = read_text(source_dir / rel)
        if any(normalize_function_name(match.group(1)) in targets for match in FUNCTION_PATTERN.finditer(text)):
            rels.append(rel)
    return '\n'.join(". '{0}'".format(str((source_dir / rel).resolve()).replace("'", "''")) for rel in rels)


def add_missing_errors(prefix: str, check_map: Dict[str, object], required_keys: List[str], errors: List[str]) -> None:
    for key in required_keys:
        if not check_map.get(key):
            errors.append(prefix + key)
