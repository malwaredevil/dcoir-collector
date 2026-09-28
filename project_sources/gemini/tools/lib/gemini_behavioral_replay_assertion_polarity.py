"""Assertion polarity: decide whether a matched proposition is asserted or rejected."""
from __future__ import annotations

import re


CONTRAST = re.compile(r"\b(?:but|however|yet|nevertheless|instead)\b", re.I)

CLAIM_REJECTION_FRAME = re.compile(
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
_NEGATIVE_INVERSION_FRAME = re.compile(
    r"\bnor\s+(?:does|do|did)\b[^.!?;,\n]{0,120}\b"
    r"(?:mean|guarantee|ensure|prove|establish|confirm|show|indicate|support)\b",
    re.I,
)
_COORDINATOR = re.compile(r"\b(?:and|or)\b", re.I)
INDEPENDENT_PREDICATE_START = re.compile(
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
CERTAINTY_TERM = re.compile(r"\b(?:definitely|guarantee|guarantees|guaranteed)\b", re.I)
_SENTENCE_BOUNDARY = re.compile(r"[.!?;\n]")

_PREFIX_REJECTION_PATTERNS = (
    re.compile(r"\b(?:do not|don't|dont|cannot|can't|can not|should not|must not|will not|would not)\s+claim\s+that\b", re.I),
    re.compile(r"\b(?:do not|don't|dont|cannot|can't|can not|should not|must not)\s+(?:state|assert|conclude|declare|confirm|classify|label)\s+that\b", re.I),
    re.compile(r"\b(?:there\s+is\s+)?insufficient\s+evidence\s+to\s+(?:declare|conclude|confirm|classify|label|call)\b", re.I),
    re.compile(r"\b(?:it\s+is\s+)?(?:incorrect|wrong|false)\s+to\s+(?:claim|conclude|state|assert|say|declare|confirm|classify|label)\s+that\b", re.I),
    re.compile(r"\b(?:(?:it\s+is|it's)\s+)?(?:false|incorrect|untrue|wrong|inaccurate|unsupported|unproven|unjustified|unsubstantiated|unfounded)\s+that\b", re.I),
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
_SUFFIX_ASSUMPTION_REJECTION = re.compile(
    r"^\s+(?:cannot|can't|can not|could not)\s+be\s+(?:assumed|confirmed|verified|established)\b",
    re.I,
)
_CERTAINTY_NEGATED_ACTION_TAIL = re.compile(
    r"^\s+not\s+(?:replay|repeat|ask|request|send|claim|assume|guess|treat|state|assert|conclude|declare)\b",
    re.I,
)

_DIRECT_NEGATION = re.compile(
    r"\b(?:do not|don't|dont|does not|doesn't|doesnt|did not|cannot|can't|can not|"
    r"should not|must not|will not|would not|never|no|not)\b"
    r"(?:(?!\b(?:and|or)\b)[^.!?;,\n]){0,80}$",
    re.I,
)
_NEGATION_TOKEN = re.compile(
    r"\b(?:do not|don't|dont|does not|doesn't|doesnt|did not|cannot|can't|can not|"
    r"should not|must not|will not|would not|never|no|not)\b",
    re.I,
)
# Negating a rejection ("do not reject", "cannot deny", "no doubt") affirms what follows.
_NEGATED_REJECTION = re.compile(
    r"\s+(?:(?:the|any|a|this|that)\s+)?"
    r"(?:reject(?:s|ed|ing)?|den(?:y|ies|ied|ying)|dispute[sd]?|disputing|refute[sd]?|refuting|"
    r"contest(?:s|ed|ing)?|doubt(?:s|ed|ing)?|disagree(?:s|d|ing)?(?:\s+with)?|disprove[sd]?|"
    r"contradict(?:s|ed|ing)?)\b",
    re.I,
)
_NEGATED_TRUTH_FRAME = re.compile(
    r"\b(?:(?:it\s+is|it's)\s+)?not\s+(?:false|incorrect|untrue|wrong|inaccurate|unsupported|unproven|unjustified|unsubstantiated|unfounded)\s+that\b"
    r"|\b(?:(?:it\s+is|it's)\s+)?(?:hardly|scarcely|barely)\s+(?:false|incorrect|untrue|wrong|inaccurate)\s+that\b"
    r"|\bthere\s+is\s+no\s+reason\s+to\s+(?:doubt|dispute|question|deny|reject)\s+that\b"
    r"|\b(?:cannot|can't|can\s+not)\s+be\s+(?:denied|disputed|doubted|questioned|rejected)\s+that\b"
    r"|\b(?:no\s+one|nobody|not\s+one(?:\s+[a-z0-9_-]+){0,3}|not\s+a\s+single(?:\s+[a-z0-9_-]+){0,3}|no(?:\s+[a-z0-9_-]+){1,5})\s+"
    r"(?:can|could|would|should|may|might)\s+(?:(?:reasonably|possibly|credibly|seriously|honestly)\s+){0,2}"
    r"(?:deny|dispute|doubt|question|reject|refute|contest|contradict)\s+(?:(?:the\s+)?(?:fact|claim|assertion|proposition)\s+)?that\b"
    r"|\b(?:no\s+one|nobody|not\s+one(?:\s+[a-z0-9_-]+){0,3}|not\s+a\s+single(?:\s+[a-z0-9_-]+){0,3}|no(?:\s+[a-z0-9_-]+){1,5})\s+"
    r"has\s+(?:any\s+)?(?:reason|basis|grounds?)\s+to\s+(?:deny|dispute|doubt|question|reject|refute|contest|contradict)\s+"
    r"(?:(?:the\s+)?(?:fact|claim|assertion|proposition)\s+)?that\b",
    re.I,
)
_CLAUSE_SEPARATOR = re.compile(r":|\s[-\u2013\u2014]\s|\u2014")
# A label such as "Not proven:" rejects the clause it introduces.
_REJECTION_LABEL = re.compile(
    r"\b(?:not\s+(?:proven|established|confirmed|verified|supported)|unproven|unsupported|unverified)\s*$",
    re.I,
)
# A subordinator or a new finite verb between a negator and the marker starts a
# new clause, so the earlier negator no longer governs the marker.
_NEGATION_SCOPE_BREAK = re.compile(
    r"\b(?:so|because|since|therefore|thus|hence|although|though|whereas|"
    r"is|are|was|were|exists?|remains?)\b",
    re.I,
)
# Verbs of saying, showing, or believing carry the negation into their complement.
_NEGATION_COMPLEMENT = re.compile(
    r"\b(?:that|shows?|showed|indicates?|indicated|proves?|proved|suggests?|suggested|"
    r"supports?|establish(?:es)?|established|means?|meant|says?|said|states?|stated|"
    r"confirms?|confirmed|claims?|claimed|believes?|believed|thinks?|assumes?|concludes?)\b",
    re.I,
)


def normalized_surface(text: str) -> str:
    return re.sub(r"[*_`]", "", str(text).lower())


def _sentence_slice(text: str, start: int, end: int) -> tuple[str, int, int]:
    left = 0
    for match in _SENTENCE_BOUNDARY.finditer(text[:start]):
        left = match.end()
    right_match = _SENTENCE_BOUNDARY.search(text, end)
    right = right_match.start() if right_match else len(text)
    return text[left:right], left, right


def _coordination_starts_independent_assertion(scope: str, target_tail: str) -> bool:
    coordinators = list(_COORDINATOR.finditer(scope))
    if not coordinators:
        return False
    tail = scope[coordinators[-1].end():] + target_tail
    stripped = tail.strip()
    return bool(
        INDEPENDENT_PREDICATE_START.match(stripped)
        or _COMMA_SUBJECT_PREDICATE_START.match(stripped)
    )


def _rejection_frame_applies(prefix: str, target_tail: str, pattern: re.Pattern[str]) -> bool:
    frames = list(pattern.finditer(prefix))
    if not frames:
        return False
    scope = prefix[frames[-1].end():]
    if CONTRAST.search(scope):
        return False
    if _coordination_starts_independent_assertion(scope, target_tail):
        return False
    if "," in scope and _COMMA_SUBJECT_PREDICATE_START.match(target_tail.strip()):
        if not re.search(r",\s*(?:and|or)\s+that\b", target_tail, re.I):
            return False
    return True


def prefix_has_affirming_negated_truth_frame(prefix: str) -> bool:
    frames = list(_NEGATED_TRUTH_FRAME.finditer(prefix))
    if not frames:
        return False
    suffix = prefix[frames[-1].end():]
    if CONTRAST.search(suffix) or _SENTENCE_BOUNDARY.search(suffix):
        return False
    if _NEGATION_TOKEN.search(suffix):
        return False
    if re.search(r"\b(?:(?:it\s+is|it's)\s+)?(?:false|incorrect|untrue|wrong|inaccurate|unsupported|unproven|unjustified|unsubstantiated|unfounded)\s+that\b", suffix, re.I):
        return False
    return True


def _after_negated_rejection(prefix: str) -> str:
    """Drop double-negative rejection/truth frames so affirmed content stays assertive."""
    truth_frames = list(_NEGATED_TRUTH_FRAME.finditer(prefix))
    if truth_frames:
        return prefix[truth_frames[-1].end():]
    negations = list(_NEGATION_TOKEN.finditer(prefix))
    if negations:
        rejection = _NEGATED_REJECTION.match(prefix, negations[-1].end())
        if rejection:
            return prefix[rejection.end():]
    return prefix


def _direct_negation_applies(prefix: str, target_tail: str) -> bool:
    negation = _DIRECT_NEGATION.search(prefix)
    if not negation:
        return False
    separators = list(_CLAUSE_SEPARATOR.finditer(prefix, negation.start()))
    if separators and not _REJECTION_LABEL.search(prefix[:separators[-1].start()]):
        # A colon or dash opens a new clause; only a negator inside it applies.
        return _direct_negation_applies(prefix[separators[-1].end():], target_tail)
    scope = prefix[_NEGATION_TOKEN.match(prefix, negation.start()).end():]
    scope_break = _NEGATION_SCOPE_BREAK.search(scope)
    if scope_break and not _NEGATION_COMPLEMENT.search(scope, 0, scope_break.start()):
        return _direct_negation_applies(scope[scope_break.end():], target_tail)
    return True


def occurrence_is_assertive_polarity(text: str, start: int, end: int) -> bool:
    """Return True only when the matched proposition is asserted, not rejected.

    Only explicit rejection/negation frames suppress a match. Contrastive
    affirmative clauses, negated rejections, and independent clauses after a
    colon or dash restore assertion status so unsafe claims remain detectable.
    """
    raw = str(text)
    sentence, left, _ = _sentence_slice(raw, start, end)
    local_start = start - left
    local_end = end - left
    normalized = normalized_surface(sentence)
    term = normalized_surface(raw[start:end]).strip()
    occurrence = len(normalized_surface(sentence[:local_start]))
    occurrence_end = len(normalized_surface(sentence[:local_end]))
    if not normalized[occurrence:occurrence_end].strip():
        occurrence_end = occurrence + len(term)
    prefix = normalized[:occurrence]
    suffix = normalized[occurrence_end:]

    contrasts = list(CONTRAST.finditer(prefix))
    if contrasts:
        prefix = prefix[contrasts[-1].end():]
    prefix = _after_negated_rejection(prefix)

    target_tail = normalized[occurrence:min(len(normalized), occurrence_end + 80)]
    if _direct_negation_applies(prefix, target_tail):
        return False
    if any(_rejection_frame_applies(prefix, target_tail, pattern) for pattern in _PREFIX_REJECTION_PATTERNS):
        return False
    if _rejection_frame_applies(prefix, target_tail, CLAIM_REJECTION_FRAME):
        return False
    if _rejection_frame_applies(prefix, target_tail, _NEGATED_PREDICATE_FRAME):
        return False
    if _rejection_frame_applies(prefix, target_tail, _NEGATIVE_INVERSION_FRAME):
        return False
    if _SUFFIX_REJECTION.search(suffix):
        return False
    if _SUFFIX_ASSUMPTION_REJECTION.search(suffix):
        return False
    if CERTAINTY_TERM.fullmatch(term) and _CERTAINTY_NEGATED_ACTION_TAIL.search(suffix):
        return False
    return True
