"""Entry-point scoped runtime patches for DCOIR Review scripts."""

from __future__ import annotations

try:
    import dcoir_review_runtime_patches

    dcoir_review_runtime_patches.activate()
except Exception:
    # Review scripts must remain able to start even if this compatibility hook
    # cannot load; the underlying reviewer then runs with its committed defaults.
    pass
