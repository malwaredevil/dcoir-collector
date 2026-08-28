"""TEST ONLY — NEVER MERGE: controlled DCOIR Review native-suggestion probe.

This file intentionally contains one deterministic, single-line Python bug so
DCOIR Review can be evaluated against a known true positive and a safe exact
repair. It is not production code and this branch/PR must never be merged.
"""


def is_high_severity(severity: str) -> bool:
    if severity == "critical" or "high":
        return True
    return False
