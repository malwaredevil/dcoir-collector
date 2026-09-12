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
- telemetry: observational usage/provider/recovery data that cannot change finding disposition;
- pipeline/entrypoint: explicit readable sequencing of the responsibilities above.

A future fix belongs in its canonical responsibility owner. A new numbered production patch is not the normal extension mechanism.

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

DCOIR Review does not review changes to itself. Independent GitHub Copilot review is the current self-change review lane, and DCOIR Review should not be restored as a required gate for other PRs until the consolidated implementation has completed its governed deterministic, semantic/canary, provider, publication/deduplication, repair, security, exact-head, and post-merge validation.

## Validation before cutover completion

Before #550 can be considered complete, the exact PR head must pass the governed DCOIR deterministic command set plus semantic recall/precision, provider transport/retry/fallback, malformed/schema/fail-closed, publication/deduplication/candidate-identity, repair-author/critic/budget, security/static, and applicable repository validation. Independent review findings must be dispositioned on the exact head. Post-merge `main` must then be read back and validated before the reviewer is restored to normal gating.
