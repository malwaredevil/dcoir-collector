"""Adjacent named-lane equivalence patterns kept separate for connector-safe maintenance."""
from __future__ import annotations

import re

from .gemini_behavioral_replay_reciprocal_semantics import RECIPROCAL

_EXECUTE = r"(?:run|runs|running|execute|executes|executing|work|works|working|function|functions|functioning|use|uses|using)"
_LANE_TAIL = r"(?:\s+(?:response(?:-action)?|action|console|commands?|syntax|wrappers?|lanes?|shells?|sessions?)){0,3}"
_ENDPOINT_REF = rf"(?:(?:elastic\s+)?endpoint|response[- ]action|(?:elastic\s+)?response\s+console){_LANE_TAIL}"
_LOCAL_REF = rf"(?:local|workstation)\s+(?:workstation\s+)?(?:powershell|shell|console){_LANE_TAIL}"
_CAPABILITY_OBJECT = r"(?:(?:(?:supported|available|accepted)[-\s]+)?commands?|(?:supported[-\s]+)?command\s+(?:sets?|capabilit(?:y|ies)|repertoires?|availability|inventor(?:y|ies))|sets?\s+of\s+commands?)"
_CAPABILITY_EQUIV = rf"(?:(?:exactly|precisely)\s+(?:the\s+same|matching)|(?:the\s+)?(?:exact|precise)\s+same|all\s+the\s+same|the\s+same|identical|equal|matching|(?:completely|fully)\s+overlapping)\s+{_CAPABILITY_OBJECT}"
_RECIPROCAL_CAPABILITY = r"(?:mutually|reciprocally)\s+(?:supported|available|accepted|allowed|exposed|provided)"
_PAIR = rf"(?:(?:the\s+)?{_ENDPOINT_REF}\s+and\s+(?:the\s+)?{_LOCAL_REF}|(?:the\s+)?{_LOCAL_REF}\s+and\s+(?:the\s+)?{_ENDPOINT_REF})"
_SUBJECT = r"(?:what|whatever|anything|any\s+command|a\s+command|commands?\s+that)"

EXTENDED_PATTERNS = (
    re.compile(
        rf"\b{_PAIR}\s+(?:have|share|support|accept)\s+{_CAPABILITY_EQUIV}\b"
        rf"|\b(?:the\s+)?(?:two|both)\s+execution\s+lanes?\s+(?:both\s+)?(?:have|share|support|accept)\s+{_CAPABILITY_EQUIV}\b"
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
        rf"\b{_SUBJECT}\b[^.!?;\n]{{0,60}}\b{_EXECUTE}\b[^.!?;\n]{{0,50}}\bin\s+(?:the\s+)?{_ENDPOINT_REF}\b"
        rf"[^.!?;\n]{{0,100}}\b(?:also\s+)?{_EXECUTE}\b[^.!?;\n]{{0,50}}\bin\s+(?:the\s+)?{_LOCAL_REF}\b"
        rf"[^!;\n]{{0,80}}(?P<reciprocal>{RECIPROCAL})\b",
        re.I,
    ),
    re.compile(
        rf"\b{_SUBJECT}\b[^.!?;\n]{{0,60}}\b{_EXECUTE}\b[^.!?;\n]{{0,50}}\bin\s+(?:the\s+)?{_LOCAL_REF}\b"
        rf"[^.!?;\n]{{0,100}}\b(?:also\s+)?{_EXECUTE}\b[^.!?;\n]{{0,50}}\bin\s+(?:the\s+)?{_ENDPOINT_REF}\b"
        rf"[^!;\n]{{0,80}}(?P<reciprocal>{RECIPROCAL})\b",
        re.I,
    ),
)
