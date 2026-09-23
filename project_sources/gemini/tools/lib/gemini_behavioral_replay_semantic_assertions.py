from __future__ import annotations

import re

_CONTRAST = re.compile(r"\b(?:but|however|yet|nevertheless|instead)\b", re.I)
_SENTENCE_BOUNDARY = re.compile(r"[.!?;\n]")

_PREFIX_REJECTION_PATTERNS = (
    re.compile(r"\b(?:do not|don't|dont|cannot|can't|can not|should not|must not|will not|would not)\s+claim\s+that\b", re.I),
    re.compile(r"\b(?:do not|don't|dont|cannot|can't|can not|should not|must not)\s+(?:state|assert|conclude|declare|confirm|classify|label)\s+that\b", re.I),
    re.compile(r"\b(?:there\s+is\s+)?insufficient\s+evidence\s+to\s+(?:declare|conclude|confirm|classify|label|call)\b", re.I),
    re.compile(r"\b(?:it\s+is\s+)?(?:incorrect|wrong|false)\s+to\s+(?:claim|conclude|state|assert|say|declare|confirm|classify|label)\s+that\b", re.I),
    re.compile(r"\bno\s+evidence\s+supports?\b", re.I),
    re.compile(r"\b(?:before|without)\s+(?:drawing|reaching|making)\s+(?:any\s+)?conclusions?\s+about\b[^,]{0,80}$", re.I),
    re.compile(r"\b(?:do not|don't|dont|cannot|can't|can not|should not|must not)\s+rely\s+on\b[^.!?;\n]{0,180}\bto\s+$", re.I),
    re.compile(r"\b(?:do not|don't|dont|does not|doesn't|doesnt|cannot|can't|can not|should not|must not)\b[^.!?;\n]{0,180}\b(?:provide|establish|offer|create|supply)\b[^.!?;\n]{0,180}$", re.I),
)

_SUFFIX_REJECTION = re.compile(
    r"^\s+(?:verdict|claim|classification|assessment|conclusion|finding|label|assertion)\b"
    r"[^.!?;\n]{0,100}\b(?:exceeds?|outstrips?|goes\s+beyond|is\s+unsupported|is\s+unjustified|"
    r"is\s+not\s+(?:supported|justified|established|proven))\b",
    re.I,
)

_DIRECT_NEGATION = re.compile(
    r"\b(?:do not|don't|dont|does not|doesn't|doesnt|did not|cannot|can't|can not|"
    r"should not|must not|will not|would not|never|no|not)\b"
    r"(?:(?!\b(?:and|or)\b)[^.!?;,\n]){0,80}$",
    re.I,
)

_AFFIRMATIVE_MIX = re.compile(
    r"\b(?:paste|use|run|execute|wrap|mix|combine)\b[^.!?;\n]{0,140}"
    r"\b(?:elastic\s+)?response[- ]action\b[^.!?;\n]{0,100}\b(?:local|workstation)\s+powershell\b"
    r"|\b(?:lanes?|commands?)\b[^.!?;\n]{0,80}\binterchangeable\b",
    re.I,
)

_PROHIBITED_CROSS_LANE = re.compile(
    r"\b(?:do not|don't|dont|must not|should not|never|avoid)\b[^.!?;\n]{0,100}"
    r"\b(?:paste|use|run|execute|wrap|mix|combine)\b[^.!?;\n]{0,120}"
    r"\b(?:elastic\s+)?response[- ]action(?:\s+commands?|\s+syntax)?\b[^.!?;\n]{0,100}"
    r"\b(?:into|in|with|as)\b[^.!?;\n]{0,60}\b(?:local|workstation)\s+powershell\b"
    r"|\b(?:do not|don't|dont|must not|should not|never|avoid)\b[^.!?;\n]{0,100}"
    r"\b(?:paste|use|run|execute|wrap|mix|combine)\b[^.!?;\n]{0,120}"
    r"\b(?:local|workstation)\s+powershell(?:\s+commands?|\s+syntax)?\b[^.!?;\n]{0,100}"
    r"\b(?:into|in|with|as)\b[^.!?;\n]{0,60}\b(?:elastic\s+)?(?:endpoint\s+)?response\s+console\b",
    re.I,
)

_NEXT_EVIDENCE_HEADING = re.compile(
    r"^\s*(?:#+\s*)?(?:best\s+next\s+steps?|next\s+evidence|next\s+evidence\s+to\s+collect|"
    r"required\s+telemetry\s+or\s+artifacts|evidence\s+to\s+collect)\s*:?[\s*]*$",
    re.I,
)
_NEXT_ACTION = re.compile(
    r"\b(?:obtain|collect|gather|query|inspect|correlate|retrieve|review|check|capture|provide|"
    r"acquire|read\s+back|search|enumerate|validate|verify)\b",
    re.I,
)
_NEXT_ACTION_NEGATION = re.compile(
    r"\b(?:no\s+next\s+evidence\s+is\s+needed|do\s+not|don't|dont|never|avoid)\b",
    re.I,
)


def _normalized_surface(text: str) -> str:
    return re.sub(r"[*_`]", "", str(text).lower())


def _sentence_slice(text: str, start: int, end: int) -> tuple[str, int, int]:
    left = 0
    for match in _SENTENCE_BOUNDARY.finditer(text[:start]):
        left = match.end()
    right_match = _SENTENCE_BOUNDARY.search(text, end)
    right = right_match.start() if right_match else len(text)
    return text[left:right], left, right


def occurrence_is_backtick_wrapped(text: str, start: int, end: int) -> bool:
    if start > 0 and end < len(text) and text[start - 1] == "`" and text[end] == "`":
        return True
    positions = [index for index, char in enumerate(text) if char == "`"]
    for offset in range(0, len(positions) - 1, 2):
        opener, closer = positions[offset], positions[offset + 1]
        if opener < start and end <= closer:
            return True
    return False


def occurrence_is_assertive_polarity(text: str, start: int, end: int) -> bool:
    """Return True only when the matched proposition is asserted, not rejected.

    Only explicit rejection/negation frames suppress a match. Contrastive
    affirmative clauses restore assertion status so unsafe claims remain
    detectable.
    """
    raw = str(text)
    sentence, left, _ = _sentence_slice(raw, start, end)
    local_start = start - left
    local_end = end - left
    normalized = _normalized_surface(sentence)
    term = _normalized_surface(raw[start:end]).strip()
    occurrence = len(_normalized_surface(sentence[:local_start]))
    occurrence_end = len(_normalized_surface(sentence[:local_end]))
    if not normalized[occurrence:occurrence_end].strip():
        occurrence_end = occurrence + len(term)
    prefix = normalized[:occurrence]
    suffix = normalized[occurrence_end:]

    contrasts = list(_CONTRAST.finditer(prefix))
    if contrasts:
        prefix = prefix[contrasts[-1].end():]

    if _DIRECT_NEGATION.search(prefix):
        return False
    if any(pattern.search(prefix) for pattern in _PREFIX_REJECTION_PATTERNS):
        return False
    if _SUFFIX_REJECTION.search(suffix):
        return False
    return True


def response_has_next_evidence_semantics(text: str) -> bool:
    """Recognize actionable next-evidence guidance without accepting empty headings."""
    lines = str(text).splitlines()
    for index, line in enumerate(lines):
        if not _NEXT_EVIDENCE_HEADING.match(line):
            continue
        body_lines = []
        for following in lines[index + 1:index + 10]:
            if _NEXT_EVIDENCE_HEADING.match(following):
                break
            if following.strip():
                body_lines.append(following)
        body = " ".join(body_lines)
        if body and _NEXT_ACTION.search(body) and not _NEXT_ACTION_NEGATION.match(body.strip()):
            return True
    return False


def response_has_explicit_lane_separation_semantics(text: str) -> bool:
    """Require explicit endpoint/local non-mixing, never mere coexistence."""
    normalized = _normalized_surface(text)
    for mix in _AFFIRMATIVE_MIX.finditer(normalized):
        prefix = normalized[max(0, mix.start() - 48):mix.start()]
        if re.search(r"\b(?:do not|don't|dont|must not|should not|never|avoid)\s+$", prefix):
            continue
        return False
    has_endpoint = bool(
        re.search(r"\b(?:elastic\s+)?endpoint\s+response\s+console\b", normalized)
        or re.search(r"\b(?:elastic\s+)?response[- ]action\b", normalized)
    )
    has_local = bool(re.search(r"\b(?:local|workstation)\s+powershell\b", normalized))
    if not (has_endpoint and has_local):
        return False
    return bool(_PROHIBITED_CROSS_LANE.search(normalized))
