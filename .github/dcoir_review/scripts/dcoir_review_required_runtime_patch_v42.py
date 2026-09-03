"""DCOIR Review v42 Architecture-B semantic-ledger composition layer.

The implementation is split into connector-safe maintained modules. It remains
semantic-behavior preserving: no prompt, model/provider, routing, escalation,
verification, repair, or semantic-result reuse behavior changes are introduced.

Stable contract vocabulary intentionally remains visible here for governance and
selftest readback: architecture-b-semantic-ledger-v1, context_fingerprint,
runtime_context_fingerprint, prospective_reuse_key, dependency-context-v1,
transient_provenance_present, and recomputed_file_count. semantic-result reuse
is intentionally disabled in this foundation.
"""

from dcoir_review_required_runtime_patch_v42_contract import (
    SEMANTIC_LEDGER_ATTR,
    SEMANTIC_LEDGER_CONTRACT,
    SEMANTIC_LEDGER_MARKER_PREFIX,
    VERSION,
)
from dcoir_review_required_runtime_patch_v42_hooks import (
    apply_pareto_context_module,
    semantic_review_ledger_for_client,
)
from dcoir_review_required_runtime_patch_v42_ledger import (
    build_semantic_review_ledger,
)

__all__ = [
    "VERSION",
    "SEMANTIC_LEDGER_CONTRACT",
    "SEMANTIC_LEDGER_MARKER_PREFIX",
    "SEMANTIC_LEDGER_ATTR",
    "build_semantic_review_ledger",
    "semantic_review_ledger_for_client",
    "apply_pareto_context_module",
]
