# DCOIR Review Architecture

## Architectural direction

DCOIR Review is migrating from historical runtime overlays to explicit, responsibility-based composition under issue #550. The production design must make the active review path understandable from imports and pipeline sequencing rather than from issue chronology, numbered patch order, or runtime replacement of functions.

The current migration baseline is `main` after PR #545. At that baseline, `scripts/dcoir_review/entrypoint.py` still imports the Pareto-context review module and applies an ordered series of historical `apply_pareto_context_module(...)` overlays. The package `module_loader.py` also retains segmented source assembly through `exec(compile(...))`. Those mechanisms are migration inputs, not the target extension model.

## Required responsibility boundaries

The consolidated implementation should assign one canonical owner to each active responsibility. Exact package names may change as the dependency inventory is completed, but the stable responsibilities are:

- provider transport: HTTP request/response reads, interruption classification, bounded transport failures, and close/replay behavior;
- provider routing: provider/model selection, attempts, fallback, retry policy, and stage-local routing;
- provider/schema normalization: supported response/schema normalization and fail-closed malformed-output handling;
- detection: deterministic and semantic candidate generation;
- challenge/adjudication: challenger and semantic adjudication behavior;
- verification: verifier authority, exact-head evidence, and supported/suppressed disposition;
- candidate identity: semantic identity, provenance-preserving deduplication, and incremental compatibility;
- quality gate: confidence/actionability floors and fail-closed publication eligibility;
- repair: repair synthesis, critic context, coordinated edit sets, and repair budgets;
- publication: review body and inline finding publication, comment deduplication, and bounded output;
- operator status: one reusable top-level PR status comment for the latest DCOIR Review activity, with formal GitHub review output remaining authoritative;
- telemetry: observational usage/provider/recovery data that cannot change finding disposition;
- pipeline/entrypoint: explicit readable sequencing of the responsibilities above.

A future fix belongs in its canonical responsibility owner. A new numbered production patch is not the normal extension mechanism.

## Characterization checkpoint

The corrected exact-head characterization for Draft PR #553 completed successfully in ChatGPT Exec run `34694686544` against source head `421fb8dbd5b03d068d3abb20b5865e1ccc82b67b`. It used an isolated secondary worktree and verified that the shared harness checkout remained unchanged.

The generated baseline inventory/provenance evidence records:

- `87` inventoried architecture modules;
- `59` production patch applications in the characterized ordered chain;
- numbered production patch ceiling `v58`, with no missing inventory modules;
- `86` loaded patch-module override namespaces represented in final provenance;
- final changed callable surfaces concentrated in the `base`, `hardened`, and `review` namespaces rather than requiring one new owner per historical patch generation.

Public patch-owned callable characterization currently resolves to five base callables, eighteen hardened callables, and thirty review callables, plus historical stored-original compatibility shims. Migration planning should follow the active responsibilities of those callables, not reproduce the historical patch count.

## Staged cutover status

The first canonical extraction is the operator-facing status publication surface required by issue #550 comment `5645826560`:

- `dcoir_review/status.py` owns discovery/reuse and best-effort create/update behavior for the stable hidden status-comment marker;
- the base `ProgressReporter` delegates status publication to that owner regardless of the legacy `post_progress_comment` debug flag;
- the status comment progresses through `Queued`, `Running`, `Completed`, or `Failed`, carries exact-head provenance once the PR head is captured, links the formal GitHub review on completion, bounds repeated same-stage edits, and reuses the same bot-authored comment on reruns;
- status-publication API failures are observational and are not raised into review disposition;
- the previous non-progress failure fallback that could create a separate status-like issue comment has been removed;
- existing v50/v54/v48 gate, telemetry, and exact-head terminal decorators remain temporarily active around `ProgressReporter` during staged migration. This first extraction therefore does not claim that the runtime patch chain has been retired.

The stable status contract is covered by `dcoir_review_status_comment_selftest.py`, including rerun reuse, same-comment identity, exact-head/formal-review rendering, spoofed-user marker rejection, debug-flag independence, and observational write failures. Exact-head status-cutover validation passed in ChatGPT Exec run `34695700055` at source head `efabcaec43676951a596afed06c601dc8486d840`; current-head CodeQL also passed at that source head.

The first historical runtime-overlay retirement moved finding-anchor normalization out of v27:

- the exact changed-line preservation invariant formerly installed by `dcoir_review_required_runtime_patch_v27.py` now lives directly in the canonical `reanchor_finding_to_changed_line(...)` implementation;
- the production entrypoint no longer applies v27, and the obsolete v27 runtime source has been deleted;
- `dcoir_review_anchor_normalization_selftest.py` owns the stable contract: a valid changed-line anchor is immutable, while a genuinely unpostable anchor can still be rescued by bounded heuristic re-anchoring;
- the old `dcoir_review_required_runtime_patch_v27_selftest.py` filename remains only as a temporary compatibility wrapper for the existing validation-command registry and contains no version-specific assertions.

That retirement is exact-head validated. ChatGPT Exec run `34697687314` passed at source head `a94ccfec6171df57da77c839466a67a092ee9139` with architecture inventory reporting 86 modules, 58 production patch applications, maximum v58, and zero missing modules. Runtime provenance confirmed v27 is absent from the production sequence and `reanchor_finding_to_changed_line` is no longer patch-owned. Current-head CodeQL run `34697652006` also passed at that source head.

The second historical runtime-overlay retirement is now staged in source for repair-critic routing:

- `dcoir_review/repair.py` is the canonical repair-policy owner for the independent critic model stack, direct-provider routing controls, and separate repair-critic session namespace;
- the active v25 repair pipeline delegates `_independent_config(...)` directly to that canonical owner, so later repair stages consume the stable policy without runtime replacement;
- the production entrypoint no longer applies `dcoir_review_required_runtime_patch_v29` and the obsolete v29 runtime source has been deleted;
- `dcoir_review_repair_routing_selftest.py` owns the stable contract, including shared-config immutability, the direct GPT-5.6 Terra / Sonnet fallback stack, strict JSON-schema payload behavior, Auto/Pareto-router removal, and explicit v29 absence from production composition;
- the historical `dcoir_review_required_runtime_patch_v29_selftest.py` path remains only as a temporary compatibility wrapper for the governed validation-command registry;
- `repair.py` is declared as an ordinary direct-import owner so orphan-module validation remains fail-closed without misclassifying it as a concatenated runtime segment.

This v29 retirement is not yet exact-head validated. The last validated production patch count is 58 after v27 retirement; source composition after the staged v29 retirement should enumerate 57 production patch applications while retaining `v58` as the maximum numbered version. Governed execution must confirm that expectation before the retirement is called validated.

## Migration invariants

The migration must preserve externally observable behavior before historical layers are removed. In particular:

- partial or interrupted provider responses must never become trusted model output;
- retry/fallback behavior remains bounded and fail-closed;
- verifier-supported evidence remains authoritative for publication;
- exact-head/source-truth requirements remain intact;
- telemetry failure cannot alter review disposition;
- repair budgets and independent critic requirements remain bounded;
- incremental review state must not merge semantically distinct candidates;
- semantically equivalent deterministic and semantic candidates should publish once while retaining provenance and verifier evidence;
- exact-head context supplied to repair logic must remain available to the critic;
- same-day dates must not be classified as future dates solely because of date/time grounding error;
- genuinely orphaned maintained modules remain a validation failure while ordinary direct-import modules are not forced into runtime-segment ownership;
- known-positive canaries retain recall and clean controls remain clean.

## Patch-chain freeze

v58 is the last permitted numbered production runtime patch. Do not add `dcoir_review_required_runtime_patch_v59.py`, v60, or another numbered production overlay as the normal repair pattern. Historical patch source may remain temporarily during characterization and staged cutover inside the #550 implementation PR, but it must not remain the production composition mechanism at completion.

## Retirement rules

Historical patch modules and version-specific self-tests may be deleted only after their required behavior is represented by canonical implementation and stable contract/regression coverage. Git history is the archive for superseded implementation generations; production source should not retain obsolete generations merely as chronology.

The migration must also remove or consolidate stored-original-function shims, cross-generation imports, stale constants, unreachable helpers, and compatibility markers that are no longer required after cutover.

## Architecture enforcement

The final architecture must be mechanically guarded. Validation should fail when:

- a new numbered production patch matching the retired patch-family pattern is introduced without an explicitly documented exception mechanism;
- the production entrypoint returns to applying a sequence of runtime function-replacement overlays as its normal extension model;
- maintained runtime ownership is ambiguous, duplicated, missing, or genuinely orphaned;
- dependency direction recreates cross-generation backreferences or a cycle that makes order implicit behavior.

DCOIR Review does not review changes to itself. Independent GitHub Copilot and External Codex are available independent review lanes, but their trigger requests remain operator-controlled. DCOIR Review should not be restored as a required gate for other PRs until the consolidated implementation has completed its governed deterministic, semantic/canary, provider, publication/deduplication, repair, security, exact-head, and post-merge validation.

## Validation before cutover completion

Before #550 can be considered complete, the exact PR head must pass the governed DCOIR deterministic command set plus semantic recall/precision, provider transport/retry/fallback, malformed/schema/fail-closed, publication/deduplication/candidate-identity, repair-author/critic/budget, security/static, and applicable repository validation. Independent review findings must be dispositioned on the exact head. Post-merge `main` must then be read back and validated before the reviewer is restored to normal gating.
