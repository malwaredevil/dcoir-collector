from __future__ import annotations

import importlib
from dataclasses import dataclass
from types import ModuleType
from typing import Iterable


@dataclass(frozen=True)
class DcoirReviewEntrypoint:
    review_module_name: str = "openrouter_pr_review_pareto_context"
    patch_module_names: tuple[str, ...] = (
        'dcoir_review_runtime_patches',
        'dcoir_review_strict_runtime_patches',
        'dcoir_review_required_runtime_patches',
        'dcoir_review_required_runtime_patch_v2',
        'dcoir_review_required_runtime_patch_v3',
        'dcoir_review_required_runtime_patch_v5_apply',
        'dcoir_review_required_runtime_patch_v6',
        'dcoir_review_required_runtime_patch_v9',
        'dcoir_review_required_runtime_patch_v10',
        'dcoir_review_required_runtime_patch_v11',
        'dcoir_review_required_runtime_patch_v12',
        'dcoir_review_required_runtime_patch_v13',
        'dcoir_review_required_runtime_patch_v14',
        'dcoir_review.finding_family',
        'dcoir_review_required_runtime_patch_v16',
        'dcoir_review.precision_guard',
        'dcoir_review_required_runtime_patch_v20',
        'dcoir_review.finding_verifier',
        'dcoir_review.quality_gate',
        'dcoir_review.normalized_finding_selection',
        'dcoir_review.repair_pipeline',
        'dcoir_review.sentinel_selection',
        'dcoir_review.finding_comment_render',
        # v33 separates pre-publication verification capacity from the bounded
        # repair budget. Stable semantic evidence and canonical finding verification
        # preserve predicate/call-site recall, blank-anchor evidence, and
        # falsification-first verifier guidance. Semantic adjudication and its
        # confidence normalization are composed explicitly by review_orchestration.
        # Stable repair-set owners support bounded coordinated edit sets
        # (multi-line, non-contiguous, and cross-file) while keeping human-only
        # application. The canonical finding-comment renderer owns linked repair-set
        # publication. The stable semantic-adjudication normalizer preserves the adjudicator's valid
        # flat-single-finding compatibility shape before canonical adjudication capping/publication.
        # v38 makes repair-author confidence advisory, normalizes only missing
        # explanatory repair metadata, and raises the independent critic hard
        # acceptance threshold while preserving exact-head structural checks.
        # Semantic-adjudication confidence normalization handles one additional
        # provider-schema seam: when an otherwise complete semantic-adjudication
        # finding omits confidence, it assigns only the configured normal floor to
        # admit the candidate to v21 verification; verifier support remains mandatory
        # before repair/publication. v31 stays
        # terminal for this historical semantic-patch chain.
        'dcoir_review.semantic_evidence_hardening',
        'dcoir_review.semantic_adjudication_normalization',
        'dcoir_review.repair_contract',
        'dcoir_review_required_runtime_patch_v31',
    )
    # Architecture-B responsibilities are deliberately outside the historical semantic
    # patch chain. These run after v31 so old semantic-order invariants remain
    # meaningful while production receives the approved incremental frontier
    # responsibility, semantic-ledger/fingerprint foundation, then fail-closed
    # semantic-result reuse on exact compatible evidence. Semantic-result reuse
    # now participates through explicit orchestration rather than a runtime installer.
    terminal_patch_module_names: tuple[str, ...] = (
        'dcoir_review.incremental_review_frontier',
        'dcoir_review.semantic_review_ledger',
    )
    # Architecture-B post-terminal owners retain verifier-authoritative publication.
    # Canonical semantic context and fail-safe adaptive budgets are installed
    # explicitly by review_orchestration rather than by a numbered patch root. v50
    # then preserves unresolved verifier-supported findings across compatible
    # incremental reviewed-head runs without re-posting unchanged inline comments.
    # Capability gating keeps historical probe objects and explicit subset tests
    # from receiving implicit overlays.
    post_terminal_patch_module_names: tuple[str, ...] = (
        'dcoir_review.publication_disposition',
        'dcoir_review.verified_finding_gate',
    )
    # Candidate-integrity overlays are cross-cutting semantic guards installed
    # after the composed Architecture-B post-terminal contract but before stage-
    # local per-file composition. The stable identity owner protects ordinary candidates from
    # unsupported free-text risk-kind inference while leaving deterministic
    # sentinel coverage and verifier authority intact.
    candidate_integrity_patch_module_names: tuple[str, ...] = (
        'dcoir_review.semantic_candidate_identity',
    )
    # Stage-local per-file composition is deliberately separate from Architecture-B
    # semantic-order invariants. The canonical per-file owner explicitly composes
    # semantic-result reuse with calibrated routing/telemetry while premium later
    # stages remain unchanged.
    stage_local_patch_module_names: tuple[str, ...] = (
        'dcoir_review.per_file_review',
    )
    # Execution-policy overlays run last so they guard the fully composed provider
    # and publication paths without changing Architecture-B semantic ordering or
    # the v47 per-file routing contract. Stable review-scope guards own exact-scope
    # provider/publication protection and the legacy optional prompt-review request. Stable structured-result recovery
    # preserves those guards while specializing deterministic structured-output
    # recovery and bounded near-threshold disposition. v53 then restores the
    # Repair-confidence admission is consumed directly by the terminal repair owner
    # rather than installed as another runtime override.
    execution_policy_patch_module_names: tuple[str, ...] = (
        'dcoir_review.review_scope_guard',
        'dcoir_review.prompt_review_scope_guard',
        'dcoir_review.review_orchestration',
    )
    # Telemetry overlays are deliberately outside execution-policy ordering
    # invariants. v54 owns request-path usage/provider/recovery telemetry after the
    # scope guards/v52/v53 and exposes bounded terminal run telemetry, but it no
    # longer replaces ProgressReporter or stores a prior reporter shim.
    telemetry_patch_module_names: tuple[str, ...] = ()
    # Canonical progress reporting is installed immediately after v54 request
    # telemetry. It is the single terminal reporter composition owner, combining
    # verified-finding completion overrides with v54 terminal run telemetry while
    # inheriting the existing base/review-scope reporter behavior. Provider
    # transport retry follows that owner, then stable semantic-adjudication
    # recovery and the remaining post-telemetry guards.
    post_telemetry_patch_module_names: tuple[str, ...] = (
        'dcoir_review.progress_reporting',
        'dcoir_review.provider_transport_retry',
        'dcoir_review.semantic_adjudication_recovery',
        'dcoir_review.final_adjudication_policy',
        'dcoir_review.provider_review',
    )

    def import_module(self, module_name: str) -> ModuleType:
        return importlib.import_module(module_name)

    def _apply_patch_modules(self, review_module: ModuleType, module_names: Iterable[str]) -> None:
        for module_name in tuple(module_names):
            patch_module = self.import_module(module_name)
            apply_patch = getattr(patch_module, "apply_pareto_context_module", None)
            if apply_patch is None:
                raise RuntimeError(f"Runtime patch module {module_name} does not expose apply_pareto_context_module")
            apply_patch(review_module)

    def apply_runtime_patches(
        self,
        review_module: ModuleType,
        patch_module_names: Iterable[str] | None = None,
    ) -> None:
        if patch_module_names is not None:
            # Explicit callers retain exact control of the requested historical
            # patch subset; production-only overlays are not implicit additions
            # to custom test/probe subsets.
            self._apply_patch_modules(review_module, patch_module_names)
            return
        self._apply_patch_modules(review_module, self.patch_module_names)
        self._apply_patch_modules(review_module, self.terminal_patch_module_names)
        if callable(getattr(review_module, "openrouter_review_with_hybrid_first_pass", None)):
            self._apply_patch_modules(review_module, self.post_terminal_patch_module_names)
            self._apply_patch_modules(review_module, self.candidate_integrity_patch_module_names)
            self._apply_patch_modules(review_module, self.stage_local_patch_module_names)
            self._apply_patch_modules(review_module, self.execution_policy_patch_module_names)
            self._apply_patch_modules(review_module, self.telemetry_patch_module_names)
            self._apply_patch_modules(review_module, self.post_telemetry_patch_module_names)

    def run(self) -> None:
        review_module = self.import_module(self.review_module_name)
        self.apply_runtime_patches(review_module)
        review_module.main()


def main() -> None:
    DcoirReviewEntrypoint().run()
