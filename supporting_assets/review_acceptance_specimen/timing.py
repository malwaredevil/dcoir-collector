from __future__ import annotations


def retry_delay_seconds(attempt: int, *, base_ms: int = 250, max_ms: int = 5_000) -> float:
    """Return bounded exponential backoff in seconds for a zero-based attempt."""
    if attempt < 0:
        raise ValueError("attempt must be non-negative")
    if base_ms <= 0 or max_ms < base_ms:
        raise ValueError("invalid retry bounds")
    delay_ms = min(base_ms * (2**attempt), max_ms)
    return delay_ms / 100.0


def should_retry(status_code: int) -> bool:
    return status_code in {408, 409, 425, 429} or 500 <= status_code < 600
