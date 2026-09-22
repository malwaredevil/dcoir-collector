from __future__ import annotations

import re

NEGATION_PATTERN = re.compile(
    r"(?:do not|don't|dont|never|avoid|must not|should not|cannot|can't|can not|not|no|isn't|isnt|wasn't|wasnt|aren't|arent|weren't|werent)(?:\s+[a-z0-9_-]+ly){0,2}(?:\s+(?:the\s+|an?\s+)?)?$"
)

REJECTED_ACTION_VERBS = r"say|state|claim|declare|confirm|conclude|classify|assign|label|advise|assure|guarantee|mean|infer|call|assert|assume|guess|determine|evaluate|assess|attempt|promise|recommend|provide|offer|search|instruct|tell|ask(?: for)?|request|require|treat|frame|use|accept|rely on|run|execute|upload|place|retrieve|review|collect|clean(?:up|\s+up)|keep|invoke|read"

REJECTED_ASSERTION_PATTERN = re.compile(
    rf"(?:wrong to (?:{REJECTED_ACTION_VERBS})|incorrect to (?:{REJECTED_ACTION_VERBS})|false to say|not true that|isn't true that|isnt true that|unsupported to (?:say|claim|treat|frame|use|accept|rely on|run|execute|upload|place|retrieve|review|collect|clean(?:up|\s+up)|keep|invoke|read)|not enough to (?:say|claim|treat|frame|use|accept|rely on|run|execute|upload|place|retrieve|review|collect|clean(?:up|\s+up)|keep|invoke|read)|not sufficient to (?:say|claim|treat|frame|use|accept|rely on|run|execute|upload|place|retrieve|review|collect|clean(?:up|\s+up)|keep|invoke|read)|premature to (?:say|claim|treat|frame|use|accept|rely on|run|execute|upload|place|retrieve|review|collect|clean(?:up|\s+up)|keep|invoke|read)|no need for|(?:do not|don't|dont|should not|shouldn't|shouldnt|must not|cannot|can't|can not) (?:{REJECTED_ACTION_VERBS})|avoid (?:saying|asking for|requesting|requiring|treating|framing|using|accepting|relying on|running|executing|uploading|placing|retrieving|reviewing|collecting|cleaning(?:up|\s+up)|keeping|invoking|reading)|no need to (?:{REJECTED_ACTION_VERBS}))\s+(?:the\s+|an?\s+)?(?:\w+\s+){{0,6}}$"
)


REJECTION_SCOPE_LIMIT = 180

POST_MARKER_REJECTION_NOUN_PHRASE = (
    r"(?:(?:(?:malicious|benign|exact|specific|precise|folder|artifact|security|operator|endpoint)\s+){0,2}"
    r"(?:verdict|claim|conclusion|assertion|classification|framing|statement|assessment|label|outcome|result|guarantee|generation))"
)

PRE_MARKER_REJECTION_FRAME_PATTERN = re.compile(
    rf"(?:"
    rf"(?:do not|don't|dont|does not|doesn't|doesnt|should not|shouldn't|shouldnt|must not|cannot|can't|can not|will not|won't|wont)\s+(?:(?:[a-z0-9_-]+ly)\s+){{0,2}}(?:{REJECTED_ACTION_VERBS})\b"
    rf"(?:[^.!?;,]{{0,100}}\band\s+(?:guarantee|promise|claim|state|assert)\s+that\b)?"
    rf"|(?:do|does|did|should|must|will|would|can|could)\s+(?:(?:also|still|simply|just|really|only)\s+){{1,2}}not\s+(?:(?:[a-z0-9_-]+ly)\s+){{0,2}}(?:{REJECTED_ACTION_VERBS})\b"
    rf"|nor\s+(?:can|should|must|would|will|could)\s+(?:[a-z0-9_-]+\s+){{0,3}}(?:(?:{REJECTED_ACTION_VERBS})\b|$)"
    rf"|nor\s+does\s+(?:[a-z0-9_-]+\s+){{0,3}}(?:mean|prove|establish|show|indicate|demonstrate|support)\b"
    rf"|nor\s+do\s+(?:i|we)\s+(?:[a-z0-9_-]+\s+){{0,3}}(?:advise|recommend|tell|instruct|ask)\b"
    rf"|(?:does|do|did)\s+not\s+(?:mean|prove|establish|show|indicate|demonstrate|support)\b"
    rf"|(?:it\s+is|it's)?\s*false\s+that\b"
    rf"|(?:it\s+is|it's)?\s*(?:wrong|incorrect|inaccurate|misleading)\s+to\s+(?:say|state|claim|assert)\b"
    rf"|(?:cannot|can't|can not)\s+make\s+(?:an?\s+)?"
    rf"|(?:cannot|can't|can not)\s+(?:determine|confirm|establish|verify)\s+(?:if|whether)\b"
    rf"|(?:cannot|can't|can not|must not|should not)\s+be\s+(?:assumed|claimed|stated|asserted|concluded)\s+that\b"
    rf"|(?:cannot|can't|can not|must not|should not)\s+be\s+(?:considered|treated|regarded|viewed|deemed)\b"
    rf"|(?:have|has|had)\s+(?:(?:also|still|simply|just|really|only)\s+)?not\s+(?:claimed|stated|asserted|said|concluded)\s+that\b"
    rf"|(?:(?:i|we)\s+)?(?:(?:am|are)\s+)?not\s+(?:asking|requesting|instructing|telling)(?:\s+you)?\s+to\b"
    rf"|(?:do not|don't|dont|cannot|can't|can not|will not|won't|wont)\s+expect(?:\s+[a-z0-9_-]+){{0,3}}\s+to\b"
    rf"|(?:cannot|can't|can not)\b[^.!?;,]{{0,120}}\b(?:claim|state|assert|tell|instruct)\b"
    rf"|nor\s+will\s+(?:i|we)\s+(?:[a-z0-9_-]+\s+){{0,3}}(?:tell|instruct|claim|state|assert)\b"
    rf"|(?:must\s+)?(?:explicitly\s+)?avoid\s+(?:[a-z0-9_-]+\s+){{0,2}}(?:claiming|stating|asserting|assuming|telling|instructing|recommending|advising)\b"
    rf"|(?:explicitly\s+)?reject(?:ed|s)?\s+(?:(?:any|the|this|that|a|an)\s+)?"
    rf"(?:claim|assertion|contention|conclusion|premise|assumption|proposition|statement|idea|notion|framing|classification|expectation)(?:s)?\s+that\b"
    rf"|(?:explicitly\s+)?reject(?:ed|s)?\s+(?:(?:any|the|this|that|a|an)\s+)?(?:recommendation|instruction|request|attempt)\s+to\b"
    rf"|(?:explicitly\s+)?reject(?:ed|s)?\s+that\b"
    rf"|rather than\s+(?:(?:attempting|trying)\s+to\s+)?"
    rf"|instead\s+of\s+(?:(?:an?|the)\s+)?(?:[a-z0-9_-]+\s+){{0,3}}(?:such\s+as\s+)?(?:attempting|trying)\s+to\s+"
    rf"|instead\s+of\s+(?:(?:an?|the)\s+)?(?:[a-z0-9_-]+\s+){{0,3}}(?:approach|attempt|plan)\s+to\s+"
    rf")"
)

POST_MARKER_REJECTION_PATTERN = re.compile(
    r"^\s*[\"'`]?(?:[,;:.!?]\s*)?(?:(?:no|nope)\b[\s,;:-]*)?(?:(?:but|however|though|although|yet|nevertheless|even so)\s+)?(?:(?:that|this|it|which|they|i|we)\s+)?(?:(?:is|are|was|were)\s+(?:(?:also|still|clearly|simply|just|really|only|explicitly)\s+)?(?:an?\s+)?)?(?:(?:also|still|clearly|simply|just|really|only|explicitly)\s+)?(?:the\s+)?(?:wrong|incorrect|false|invalid|misleading|wrong framing|wrong frame|incorrect framing|incorrect frame|false framing|false frame|wrong conclusion|incorrect conclusion|false conclusion|rejected(?:\s+as\s+(?:stale|unsupported|invalid|incorrect))?|reject(?:ed)?\s+(?:that|this)\s+(?:classification|conclusion|claim|framing)|not enough|not necessary|not needed|not required|unnecessary|insufficient|unsupported|unfounded|overstated|in name only|nominal|label only|just a label|only a label|phrase i would not use|phrase we would not use|a phrase i would not use|a phrase we would not use|should be ignored|should be discarded|should not be used|should not be relied on|can be ignored|can be discarded|does not matter|doesn't matter|doesnt matter|prove it|infer .* anyway|require the full transcript|request the full transcript|ask for the full transcript)"
)

POST_ACTION_REJECTION_PATTERN = re.compile(
    r"^\s*[\"'`]?(?:[,;:.!?]\s*)?(?:(?:that|this|it|which|they)\s+)?(?:is|are|was|were)\s+(?:unavailable|prohibited)\b"
)
