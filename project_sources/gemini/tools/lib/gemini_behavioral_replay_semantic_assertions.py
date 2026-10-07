from __future__ import annotations

import re
from dataclasses import dataclass

from .gemini_behavioral_replay_assertion_polarity import (
    CERTAINTY_TERM as _CERTAINTY_TERM,
    CLAIM_REJECTION_FRAME as _CLAIM_REJECTION_FRAME,
    CONTRAST as _CONTRAST,
    INDEPENDENT_PREDICATE_START as _INDEPENDENT_PREDICATE_START,
    normalized_surface as _normalized_surface,
    occurrence_is_assertive_polarity,
)

from .gemini_behavioral_replay_lane_equivalence import has_affirmative_cross_lane_equivalence


_ENDPOINT_CONTEXT = re.compile(
    r"\b(?:elastic\s+)?(?:endpoint\s+)?response(?:[- ]action)?\s+(?:console|syntax|wrapper|commands?)\b"
    r"|\bendpoint\s+response\s+console\b",
    re.I,
)
_LOCAL_POWERSHELL = re.compile(r"\b(?:local|workstation)\s+(?:workstation\s+)?powershell\b|\blocal\s+powershell\b", re.I)
_REFERENTIAL_LOCAL_MIX = re.compile(
    r"\b(?:paste|use|run|execute|wrap)\s+(?:this|that|the)?\s*(?:endpoint\s+)?(?:response[- ]action\s+)?"
    r"(?:wrapper|syntax|command(?:s)?)\b[^.!?;\n]{0,100}\b(?:into|in|with|as)\b[^.!?;\n]{0,50}"
    r"\b(?:local|workstation)\s+(?:workstation\s+)?powershell\b",
    re.I,
)
_AMBIGUOUS_LOCAL_TARGET = re.compile(
    r"\banything\s+(?:[a-z0-9_-]+\s+){1,3}(?:local|workstation)\s+(?:workstation\s+)?powershell\b",
    re.I,
)
_EXPLICIT_SEPARATION_RELATION = re.compile(
    r"\b(?:keep(?:ing)?|kept)?\b[^.!?;\n]{0,100}\bseparate(?:d)?\s+from\b"
    r"|\bseparate(?:d)?\s+from\b",
    re.I,
)
_COORDINATED_CLAUSE_BREAK = re.compile(
    r",\s*(?:and|or|but|however|whereas|yet)\b",
    re.I,
)
_LANE_INDEPENDENT_CLAUSE_START = re.compile(
    r"^(?:(?:local|workstation)\s+(?:workstation\s+)?powershell|"
    r"(?:elastic\s+)?(?:endpoint\s+)?response(?:[- ]action)?\s+(?:console|commands?|syntax))\b"
    r"[^.!?;\n]{0,80}\b(?:runs?|uses?|executes?|collects?|is|are|does|will|can)\b",
    re.I,
)


def _relation_has_independent_clause_break(segment: str) -> bool:
    for boundary in _COORDINATED_CLAUSE_BREAK.finditer(segment):
        tail = segment[boundary.end():].strip()
        if _INDEPENDENT_PREDICATE_START.match(tail) or _LANE_INDEPENDENT_CLAUSE_START.match(tail):
            return True
    return False
_LANE_TARGET_HEAD_BLOCKERS = frozenset(
    {
        "and", "or", "but", "however", "whereas", "yet", "then",
        "except", "excepting", "excluding", "excluded", "without", "unless", "until", "than",
        "instead", "rather", "not", "no", "never", "nor", "apart", "unlike", "versus", "vs",
        "against", "besides", "beside", "save", "saving", "aside", "outside", "beyond", "bar",
        "barring", "sans", "minus", "from", "to", "for", "of", "in", "on", "at", "by", "with",
        "as", "about", "around", "through", "via", "per", "under", "over", "before", "after",
        "between", "among", "across", "into", "onto", "within", "near", "during", "since",
        "toward", "towards", "upon", "if", "when", "while", "though", "although", "because",
        "whether", "once", "where", "wherever", "whenever",
    }
)


def lane_target_head_index(tokens: list[str]) -> int | None:
    scan_limit = min(len(tokens), 4)
    for index in range(scan_limit):
        token = tokens[index]
        if token in _LANE_TARGET_HEAD_BLOCKERS:
            return None
        if token in {"endpoint", "response-action", "local", "workstation"}:
            return index
        if token == "response" and index + 1 < len(tokens) and tokens[index + 1] in {"action", "console"}:
            return index
    return None


def _direct_lane_target_after_relation(segment: str, target_start: int) -> bool:
    prefix = segment[:target_start]
    relations = list(re.finditer(r"\b(?:into|in|with|as)\b", prefix))
    if not relations:
        return False
    scope = prefix[relations[-1].end():]
    target_preview = segment[target_start:target_start + 80]
    tokens = re.findall(r"[a-z0-9_-]+", (scope + " " + target_preview).lower())
    return lane_target_head_index(tokens) is not None
_INTERPRET_TERM = re.compile(r"\binterpret(?:ation|ing|ed|s)?\b", re.I)
_INTERPRET_DIRECTIVE = re.compile(
    r"^\s*(?:\d+[.)]\s*)?(?:[-*]\s*)?interpret\b",
    re.I,
)
_NEGATED_INTERPRET_DIRECTIVE = re.compile(
    r"^\s*(?:\d+[.)]\s*)?(?:[-*]\s*)?(?:do\s+not|don't|dont|never|avoid)\s+interpret\b",
    re.I,
)
_REVIEW_ORDER_DIRECTIVE = re.compile(
    r"^\s*(?:\d+[.)]\s*)?(?:[-*]\s*)?(?:review|start\s+with|begin\s+with)\b"
    r"[^\n]{0,180}\bin\s+this\s+order\b",
    re.I,
)
_NEGATED_REVIEW_ORDER_DIRECTIVE = re.compile(
    r"^\s*(?:\d+[.)]\s*)?(?:[-*]\s*)?(?:do\s+not|don't|dont|never|avoid)\s+"
    r"(?:review|start\s+with|begin\s+with)\b[^\n]{0,180}\bin\s+this\s+order\b",
    re.I,
)
_INTERPRET_ORDER = re.compile(
    r"\b(?:review|start\s+with|begin\s+with|interpret)\b[^\n.!?]{0,180}"
    r"\b(?:in\s+this\s+order|analyst[- ]first|orientation\s+surfaces?)\b",
    re.I,
)
_RETURNED_REVIEW_ORDER = re.compile(
    r"\breview\s+(?:the\s+)?(?:returned\s+)?(?:outputs?|evidence|artifacts?)\b[^\n.!?]{0,100}\bin\s+this\s+order\b",
    re.I,
)
_INTERPRETATION_SURFACES = (
    "analyst_overview_path",
    "upload_summary_path",
    "metadata_report_path",
    "security_high_signal_summary_path",
)

# Elastic response-action syntax named either generically or by its concrete commands.
_RESPONSE_ACTION_COMMAND = r"(?:upload\s+--file|execute\s+--command|get-file\s+--path)"
# Double-negative/encouragement forms (for example, "do not hesitate to X") instruct X; they are not prohibitions.
_PROHIBITION = r"\b(?:do not|don't|dont|must not|should not|never|avoid)\b(?!\s+(?:forget|hesitate|fail|stop|avoid|refuse|decline|refrain|be\s+(?:afraid|reluctant|hesitant))\b)"

_AFFIRMATIVE_MIX = re.compile(
    r"\b(?:paste|use|run|execute|wrap|mix|combine)\b[^.!?;\n]{0,120}"
    r"(?:\b(?:elastic\s+)?(?:endpoint\s+)?response[- ]action(?:\s+commands?|\s+syntax|\s+wrapper)?\b|" + _RESPONSE_ACTION_COMMAND + r")"
    r"[^.!?;\n]{0,100}\b(?:with|into|interchangeably\s+with|in\s+(?:the\s+)?same\s+shell\s+as)\b"
    r"[^.!?;\n]{0,70}\b(?:local|workstation)\s+(?:workstation\s+)?powershell\b"
    r"|\b(?:endpoint\s+)?response[- ]action(?:\s+commands?|\s+syntax|\s+wrapper)?\b"
    r"[^.!?;\n]{0,100}\b(?:and|with)\b[^.!?;\n]{0,70}\b(?:local|workstation)\s+(?:workstation\s+)?powershell\b"
    r"[^.!?;\n]{0,60}\b(?:interchangeably|same\s+shell|same\s+command)\b",
    re.I,
)

_PROHIBITED_CROSS_LANE = re.compile(
    _PROHIBITION + r"[^.!?;\n]{0,100}"
    r"\b(?:paste|use|run|execute|wrap|mix|combine)\b[^.!?;\n]{0,120}"
    r"(?:\b(?:elastic\s+)?response[- ]action(?:\s+commands?|\s+syntax)?\b|" + _RESPONSE_ACTION_COMMAND + r")"
    r"[^.!?;\n]{0,100}"
    r"\b(?:into|in|with|as)\b[^.!?;\n]{0,60}\b(?:local|workstation)\s+powershell\b"
    r"|" + _PROHIBITION + r"[^.!?;\n]{0,100}"
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


def occurrence_is_backtick_wrapped(text: str, start: int, end: int) -> bool:
    if start > 0 and end < len(text) and text[start - 1] == "`" and text[end] == "`":
        return True
    positions = [index for index, char in enumerate(text) if char == "`"]
    for offset in range(0, len(positions) - 1, 2):
        opener, closer = positions[offset], positions[offset + 1]
        if opener < start and end <= closer:
            return True
    return False



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


@dataclass(frozen=True)
class SemanticAnalysis:
    text: str

    @property
    def normalized(self) -> str:
        return _normalized_surface(self.text)

    def occurrence_is_assertive(self, start: int, end: int) -> bool:
        return occurrence_is_assertive_polarity(self.text.lower(), start, end)

    def has_no_claim_semantics(self) -> bool:
        lowered = self.text.lower()
        if _CLAIM_REJECTION_FRAME.search(lowered):
            return True
        for occurrence in _CERTAINTY_TERM.finditer(lowered):
            if not self.occurrence_is_assertive(occurrence.start(), occurrence.end()):
                return True
        return False

    def execution_lane_separation_status(self) -> bool | None:
        normalized = self.normalized
        has_endpoint = bool(_ENDPOINT_CONTEXT.search(normalized))
        has_local = bool(_LOCAL_POWERSHELL.search(normalized))
        if not (has_endpoint and has_local):
            return None
        if _AMBIGUOUS_LOCAL_TARGET.search(normalized):
            return False

        if has_affirmative_cross_lane_equivalence(normalized):
            return False

        for mix in _AFFIRMATIVE_MIX.finditer(normalized):
            if _CONTRAST.search(mix.group(0)) or _EXPLICIT_SEPARATION_RELATION.search(mix.group(0)):
                continue
            if occurrence_is_assertive_polarity(normalized, mix.start(), mix.end()):
                return False
        for mix in _REFERENTIAL_LOCAL_MIX.finditer(normalized):
            if _CONTRAST.search(mix.group(0)) or _EXPLICIT_SEPARATION_RELATION.search(mix.group(0)):
                continue
            if occurrence_is_assertive_polarity(normalized, mix.start(), mix.end()):
                return False

        for relation in _PROHIBITED_CROSS_LANE.finditer(normalized):
            relation_text = relation.group(0)
            if _relation_has_independent_clause_break(relation_text):
                continue
            local_target = _LOCAL_POWERSHELL.search(relation_text)
            endpoint_target = _ENDPOINT_CONTEXT.search(relation_text)
            if local_target and _direct_lane_target_after_relation(relation_text, local_target.start()):
                return True
            if endpoint_target and _direct_lane_target_after_relation(relation_text, endpoint_target.start()):
                return True

        for mix in _REFERENTIAL_LOCAL_MIX.finditer(normalized):
            if occurrence_is_assertive_polarity(normalized, mix.start(), mix.end()):
                continue
            prior = normalized[max(0, mix.start() - 260):mix.start()]
            if _ENDPOINT_CONTEXT.search(prior):
                return True

        endpoint_only = bool(re.search(
            r"\buse\b[^.!?;\n]{0,120}\b(?:response[- ]action\s+syntax|endpoint\s+response\s+console)\b"
            r"[^.!?;\n]{0,120}\bonly\b|\bonly\b[^.!?;\n]{0,120}\bendpoint\s+response\s+console\b",
            normalized,
        ))
        local_only = bool(re.search(
            r"\buse\b[^.!?;\n]{0,100}\b(?:direct\s+)?powershell\b[^.!?;\n]{0,120}\bonly\b"
            r"|\b(?:direct\s+)?powershell\s+only\s+for\b",
            normalized,
        ))
        if endpoint_only and local_only:
            return True
        return None

    def interpretation_actionability_status(self) -> bool | None:
        lowered = self.text.lower()
        normalized = self.normalized
        surface_count = sum(1 for surface in _INTERPRETATION_SURFACES if surface in lowered)
        if surface_count < 2:
            return None

        lines = self.text.splitlines()
        primary_directive: bool | None = None
        ordered_review_directive = False
        for line in lines:
            if _NEGATED_INTERPRET_DIRECTIVE.search(line) or _NEGATED_REVIEW_ORDER_DIRECTIVE.search(line):
                return False
            if primary_directive is None and _INTERPRET_DIRECTIVE.search(line):
                primary_directive = True
            if _REVIEW_ORDER_DIRECTIVE.search(line):
                ordered_review_directive = True

        ordered_action = bool(_INTERPRET_ORDER.search(normalized)) or ordered_review_directive
        if primary_directive is True and ordered_action:
            return True
        if primary_directive is None and ordered_review_directive:
            return True

        interpret_occurrences = list(_INTERPRET_TERM.finditer(lowered))
        assertive_interpret = any(
            self.occurrence_is_assertive(occurrence.start(), occurrence.end())
            for occurrence in interpret_occurrences
        )
        rejected_interpret = bool(interpret_occurrences) and not assertive_interpret
        if rejected_interpret:
            return False
        if primary_directive is None and not interpret_occurrences and _RETURNED_REVIEW_ORDER.search(normalized):
            return True
        return None


def analyze_semantics(text: str) -> SemanticAnalysis:
    return SemanticAnalysis(str(text))
