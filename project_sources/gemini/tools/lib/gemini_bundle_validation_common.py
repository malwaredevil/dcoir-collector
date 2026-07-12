from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Dict, List

MANIFEST_NAME = 'Gemini_Bundle_Source_Manifest.json'
AGENT_DIR = '01_GEMINI_AGENT_BUILD'
QUICK_START = '00_START_HERE/Gemini_Build_Quick_Start.md.txt'
ATTACHMENT_MAP = '00_START_HERE/Agent_Attachment_Map.md.txt'
DEFAULT_GENERATED_KNOWLEDGE_DIR = '02_PRIME_AGENT_ATTACHMENTS'
RUNTIME_GOVERNANCE_LEAK_PATTERNS = {
    'gemini_research_reference': r'\bGemini Research Reference\b',
    'airtable_idea_inbox': r'\bAirtable Idea Inbox\b',
    'source_prompt_record': r'\bIDEA-[0-9]{8}-[A-Z0-9-]+\b',
    'ircore_gemini_research_surface': r'\bircore\.(?:gemini_research_findings|gemini_research_consultation_receipts|get_gemini_research_consultation_v1|get_gemini_research_receipt_v1)\b',
    'gemini_builder_governance': r'\bGemini Builder Governance Rule\b',
}
VISIBILITY_CHECKS = {
    'collector_artifact_interpretation_visibility': ['collector artifact', 'upload summary'],
    'collector_pivot_visibility': ['targeted collection', 'collector'],
    'ioc_ownership_visibility': ['ioc', 'provenance'],
    'mixed_format_ioc_parsing_visibility': ['csv', 'pdf', 'docx'],
    'false_positive_aware_security_product_behavior': ['false-positive-aware', 'security product'],
    'starter_prompt_visibility': ['starter prompt 1', 'starter prompt 2', 'starter prompt 3'],
    'operator_state_awareness_visibility': ['operator', 'analyst'],
}


def load_manifest(source_root: Path) -> Dict:
    return json.loads((source_root / MANIFEST_NAME).read_text(encoding='utf-8'))


def resolve_repo_root(source_root: Path) -> Path:
    return source_root.parent.parent.parent


def rel_posix(path: Path, source_root: Path) -> str:
    return path.relative_to(source_root).as_posix()


def generated_attachment_name(source_rel: str) -> str:
    name = Path(source_rel).name
    if not name.endswith('.md'):
        raise ValueError(f'Knowledge attachment source must be a markdown file: {source_rel}')
    return name + '.txt'


def gather_text(paths: List[Path]) -> str:
    parts: List[str] = []
    for path in paths:
        if path.exists() and path.is_file():
            try:
                parts.append(path.read_text(encoding='utf-8', errors='ignore').lower())
            except Exception:
                continue
    return '\n'.join(parts)


def markdown_heading_or_label_count(text: str, label: str) -> int:
    patterns = [
        rf'(?im)^\s*###\s+{re.escape(label)}\s*$',
        rf'(?im)^\s*{re.escape(label)}\s*:',
    ]
    return sum(len(re.findall(pattern, text)) for pattern in patterns)
