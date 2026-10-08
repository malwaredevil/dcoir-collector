"""Canonical regex vocabulary shared by replay assertion-polarity engines."""
from __future__ import annotations

import re

# Assertion polarity treats bare "instead" as a contrast boundary.
ASSERTION_CONTRAST = re.compile(r"\b(?:but|however|yet|nevertheless|instead)\b", re.I)

# Lexical rejection scope intentionally excludes "instead of", which is not a
# clause-level contrast and must not reset the rejection frame.
REJECTION_SCOPE_CONTRAST = re.compile(
    r"\b(?:but|however|yet|nevertheless|instead(?!\s+of\b))\b"
)

# Assertion-polarity clause restart vocabulary. These patterns intentionally
# remain broader than the lexical rejection-scope pair below.
INDEPENDENT_PREDICATE_START = re.compile(
    r"^(?:(?:the\s+evidence|this|that|it|they|we|i|these|those|[a-z0-9_-]+)\s+)?"
    r"(?:(?:clearly|definitely|certainly|explicitly|actually|also|still|now|then)\s+){0,3}"
    r"(?:is|are|was|were|remains?|will|would|can|could|does|do|has|have|guarantees?|confirms?|proves?|"
    r"shows?|indicates?|supports?|establishes?|ensures?|produces?|means?|claims?|concludes?|declares?)\b",
    re.I,
)
COMMA_SUBJECT_PREDICATE_START = re.compile(
    r"^(?:(?:and|but|so)\s+)?(?:i|we|you|they|he|she|it|(?:this|that|these|those)(?:\s+[a-z0-9_-]+){0,4}|"
    r"the(?:\s+[a-z0-9_-]+){1,8}|(?!(?:that|which|who|and|or|but|so)\b)[a-z0-9_-]+(?:\s+[a-z0-9_-]+){0,2})\s+"
    r"(?:(?:clearly|definitely|certainly|explicitly|actually|also|still|now|then)\s+){0,3}"
    r"(?:will|would|should|can|could|must|do|does|did|am|are|is|was|were|remain(?:s)?|have|has|"
    r"guarantee(?:s|d)?|confirm(?:s|ed)?|claim(?:s|ed)?|state(?:s|d)?|assert(?:s|ed)?|"
    r"conclude(?:s|d)?|prove(?:s|d)?|establish(?:es|ed)?|show(?:s|ed)?|indicate(?:s|d)?)\b",
    re.I,
)

# The lexical rejection engine consumes normalized lower-case text and keeps a
# narrower restart vocabulary so a nearby noun phrase cannot escape rejection.
COORDINATED_AFFIRMATIVE_PREDICATE = re.compile(
    r"^(?:(?:clearly|definitely|certainly|explicitly|actually|also|still|now|then)\s+){0,3}"
    r"(?:guarantees?|guaranteed|confirms|confirmed|claims|claimed|states|stated|asserts|asserted|"
    r"concludes|concluded|proves|proved|establishes|established|shows|showed|indicates|indicated|"
    r"means|meant|recommends|recommended|requires|required|needs|needed|believes|believed|"
    r"will|would|can|could|must|should|is|are|was|were|has|have|does|do)\b"
)
COORDINATED_AFFIRMATIVE_SUBJECT_PREDICATE = re.compile(
    r"^(?:i|we|you|they|he|she|it|this|that|these|those|"
    r"the(?:\s+[a-z0-9_-]+){1,3}|(?!(?:a|an|the)\b)[a-z0-9_-]+)\s+"
    r"(?:(?:clearly|definitely|certainly|explicitly|actually|also|still|now|then)\s+){0,3}"
    r"(?:guarantee(?:s|d)?|confirm(?:s|ed)?|claim(?:s|ed)?|state(?:s|d)?|assert(?:s|ed)?|"
    r"conclude(?:s|d)?|prove(?:s|d)?|establish(?:es|ed)?|show(?:s|ed)?|indicate(?:s|d)?|"
    r"mean(?:s|t)?|recommend(?:s|ed)?|require(?:s|d)?|need(?:s|ed)?|believe(?:s|d)?|"
    r"will|would|can|could|must|should|is|are|was|were|has|have|does|do)\b"
)
