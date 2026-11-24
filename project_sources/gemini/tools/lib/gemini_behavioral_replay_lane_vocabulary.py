"""Canonical endpoint/local lane vocabulary for replay scorers.

The same local-lane aliases feed equivalence, composition, semantic, and clause
presence checks. Endpoint scopes remain named separately where their grammars
need different precision, but all endpoint fragments are owned here.
"""
from __future__ import annotations

import re

EXECUTE = r"(?:run|runs|running|execute|executes|executing|work|works|working|function|functions|functioning|use|uses|using)"
LANE_TAIL = r"(?:\s+(?:response(?:-action)?|action|console|commands?|syntax|wrappers?|lanes?|shells?|sessions?)){0,3}"

# Broad equivalence references.
ENDPOINT_REF_BASE = r"(?:(?:elastic\s+)?endpoint|response[- ]action|(?:elastic\s+)?response\s+console)"
LOCAL_REF_BASE = r"(?:local|workstation)\s+(?:workstation\s+)?(?:powershell|shell|console|lane)"
ENDPOINT_REF = rf"{ENDPOINT_REF_BASE}{LANE_TAIL}"
LOCAL_REF = rf"{LOCAL_REF_BASE}{LANE_TAIL}"

# Composition grammar needs an explicit endpoint noun phrase rather than the
# broader standalone `endpoint` accepted by equivalence discovery.
ENDPOINT_RELATION_REF = r"(?:elastic\s+)?(?:endpoint\s+response\s+console|endpoint\s+console|response\s+console|endpoint\s+response[- ]actions?|response[- ]actions?|endpoint\s+lane)"
LOCAL_RELATION_REF = LOCAL_REF_BASE

# Semantic assertion patterns accept endpoint command/syntax surfaces. Local
# context intentionally shares the exact same alias set as relation/equivalence.
ENDPOINT_CONTEXT_REF = (
    r"(?:(?:elastic\s+)?(?:endpoint\s+)?response(?:[- ]action)?\s+(?:console|syntax|wrapper|commands?)"
    r"|endpoint\s+response\s+console)"
)
LOCAL_CONTEXT_REF = LOCAL_REF_BASE

CAPABILITY_OBJECT = r"(?:(?:(?:supported|available|accepted)[-\s]+)?commands?|(?:supported[-\s]+)?command\s+(?:sets?|capabilit(?:y|ies)|repertoires?|availability|inventor(?:y|ies))|sets?\s+of\s+commands?)"
CAPABILITY_EQUIV = rf"(?:(?:exactly|precisely)\s+(?:the\s+same|matching)|(?:the\s+)?(?:exact|precise)\s+same|all\s+the\s+same|the\s+same|identical|equal|matching|(?:completely|fully)\s+overlapping)\s+{CAPABILITY_OBJECT}"

_LOCAL_CONTEXT = re.compile(rf"\b{LOCAL_CONTEXT_REF}\b", re.I)


def clause_has_endpoint_lane(clause: str) -> bool:
    normalized = str(clause).lower()
    return (
        "endpoint" in normalized and (
            "response action" in normalized
            or "response-action" in normalized
            or "response console" in normalized
            or "endpoint execution" in normalized
            or "execute --command" in normalized
        )
    ) or (
        "execute --command" in normalized
        and ("response action" in normalized or "response-action" in normalized)
    )


def clause_has_local_lane(clause: str) -> bool:
    normalized = str(clause).lower()
    return bool(_LOCAL_CONTEXT.search(normalized)) or (
        ("local" in normalized or "workstation" in normalized)
        and ("powershell" in normalized or "command" in normalized)
    )
