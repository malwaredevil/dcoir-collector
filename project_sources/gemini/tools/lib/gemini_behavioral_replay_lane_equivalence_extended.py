"""Adjacent named-lane equivalence patterns kept separate for connector-safe maintenance."""
from __future__ import annotations

import re

from .gemini_behavioral_replay_reciprocal_semantics import RECIPROCAL
from .gemini_behavioral_replay_lane_vocabulary import (
    EXECUTE,
    ENDPOINT_REF,
    LOCAL_REF,
    CAPABILITY_EQUIV,
)

_RECIPROCAL_CAPABILITY = r"(?:mutually|reciprocally)\s+(?:supported|available|accepted|allowed|exposed|provided)"
_PAIR = rf"(?:(?:the\s+)?{ENDPOINT_REF}\s+and\s+(?:the\s+)?{LOCAL_REF}|(?:the\s+)?{LOCAL_REF}\s+and\s+(?:the\s+)?{ENDPOINT_REF})"
_SUBJECT = r"(?:what|whatever|anything|any\s+command|a\s+command|commands?\s+that)"

EXTENDED_PATTERNS = (
    re.compile(
        rf"\b{_PAIR}\s+(?:have|share|support|accept)\s+{CAPABILITY_EQUIV}\b"
        rf"|\b(?:the\s+)?(?:two|both)\s+execution\s+lanes?\s+(?:both\s+)?(?:have|share|support|accept)\s+{CAPABILITY_EQUIV}\b"
        rf"|\b{_PAIR}\s+each\s+(?:supports?|accepts?|allows?|exposes?|provides?|offers?)\s+"
        rf"(?:all\s+|every\s+|any\s+)?(?:the\s+)?other(?:\s+(?:execution\s+)?lane)?['’]s\s+commands?\b"
        rf"|\beach\s+execution\s+(?:lane|context)\s+(?:supports?|accepts?|allows?|exposes?|provides?|offers?)\s+"
        rf"(?:all|every|any)\s+commands?\s+(?:(?:that|which)\s+)?(?:the\s+)?other(?:\s+execution)?\s+(?:lane|context)\s+"
        rf"(?:does|supports?|accepts?|allows?|exposes?|provides?|offers?)\b"
        rf"|\bcommands?\s+(?:are|remain)\s+(?P<reciprocal>{_RECIPROCAL_CAPABILITY})\b[^.!?;\n]{{0,80}}"
        rf"\b(?:across|between)\s+{_PAIR}\b",
        re.I,
    ),
    re.compile(
        rf"\b{_SUBJECT}\b[^.!?;\n]{{0,60}}\b{EXECUTE}\b[^.!?;\n]{{0,50}}\bin\s+(?:the\s+)?{ENDPOINT_REF}\b"
        rf"[^.!?;\n]{{0,100}}\b(?:also\s+)?{EXECUTE}\b[^.!?;\n]{{0,50}}\bin\s+(?:the\s+)?{LOCAL_REF}\b"
        rf"[^!;\n]{{0,80}}(?P<reciprocal>{RECIPROCAL})\b",
        re.I,
    ),
    re.compile(
        rf"\b{_SUBJECT}\b[^.!?;\n]{{0,60}}\b{EXECUTE}\b[^.!?;\n]{{0,50}}\bin\s+(?:the\s+)?{LOCAL_REF}\b"
        rf"[^.!?;\n]{{0,100}}\b(?:also\s+)?{EXECUTE}\b[^.!?;\n]{{0,50}}\bin\s+(?:the\s+)?{ENDPOINT_REF}\b"
        rf"[^!;\n]{{0,80}}(?P<reciprocal>{RECIPROCAL})\b",
        re.I,
    ),
)
