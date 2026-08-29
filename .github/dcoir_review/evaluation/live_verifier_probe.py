"""TEST ONLY - NEVER MERGE: controlled DCOIR Review verifier probe.

This file intentionally contains one deterministic semantic bug that should be
found by ordinary model review, not by a high-risk sentinel. The function's
contract is explicit so a verifier can judge the finding against full-file
context and the exact changed line.
"""


def is_recent(age_minutes: int) -> bool:
    """Return True when age_minutes is between 0 and 60 inclusive."""
    return age_minutes >= 0 and age_minutes >= 60
