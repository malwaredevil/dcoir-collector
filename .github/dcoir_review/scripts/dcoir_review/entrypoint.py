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
        'dcoir_review_required_runtime_patch_v4_apply',
        'dcoir_review_required_runtime_patch_v5_apply',
        'dcoir_review_required_runtime_patch_v6',
        'dcoir_review_required_runtime_patch_v7',
        'dcoir_review_required_runtime_patch_v8',
        'dcoir_review_required_runtime_patch_v9',
        'dcoir_review_required_runtime_patch_v10',
        'dcoir_review_required_runtime_patch_v11',
        'dcoir_review_required_runtime_patch_v12',
        'dcoir_review_required_runtime_patch_v13',
        'dcoir_review_required_runtime_patch_v14',
        'dcoir_review_required_runtime_patch_v15',
        'dcoir_review_required_runtime_patch_v16',
        'dcoir_review_required_runtime_patch_v17',
        'dcoir_review_required_runtime_patch_v18',
        'dcoir_review_required_runtime_patch_v19',
        'dcoir_review_required_runtime_patch_v20',
        'dcoir_review_required_runtime_patch_v21',
        'dcoir_review_required_runtime_patch_v22',
        'dcoir_review_required_runtime_patch_v23',
        'dcoir_review_required_runtime_patch_v24',
        'dcoir_review_required_runtime_patch_v25',
        'dcoir_review_required_runtime_patch_v26',
        'dcoir_review_required_runtime_patch_v27',
        'dcoir_review_required_runtime_patch_v29',
        'dcoir_review_required_runtime_patch_v28',
        'dcoir_review_required_runtime_patch_v30',
        # v32 owns adversarial model/prompt/hybrid review behavior. v33 then
        # separates pre-publication verification capacity from the bounded
        # repair budget. v34 strengthens predicate/call-site recall, blank-anchor
        # evidence handling, and debug lifecycle readback. v35 adds a bounded
        # final semantic adjudicator plus falsification-first verifier guidance.
        # v36 upgrades verified repairs from one exact line to bounded coordinated
        # edit sets (multi-line, non-contiguous, and cross-file) while keeping
        # human-only application. v37 strictly normalizes the adjudicator's valid
        # flat-single-finding compatibility shape before v35 capping/publication.
        # v38 makes repair-author confidence advisory, normalizes only missing
        # explanatory repair metadata, and raises the independent critic hard
        # acceptance threshold while preserving exact-head structural checks.
        # v39 handles one additional provider-schema seam: when an otherwise
        # complete semantic-adjudication finding omits confidence, it assigns only
        # the configured normal floor to admit the candidate to v21 verification;
        # verifier support remains mandatory before repair/publication. v31 stays
        # terminal for this historical semantic-patch chain.
        'dcoir_review_required_runtime_patch_v32',
        'dcoir_review_required_runtime_patch_v33',
        'dcoir_review_required_runtime_patch_v34',
        'dcoir_review_required_runtime_patch_v35',
        'dcoir_review_required_runtime_patch_v36',
        'dcoir_review_required_runtime_patch_v37',
        'dcoir_review_required_runtime_patch_v38',
        'dcoir_review_required_runtime_patch_v39',
        'dcoir_review_required_runtime_patch_v31',
    )
    # Architecture-B overlays are deliberately outside the historical semantic
    # patch chain. These run after v31 so old semantic-order invariants remain
    # meaningful while production receives the approved incremental frontier
    # (v41), semantic-ledger/fingerprint foundation (v42), then fail-closed
    # semantic-result reuse on exact compatible evidence (v43).
    terminal_patch_module_names: tuple[str, ...] = (
        'dcoir_review_required_runtime_patch_v41',
        'dcoir_review_required_runtime_patch_v42',
        'dcoir_review_required_runtime_patch_v43',
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
            # patch subset; Architecture-B terminal overlays are a production
            # default, not an implicit addition to custom test/probe subsets.
            self._apply_patch_modules(review_module, patch_module_names)
            return
        self._apply_patch_modules(review_module, self.patch_module_names)
        self._apply_patch_modules(review_module, self.terminal_patch_module_names)

    def run(self) -> None:
        review_module = self.import_module(self.review_module_name)
        self.apply_runtime_patches(review_module)
        review_module.main()


def main() -> None:
    DcoirReviewEntrypoint().run()
