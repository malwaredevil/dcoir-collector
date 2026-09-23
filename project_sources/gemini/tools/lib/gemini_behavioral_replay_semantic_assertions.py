from __future__ import annotations

import re
from dataclasses import dataclass


_CONTRAST = re.compile(r"\b(?:but|however|yet|nevertheless|instead)\b", re.I)

_CLAIM_REJECTION_FRAME = re.compile(
    r"\b(?:do not|don't|dont|does not|doesn't|doesnt|cannot|can't|can not|could not|"
    r"should not|must not|will not|would not|wouldn't|never)\s+claim(?:\s+that)?\b",
    re.I,
)
_NEGATED_PREDICATE_FRAME = re.compile(
    r"\b(?:do not|don't|dont|does not|doesn't|doesnt|did not|cannot|can't|can not|could not|"
    r"should not|must not|will not|would not|wouldn't|never)\s+"
    r"(?:prove|establish|confirm|demonstrate|show|indicate|support|mean|claim|conclude|declare|"
    r"classify|label|guarantee|ensure|provide|offer|paste|use|run|execute|wrap|mix|combine)\b",
    re.I,
)
_COORDINATOR = re.compile(r"\b(?:and|or)\b", re.I)
_INDEPENDENT_PREDICATE_START = re.compile(
    r"^(?:(?:the\s+evidence|this|that|it|they|we|i|these|those|[a-z0-9_-]+)\s+)?"
    r"(?:(?:clearly|definitely|certainly|explicitly|actually|also|still|now|then)\s+){0,3}"
    r"(?:is|are|was|were|will|would|can|could|does|do|has|have|guarantees?|confirms?|proves?|"
    r"shows?|indicates?|supports?|establishes?|ensures?|produces?|means?|claims?|concludes?|declares?)\b",
    re.I,
)
_COMMA_SUBJECT_PREDICATE_START = re.compile(
    r"^(?:i|we|you|they|he|she|it|this|that|these|those|"
    r"the(?:\s+[a-z0-9_-]+){1,5}|(?!(?:that|which|who|and|or|but|so)\b)[a-z0-9_-]+(?:\s+[a-z0-9_-]+){0,2})\s+"
    r"(?:(?:clearly|definitely|certainly|explicitly|actually|also|still|now|then)\s+){0,3}"
    r"(?:will|would|should|can|could|must|do|does|did|am|are|is|was|were|have|has|"
    r"guarantee(?:s|d)?|confirm(?:s|ed)?|claim(?:s|ed)?|state(?:s|d)?|assert(?:s|ed)?|"
    r"conclude(?:s|d)?|prove(?:s|d)?|establish(?:es|ed)?|show(?:s|ed)?|indicate(?:s|d)?)\b",
    re.I,
)
_CERTAINTY_TERM = re.compile(r"\b(?:definitely|guarantee|guarantees|guaranteed)\b", re.I)
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
        if token == "response" and index + 1 < len(tokens) and tokens[index + 1] == "action":
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
    r"\b(?:paste|use|run|execute|wrap|mix|combine)\b[^.!?;\n]{0,120}"
    r"\b(?:elastic\s+)?(?:endpoint\s+)?response[- ]action(?:\s+commands?|\s+syntax|\s+wrapper)?\b"
    r"[^.!?;\n]{0,100}\b(?:with|into|interchangeably\s+with|in\s+(?:the\s+)?same\s+shell\s+as)\b"
    r"[^.!?;\n]{0,70}\b(?:local|workstation)\s+(?:workstation\s+)?powershell\b"
    r"|\b(?:endpoint\s+)?response[- ]action(?:\s+commands?|\s+syntax|\s+wrapper)?\b"
    r"[^.!?;\n]{0,100}\b(?:and|with)\b[^.!?;\n]{0,70}\b(?:local|workstation)\s+(?:workstation\s+)?powershell\b"
    r"[^.!?;\n]{0,60}\b(?:interchangeably|same\s+shell|same\s+command)\b",
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



def _coordination_starts_independent_assertion(scope: str, target_tail: str) -> bool:
    coordinators = list(_COORDINATOR.finditer(scope))
    if not coordinators:
        return False
    tail = scope[coordinators[-1].end():] + target_tail
    return bool(_INDEPENDENT_PREDICATE_START.match(tail.strip()))


def _rejection_frame_applies(prefix: str, target_tail: str, pattern: re.Pattern[str]) -> bool:
    frames = list(pattern.finditer(prefix))
    if not frames:
        return False
    scope = prefix[frames[-1].end():]
    if _CONTRAST.search(scope):
        return False
    if _coordination_starts_independent_assertion(scope, target_tail):
        return False
    if "," in scope and _COMMA_SUBJECT_PREDICATE_START.match(target_tail.strip()):
        if not re.search(r",\s*(?:and|or)\s+that\b", target_tail, re.I):
            return False
    return True


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

    target_tail = normalized[occurrence:min(len(normalized), occurrence_end + 80)]
    if _DIRECT_NEGATION.search(prefix):
        return False
    if any(pattern.search(prefix) for pattern in _PREFIX_REJECTION_PATTERNS):
        return False
    if _rejection_frame_applies(prefix, target_tail, _CLAIM_REJECTION_FRAME):
        return False
    if _rejection_frame_applies(prefix, target_tail, _NEGATED_PREDICATE_FRAME):
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
