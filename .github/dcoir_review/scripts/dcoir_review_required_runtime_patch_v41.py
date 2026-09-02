"""DCOIR Review v41 Architecture-B incremental review frontier composition layer."""

from dcoir_review_required_runtime_patch_v41_hooks import apply_pareto_context_module
from dcoir_review_required_runtime_patch_v41_review_state import (
    ARCHITECTURE_CONTRACT,
    ARCHITECTURE_CONTRACT_MARKER,
    BASE_CONTRACT_PREFIX,
    TRUSTED_REVIEW_AUTHORS,
    latest_compatible_context_review,
)
from dcoir_review_required_runtime_patch_v41_scope import (
    INITIAL_DIFF_CONSUMED_KEY,
    SCOPE_CACHE_ATTR,
    resolve_review_scope,
)

VERSION = "v41"

__all__ = [
    "VERSION",
    "ARCHITECTURE_CONTRACT",
    "ARCHITECTURE_CONTRACT_MARKER",
    "BASE_CONTRACT_PREFIX",
    "TRUSTED_REVIEW_AUTHORS",
    "INITIAL_DIFF_CONSUMED_KEY",
    "SCOPE_CACHE_ATTR",
    "resolve_review_scope",
    "latest_compatible_context_review",
    "apply_pareto_context_module",
]
