"""Shared endpoint/local lane vocabulary for the lane-equivalence scorers.

lane_equivalence and lane_equivalence_extended both build their patterns from
these fragments, so a vocabulary change reaches every equivalence pattern.
"""
from __future__ import annotations

EXECUTE = r"(?:run|runs|running|execute|executes|executing|work|works|working|function|functions|functioning|use|uses|using)"
LANE_TAIL = r"(?:\s+(?:response(?:-action)?|action|console|commands?|syntax|wrappers?|lanes?|shells?|sessions?)){0,3}"
ENDPOINT_REF = rf"(?:(?:elastic\s+)?endpoint|response[- ]action|(?:elastic\s+)?response\s+console){LANE_TAIL}"
LOCAL_REF = rf"(?:local|workstation)\s+(?:workstation\s+)?(?:powershell|shell|console){LANE_TAIL}"
CAPABILITY_OBJECT = r"(?:(?:(?:supported|available|accepted)[-\s]+)?commands?|(?:supported[-\s]+)?command\s+(?:sets?|capabilit(?:y|ies)|repertoires?|availability|inventor(?:y|ies))|sets?\s+of\s+commands?)"
CAPABILITY_EQUIV = rf"(?:(?:exactly|precisely)\s+(?:the\s+same|matching)|(?:the\s+)?(?:exact|precise)\s+same|all\s+the\s+same|the\s+same|identical|equal|matching|(?:completely|fully)\s+overlapping)\s+{CAPABILITY_OBJECT}"
