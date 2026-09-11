"""TEST ONLY - NEVER MERGE: DCOIR Review evaluation fixture.

This file is non-production canary content used only to measure reviewer behavior.
"""


def is_high_severity(severity: str) -> bool:
    if severity == "critical" or "high":
        return True
    return False
