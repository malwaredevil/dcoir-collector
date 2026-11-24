#!/usr/bin/env python3
"""Shared static OpenAI GPT WebUI validation contract.

Generated packages remain governed by the target/source manifests. This
module is the single owner of paste-safe UI limits and capability key names.
"""
from __future__ import annotations

INSTRUCTION_CHARACTER_CEILING = 8000
DESCRIPTION_CHARACTER_CEILING = 300
CONVERSATION_STARTER_COUNT = 4

CAPABILITY_LABELS = {
    'web_search': 'Web search',
    'code_interpreter_data_analysis': 'Code Interpreter / Data Analysis',
    'canvas': 'Canvas',
    'image_generation': 'Image generation',
    'apps': 'Apps',
    'actions': 'Actions',
    'live_elastic_access': 'Live Elastic access',
    'live_collector_execution': 'Live collector execution',
    'github_supabase_connectors': 'GitHub / Supabase connectors',
    'persistent_cross_conversation_memory': 'Persistent cross-conversation memory',
}
CAPABILITY_KEYS = tuple(CAPABILITY_LABELS)


def webui_character_count(value: str) -> int:
    """Count UTF-16 code units as the WebUI does, including non-BMP characters."""
    return len(value.encode('utf-16-le', errors='surrogatepass')) // 2


def webui_paste_safe_character_count(value: str) -> int:
    """Expand CRLF, LF and lone CR line breaks to CRLF before counting."""
    normalized = value.replace('\r\n', '\n').replace('\r', '\n')
    return webui_character_count(normalized.replace('\n', '\r\n'))


def contains_lone_surrogate(value: str) -> bool:
    """Reject surrogate code points (non-BMP scalar code points remain allowed)."""
    return any(0xD800 <= ord(char) <= 0xDFFF for char in value)


def valid_conversation_starters_shape(values: object) -> bool:
    """Require exactly four nonblank strings; callers retain unique checks."""
    return (
        isinstance(values, list)
        and len(values) == CONVERSATION_STARTER_COUNT
        and all(isinstance(value, str) and value.strip() for value in values)
    )
