"""DCOIR Review v33 candidate-verification and repair-budget separation.

Issue #456 exposed a second-order integration problem after v32 added an
independent adversarial reviewer.  The merged review can legitimately contain
more raw actionable candidates than the number of findings for which the
reviewer is configured to synthesize one-click repairs.  Treating those two
budgets as one causes a fail-closed review before the evidence verifier can
suppress unsupported candidates.

v33 separates the stages while keeping each bounded:

* ordinary model candidates may enter v21 verification up to the already
  normalized inline-review ceiling, with an absolute 12-candidate hard cap;
* every verifier-supported finding remains publishable;
* repair author/critic work is attempted only for the configured
  ``fix_synthesis_max_findings`` budget;
* verifier-supported findings beyond that repair budget remain visible but
  receive no one-click suggestion.

This module does not weaken the v21 evidence requirement, does not increase the
GitHub inline-publication ceiling, and adds no autonomous remediation or branch
write capability.
"""

from __future__ import annotations

from typing import Any

from dcoir_review import finding_verifier as v21
from dcoir_review import repair as repair_policy
from dcoir_review import repair_pipeline as repair


VERSION = "v33"
APPLIED_MARKER = "_dcoir_review_v33_applied"
DEFERRED_OUTCOME = repair_policy.BUDGET_DEFERRED_OUTCOME



def verifier_candidate_limit(config: Any) -> int:
    """Compatibility delegate to the canonical finding-verifier policy."""

    return v21.verifier_candidate_limit(config)


def repair_synthesis_budget(config: Any) -> int:
    """Compatibility delegate to the canonical repair policy owner."""
    return repair_policy.repair_synthesis_budget(config)


def _deferred_verified_finding(raw: dict[str, Any], ordinal: int) -> dict[str, Any]:
    """Compatibility delegate to the canonical repair policy owner."""

    return repair_policy.budget_deferred_verified_finding(raw, ordinal, repair)




def apply_pareto_context_module(module: Any) -> None:
    """Retain the historical applied marker without mutating repair ownership."""

    if getattr(module, APPLIED_MARKER, False):
        return
    setattr(module, APPLIED_MARKER, True)
