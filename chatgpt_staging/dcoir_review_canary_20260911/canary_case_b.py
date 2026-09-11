"""TEST ONLY - NEVER MERGE: DCOIR Review evaluation fixture.

This file is non-production canary content used only to measure reviewer behavior.
"""


def is_recent(age_minutes: int) -> bool:
    """Return True when age_minutes is between 0 and 60 inclusive."""
    return age_minutes >= 0 and age_minutes >= 60
