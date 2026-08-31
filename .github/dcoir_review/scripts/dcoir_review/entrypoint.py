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
        # human-only application. v31 remains terminal because it does not
        # overwrite these review surfaces.
        'dcoir_review_required_runtime_patch_v32',
        'dcoir_review_required_runtime_patch_v33',
        'dcoir_review_required_runtime_patch_v34',
        'dcoir_review_required_runtime_patch_v35',
        'dcoir_review_required_runtime_patch_v36',
        'dcoir_review_required_runtime_patch_v31',
    )

    def import_module(self, module_name: str) -> ModuleType:
        return importlib.import_module(module_name)

    def apply_runtime_patches(
        self,
        review_module: ModuleType,
        patch_module_names: Iterable[str] | None = None,
    ) -> None:
        for module_name in tuple(patch_module_names or self.patch_module_names):
            patch_module = self.import_module(module_name)
            apply_patch = getattr(patch_module, "apply_pareto_context_module", None)
            if apply_patch is None:
                raise RuntimeError(f"Runtime patch module {module_name} does not expose apply_pareto_context_module")
            apply_patch(review_module)

    def run(self) -> None:
        review_module = self.import_module(self.review_module_name)
        self.apply_runtime_patches(review_module)
        review_module.main()


def main() -> None:
    DcoirReviewEntrypoint().run()
