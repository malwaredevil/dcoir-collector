# DCOIR Review Architecture

## Architectural direction

DCOIR Review is migrating from historical runtime overlays to explicit, responsibility-based composition under issue #550. The production design must make the active review path understandable from imports and pipeline sequencing rather than from issue chronology, numbered patch order, or runtime replacement of functions.

The current migration baseline is `main` after PR #545. At that baseline, `scripts/dcoir_review/entrypoint.py` still imports the Pareto-context review module and applies an ordered series of historical `apply_pareto_context_module(...)` overlays. The package `module_loader.py` also retains segmented source assembly through `exec(compile(...))`. Those mechanisms are migration inputs, not the target extension model.

## Maintainer-readability and consolidation standard

The architecture migration is judged by maintainability and actual ownership collapse, not by cosmetic renaming. Canonical files and packages must represent stable responsibilities, and active functions must have one obvious authoritative owner or a deliberately small explicit composition. Historical patch boundaries do not define the target module boundaries.

A rename, file move, alias, forwarding wrapper, or one-for-one `v## -> friendly_name.py` translation is not sufficient progress when the same duplicate implementations, runtime replacement chain, stored-original shims, or hidden mutation order still exist. Surviving behavior should be merged into responsibility-based owners; superseded/dead implementations and unnecessary compatibility wrappers should be removed once characterization and parity evidence make that safe. Version labels remain only where they are genuine external/schema/protocol/persisted-data compatibility contracts.

Stable tests must protect product behavior, canonical ownership, explicit composition, and security/reliability invariants. They must not require obsolete patch registration or historical ordering solely to preserve the old architecture. Each credited slice should demonstrate a measurable structural improvement such as fewer override chains, superseded callable installations, stored-original callables, numbered final owners, duplicate definitions, or historical source paths while preserving required behavior.

**Maintainer test:** a professional programmer new to the repository should be able to locate the authoritative implementation, understand how the active path is composed, and make a future fix from normal module/function structure without reconstructing issue chronology or walking backward through `_v##` files. If this is not true for a responsibility, its migration is incomplete.

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
- existing v50/v54 gate and telemetry decorators remain temporarily active around `ProgressReporter` during staged migration. This first extraction therefore does not claim that the runtime patch chain has been retired.

The stable status contract is covered by `dcoir_review_status_comment_selftest.py`, including rerun reuse, same-comment identity, exact-head/formal-review rendering, spoofed-user marker rejection, debug-flag independence, and observational write failures. Exact-head status-cutover validation passed in ChatGPT Exec run `34695700055` at source head `efabcaec43676951a596afed06c601dc8486d840`; current-head CodeQL also passed at that source head.

The first historical runtime-overlay retirement moved finding-anchor normalization out of v27:

- the exact changed-line preservation invariant formerly installed by `dcoir_review_required_runtime_patch_v27.py` now lives directly in the canonical `reanchor_finding_to_changed_line(...)` implementation;
- the production entrypoint no longer applies v27, and the obsolete v27 runtime source has been deleted;
- `dcoir_review_anchor_normalization_selftest.py` owns the stable contract: a valid changed-line anchor is immutable, while a genuinely unpostable anchor can still be rescued by bounded heuristic re-anchoring;
- the governed validation-command registry now names the stable `dcoir_review_anchor_normalization_selftest.py` contract directly, and the obsolete v27 compatibility wrapper has been deleted; Git history remains the record of the retired filename.

That retirement is exact-head validated. ChatGPT Exec run `34697687314` passed at source head `a94ccfec6171df57da77c839466a67a092ee9139` with architecture inventory reporting 86 modules, 58 production patch applications, maximum v58, and zero missing modules. Runtime provenance confirmed v27 is absent from the production sequence and `reanchor_finding_to_changed_line` is no longer patch-owned. Current-head CodeQL run `34697652006` also passed at that source head.

The second historical runtime-overlay retirement moved repair-critic routing out of v29:

- `dcoir_review/repair.py` is the canonical repair-policy owner for the independent critic model stack, direct-provider routing controls, and separate repair-critic session namespace;
- the active repair pipeline delegates independent-critic configuration directly to that canonical owner, so later repair stages consume stable policy without runtime replacement;
- the production entrypoint no longer applies `dcoir_review_required_runtime_patch_v29` and the obsolete v29 runtime source has been deleted;
- `dcoir_review_repair_routing_selftest.py` owns the stable contract, including shared-config immutability, the direct GPT-5.6 Terra / Sonnet fallback stack, strict JSON-schema payload behavior, Auto/Pareto-router removal, and explicit v29 absence from production composition;
- the governed validation-command registry names `dcoir_review_repair_routing_selftest.py` directly, and the obsolete v29 compatibility wrapper has been deleted rather than retained as repository history;
- `repair.py` is declared as an ordinary direct-import owner so orphan-module validation remains fail-closed without misclassifying it as a concatenated runtime segment.

The third historical retirement removed the oversized v25 repair-pipeline owner:

- production composition now loads `dcoir_review.repair_pipeline` at the former v25 position, preserving repair-stage ordering without a numbered runtime module;
- `dcoir_review/repair_support.py` owns prompt construction, parsing, verifier-provenance cleanup, and exact-line replacement validation, while `repair_pipeline.py` owns repair composition and the bounded compatibility hooks still used by later staged retirements;
- later not-yet-retired repair overlays import the stable repair-pipeline namespace instead of importing v25, eliminating their direct dependency on the deleted historical module;
- the permanent repair modules remain under the 15,000-byte connector-safe source limit and the runtime-module self-test enforces that limit for direct-import modules as well as concatenated segments;
- `dcoir_review_repair_pipeline_selftest.py` owns the stable repair contract, the governed validation registry names it directly, and the obsolete v25 runtime/self-test files are deleted; Git history remains the archive.

The v29 and v25 retirements are exact-head validated together with the earlier v27 retirement. ChatGPT Exec run `34710041549` passed at source head `de2bb9c23dc1c72c2e22b425e3a710a42bb75020`; its artifact records 57 production components, maximum numbered version 58, and `retired=v25,v27,v29`. Current-head CodeQL run `34709741071` and Dependency Review run `34709741014` also passed, and all three GHAS review threads are resolved and outdated.

The next bounded retirement moves repair operational reliability out of historical v28:

- `dcoir_review/repair_reliability.py` owns repair-author/critic execution, fail-closed stage handling, bounded diagnostics, and the established v28 compatibility provenance/debug contract;
- `dcoir_review/repair_render.py` owns verified-repair GitHub rendering and native suggestion-fence safety;
- `repair_pipeline.py` delegates to those permanent owners directly instead of requiring a v28 runtime overlay, while retaining the bounded `_build_repair_for_finding` compatibility hook consumed by later not-yet-retired overlays such as v33;
- v30 now wraps the stable repair-reliability owner rather than importing a numbered v28 module;
- the production entrypoint no longer applies v28, the historical v28 runtime file is deleted, and `dcoir_review_repair_reliability_selftest.py` replaces the historical v28 self-test path;
- the runtime module-loader registry classifies the new owners as direct-import modules, preserving fail-closed orphan detection and the connector-safe source-size rule.

This v28 retirement is exact-head validated. ChatGPT Exec run `34714762351` passed at source head `1be96623305fdaca08ddb7f686f480ca8525c97b`; its artifact records 56 production components, maximum numbered version 58, `retired=v25,v27,v28,v29`, stable repair pipeline/reliability/render ownership, and the explicit terminal marker `ISSUE550_PR553_V28_RETIREMENT_VALIDATION_002_PASS`. Current-head CodeQL run `34714292707` and Dependency Review run `34714292700` also passed, and all 21 GHAS review threads are resolved and outdated.

The next bounded retirement moves immutable ordinary-finding / deterministic-sentinel selection out of historical v26:

- `dcoir_review/sentinel_selection.py` owns the v26 invariant that normalized ordinary model findings remain unchanged unless selection output has provenance matching a real changed-code risk sentinel;
- production composition loads `dcoir_review.sentinel_selection` at the former v26 position, preserving ordering while removing the numbered production overlay;
- the stable owner intentionally retains the existing v16 sentinel-key helper dependency for this bounded slice rather than widening the change into the much larger historical sentinel-classification migration; that backreference remains explicit debt for a later responsibility-based retirement;
- `dcoir_review_sentinel_selection_selftest.py` replaces the historical v26 self-test and extends the contract with a characterized real-sentinel case proving deterministic priority does not rewrite an ordinary model finding at the same site;
- the runtime module-loader registry classifies the stable owner as a direct-import module, and the governed validation-command registry names the stable contract test directly;
- the historical v26 runtime and version-specific self-test files are removed; Git history remains the archive.

This v26 retirement is exact-head validated. ChatGPT Exec run `34744968256` passed at source head `bcabb8d69f9c2a52399c533fce812fdaf3030f8d`; its artifact records 56 production components, maximum numbered version 58, `retired=v25,v26,v27,v28,v29`, stable `dcoir_review.sentinel_selection` ownership, and terminal marker `ISSUE550_PR553_V26_SENTINEL_SELECTION_VALIDATION_001_PASS`. Current-head CodeQL run `34744704692` and Dependency Review run `34744704821` also passed, and all 21 observed GHAS review threads remain resolved and outdated.

The next bounded retirement moves verifier-aware ordinary-finding rendering out of historical v24:

- `dcoir_review/verified_finding_render.py` owns the v24 contract that independently verified ordinary semantic findings retain their verified title/body and repair guidance instead of being rewritten through deterministic sentinel templates;
- deterministic/sentinel-backed findings continue through the pre-existing canonical renderer unchanged;
- production composition loads the stable owner at the former v24 position, after v23 selection compatibility and before the canonical repair pipeline, preserving runtime ordering without a numbered v24 owner;
- `dcoir_review_verified_finding_render_selftest.py` replaces the historical v24 self-test and mechanically asserts the stable owner position plus the verified-ordinary/deterministic-sentinel rendering split;
- the runtime module-loader registry classifies the stable owner as a direct-import module and the governed validation-command registry names the stable contract test directly;
- the historical v24 runtime and version-specific self-test files are removed; Git history remains the archive.

This v24 retirement is exact-head validated. ChatGPT Exec run `34746090998` passed at source head `11a7297678ab65930da4ff96bb64af6bed51388b`; its artifact records 56 production components, maximum numbered version 58, `retired=v24,v25,v26,v27,v28,v29`, stable `dcoir_review.verified_finding_render` ownership, and terminal marker `ISSUE550_PR553_V24_VERIFIED_FINDING_RENDER_VALIDATION_001_PASS`. Current-head CodeQL run `34745679351` also passed; Dependency Review is not enabled for this repository, and the 21 observed historical GHAS review threads remain resolved/outdated.

The next bounded retirement moves normalized-finding selection compatibility out of historical v23:

- `dcoir_review/normalized_finding_selection.py` owns the v23 contract that sentinel/required coverage retains priority while otherwise-eligible normalized model findings dropped by legacy required-coverage selection are restored only into spare inline capacity;
- occupied sentinel sites and exact selected identities remain protected from duplicate restoration, and v21 remains the downstream publication gate for restored ordinary candidates;
- production composition loads the stable owner at the former v23 position, after `dcoir_review.quality_gate` and immediately before `dcoir_review.verified_finding_render`;
- `dcoir_review_normalized_finding_selection_selftest.py` replaces the historical v23 self-test and mechanically asserts stable composition plus ordinary-candidate survival and one-comment sentinel priority;
- the runtime module-loader registry and governed validation-command registry reference the stable owner/test directly;
- the historical v23 runtime and version-specific self-test files are removed; Git history remains the archive.

This v23 retirement is locally staged only. Exact-head GitHub validation and current-head security workflow readback remain required after publication before the slice can be credited as governed validated.

The next bounded retirement moves finding-family compatibility out of historical v15:

- `dcoir_review/finding_family.py` owns stable finding-family classification and family-priority compatibility;
- production composition loads the stable owner at the former v15 position between v14 and v16;
- v16 now imports the stable finding-family owner instead of the historical v15 module;
- `dcoir_review_finding_family_selftest.py` replaces the version-specific v15 self-test and adds an exact composition assertion;
- the v14 import-compatibility regression now exercises the stable owner;
- runtime module ownership and the governed validation-command registry reference the stable module/test directly;
- the historical v15 wrapper, segmented implementation, and version-specific self-test are removed; Git history remains the archive.

This v15 retirement is exact-head validated. ChatGPT Exec run `34752978482` passed at source head `0e6106705b7231e785e3934adc2097b3bfaff61d` with terminal marker `ISSUE550_PR553_V15_FINDING_FAMILY_VALIDATION_001_PASS`; its artifact confirms 56 production components, maximum numbered version 58, and `retired=v15,v23,v24,v25,v26,v27,v28,v29`. The same exact head includes the v16 split-module dependency regression that caught and repaired the intervening GHAS unused-import Autofix break. Current-head CodeQL run `34750501850` passed Actions, Python, and aggregate reporting.

The next bounded retirement moves summary-only semantic recovery out of historical v22:

- `dcoir_review/quality_gate.py` owns the stable quality-gate contract that recognizes actionable semantic problem language when structured findings are empty while suppressing explicit negations, zero-count findings, and neutral schema-only references;
- the stable owner also preserves the bounded whole-PR quality-retry path at the former v22 composition point, immediately before `dcoir_review.normalized_finding_selection`;
- the stable quality gate explicitly tags its retry configuration as `broad-quality-retry`, removing the historical filename-inspection dependency from telemetry classification;
- private compatibility storage and debug artifact paths now use stable quality-gate/semantic-retry names rather than version chronology;
- `dcoir_review_quality_gate_selftest.py` replaces the version-specific v22 self-test and asserts both semantic positive/negative precision and exact stable-owner composition;
- runtime module ownership and the governed validation-command registry reference the stable module/test directly;
- the historical v22 runtime and version-specific self-test files are removed; Git history remains the archive.

This v22 quality-gate retirement is exact-head validated. ChatGPT Exec run `34754938413` passed at source head `2e6d47a3d25e5ccb33d0a91fbc1bb260ff266c94` with terminal marker `ISSUE550_PR553_V22_QUALITY_GATE_VALIDATION_001_PASS`; its artifact confirms 56 production components, maximum numbered version 58, and `retired=v15,v22,v23,v24,v25,v26,v27,v28,v29`. Current-head CodeQL run `34754683222` passed Python, Actions, and aggregate reporting on the same source head.

The next bounded retirement moves candidate-finding evidence verification out of historical v21:

- `dcoir_review/finding_verifier.py` owns the bounded publication-verification contract for ordinary model findings and deterministic core sentinels;
- ordinary findings require exact anchored head-file evidence plus a fail-closed model verifier, while deterministic core sentinels remain evidence-verified without allowing a model veto;
- the existing `_dcoir_verifier_v21` finding marker is intentionally preserved as a compatibility data contract during this behavior-preserving migration;
- stable downstream owners (`verified_finding_render.py`, `repair_support.py`, and `repair_pipeline.py`) now depend directly on `dcoir_review.finding_verifier`; historical overlays that still consume the verifier resolve that dependency through the stable owner path;
- `dcoir_review_finding_verifier_selftest.py` replaces the version-specific v21 self-test and asserts exact stable composition between v20 and `dcoir_review.quality_gate`;
- runtime module ownership and the governed validation-command registry reference the stable module/test directly;
- the historical v21 runtime and version-specific self-test files are removed; Git history remains the archive.

This v21 finding-verifier retirement is exact-head validated. ChatGPT Exec run `34757094524` passed at source head `f42b9d43ea637cc88a5f13329f655b7352b85d84` with terminal marker `ISSUE550_PR553_V21_FINDING_VERIFIER_VALIDATION_001_PASS`; its artifact confirms 56 production components, maximum numbered version 58, and `retired=v15,v21,v22,v23,v24,v25,v26,v27,v28,v29`. Current-head CodeQL run `34756805023` passed Actions, Python, and aggregate reporting on the same source head.

The next bounded retirement moves precision guarding out of historical v19:

- `dcoir_review/precision_guard.py` owns language-scoped sentinel suppression, fail-closed fix-synthesis contradiction detection, and bounded repair-outcome telemetry as one precision responsibility;
- the externally meaningful `metadata/fix-synthesis-outcomes-v19.json` path and `v19` artifact schema marker are intentionally preserved as compatibility data contracts, while private stored-original names move to stable precision-guard ownership;
- `dcoir_review_precision_guard_selftest.py` replaces the version-specific v19 self-test and asserts both behavior and exact stable composition between v18 and v20;
- runtime composition, direct-import ownership, and the governed validation-command registry reference the stable owner/test directly;
- the historical v19 runtime and version-specific self-test files are removed; Git history remains the archive.

The v19 precision-guard retirement is exact-head governed validated on corrective source head `f57eab7464beb601ce350833a6152e5b6d77b20e`. Recovery ChatGPT Exec run `34760172201` passed after the architecture document was restored to the already-validated tree, and current-head CodeQL run `34759462183` passed on that exact head.

## v34 semantic-evidence hardening retirement

Historical v34 runtime ownership is retired into `dcoir_review.semantic_evidence_hardening`. The stable owner preserves the predicate/call-site audit requirements used by primary and independent semantic review, distinguishes an intentionally blank changed-line anchor from missing evidence for the finding verifier, and records the bounded verifier input/output debug manifests. v35 consumes the stable predicate-audit contract directly.

The historical debug artifact paths `metadata/v34-verifier-input.json` and `responses/v34-verifier-output.json`, plus their `dcoir_review_v34_*` schema identifiers, remain compatibility data and do not imply continuing v34 runtime ownership. The stable self-test owns the predicate-audit, blank-anchor, verifier lifecycle, composition-order, and idempotence regressions.

## v45 publication-disposition retirement

Historical v45 runtime ownership is retired into `dcoir_review.publication_disposition`. The stable owner records the exact-head verifier disposition and builds the final GitHub review body only from verifier-authoritative findings plus the final repaired set; model-authored summary prose, unanchored hypotheses, and legacy overflow prose cannot bypass publication verification.

The historical `metadata/final-publication-disposition-v45.json` artifact path, `dcoir_review_final_publication_disposition_v1` schema, and `v45` version value remain compatibility/provenance data for downstream gate-state recovery. v50 gate-state code and architecture benchmarks import the stable publication owner directly. The stable self-test owns the publication body, exact-head disposition, configuration, and composition regressions. Historical v45 production/self-test files are removed; Git history remains the archive.

This slice must not be credited as governed validated until publication readback and exact-head validation pass on the published PR head.

## v47 per-file routing retirement

The next bounded retirement moves stage-local first-pass routing out of historical v47:

- `dcoir_review/per_file_routing.py` owns per-file configuration projection, calibrated Sonnet routing controls, Response Healing payload projection, and bounded per-file request telemetry attachment;
- the shared OpenRouter payload builder is installed once by `dcoir_review.per_file_routing`: v32 contributes its GPT-5/reasoning compatibility contract through `apply_reasoning_payload_policy(...)` instead of wrapping the builder, so the final payload path is `base hardened builder -> explicit v32 reasoning policy -> per-file routing projection` without v32/per-file stored-original payload shims;
- production composition loads `dcoir_review.per_file_routing` in the stage-local position instead of the numbered v47 overlay;
- the historical `dcoir_v47_per_file_projection` attribute value is intentionally preserved as a compatibility/provenance data marker, while `PER_FILE_PROJECTION_ATTR` in the stable owner becomes its canonical definition;
- v54 telemetry imports that stable marker constant instead of hard-coding a dependency on historical v47 ownership;
- `dcoir_review_per_file_routing_selftest.py` owns the stable behavioral contract, and the validation registry plus review-scope composition regression reference the stable owner directly;
- the runtime module-loader registry classifies `per_file_routing.py` as an ordinary direct-import owner;
- the historical v47 runtime and version-specific self-test files are removed; Git history remains the archive.

This slice must not be credited as governed validated until publication readback and separately approved exact-head validation pass on the published PR head.

## v48 review-scope guard retirement

The historical v48 exact-scope execution policy is now responsibility-owned rather than version-owned:

- `dcoir_review/review_scope_guard.py` owns immutable PR head/base scope state, fail-closed live-scope verification, request authorization, stale-head terminal classification, and the stable stale-head debug artifact contract;
- `dcoir_review/review_scope_guard_hooks.py` owns the provider, publication, progress-reporter, and main-path hooks that enforce that state without changing workflow concurrency;
- production composition loads `dcoir_review.review_scope_guard` immediately before `dcoir_review.prompt_review_scope_guard`, preserving the historical execution-policy ordering before v52/v53;
- `dcoir_review.prompt_review_scope_guard` now delegates to the stable review-scope owner for the legacy v6 direct prompt-review request;
- v52 structured-output recovery now imports the stable review-scope owner and uses the stable stored-provider boundary name while preserving the exact-scope checks around recovered requests;
- private `_dcoir_review_v48_*` storage and apply markers are retired because they were implementation history, not compatibility data; the externally meaningful `metadata/stale-head-supersession.json` path, `dcoir_review_stale_head_guard_v1` schema, and terminal prefixes are preserved;
- `dcoir_review_review_scope_guard_selftest.py` plus its stable support module own the deterministic supersession/publication regression contract;
- the historical v48 wrapper/core/hooks, version-specific selftest/support, and earlier prompt-review companion source are removed; Git history remains the archive.

This slice must not be credited as governed validated until publication readback and exact-head validation pass on the published PR head.

### Provider transport retry retirement

The next bounded retirement moves interrupted provider response-read recovery out of historical v58:

- `dcoir_review/provider_transport_retry.py` owns transient transport-failure classification, interrupted HTTP error-body replay, bounded reuse of the existing retry/fallback loop, and transport-failure telemetry projection;
- production composition loads `dcoir_review.provider_transport_retry` immediately after v54 telemetry and before stable semantic-adjudication recovery plus the remaining v56-v57 post-telemetry overlays;
- `dcoir_review_provider_transport_retry_selftest.py` remains the stable behavioral contract and imports the stable owner directly;
- the runtime module-loader guard keeps 58 as the historical ceiling, rejects v59+, and also rejects reintroduction of retired v58 production ownership while allowing the highest remaining numbered overlay to fall below 58;
- the historical v58 production module is removed; Git history remains the archive.

This slice must not be credited as governed validated until publication readback and separately approved exact-head validation pass on the published PR head.

### Semantic-adjudication recovery retirement

The next bounded retirement moves the #524 valid-JSON/schema-shape recovery out of historical v55:

- `dcoir_review/semantic_adjudication_recovery.py` owns the narrow adjudicator-shape fallback and stable semantic-candidate-identity-aware exact deduplication used before adjudication;
- canonical and complete flat-finding results remain on the existing v35/v37 path, while only the proven unsupported valid-object shape may retain already-structured upstream hypotheses for independent verification;
- recovery stays bounded to the active production ranker and verifier capacity, performs no extra model call, and preserves the stable `_semantic_adjudication_shape_recovery` result marker consumed by downstream disposition logic;
- production composition loads `dcoir_review.semantic_adjudication_recovery` after provider transport retry and before the remaining v56-v57 post-telemetry overlays;
- `dcoir_review_semantic_adjudication_recovery_selftest.py` owns the stable behavioral contract, including fail-closed malformed-shape coverage and semantic-identity preservation;
- the historical `v55` marker value is retained only as compatibility/provenance data inside the recovery marker; the historical v55 production module and version-specific self-test are removed.

This slice must not be credited as governed validated until publication readback and separately approved exact-head validation pass on the published PR head.

### Semantic-candidate identity retirement

Historical v51 runtime ownership is retired into an explicit stable responsibility:

- `dcoir_review/semantic_candidate_identity.py` owns candidate IDs, semantic keys, risk-provenance discrimination, ranking-boundary identity protection, and the stable candidate-identity contract;
- `dcoir_review/semantic_candidate_identity_hooks.py` owns the bounded final-selector and verifier hook installation and receives the stable owner explicitly, avoiding a reciprocal import/cycle;
- production composition loads `dcoir_review.semantic_candidate_identity` in the existing candidate-integrity position before stage-local routing;
- stable semantic-adjudication recovery imports the stable identity owner directly for exact candidate-key derivation and no longer depends on historical v51 runtime ownership;
- `_dcoir_v51_candidate_id`, `_dcoir_v51_semantic_candidate_key`, `metadata/v51-*`, `dcoir_review_v51_*`, and the `v51:` contract/version marker remain compatibility/provenance data because durable diagnostics and recovery consume those values;
- `dcoir_review_semantic_candidate_identity_selftest.py` owns the stable behavioral contract, including semantic/risk identity preservation, final selection, verifier provenance, composition, and compatibility-data assertions;
- the runtime module-loader guard classifies both stable modules as direct imports and rejects reintroduction of historical v51 production ownership;
- the historical v51 production module and version-specific self-test are removed; Git history remains the archive.

This slice must not be credited as governed validated until publication readback and exact-head validation pass on the published PR head.

### Semantic-adjudication normalization retirement

The next bounded retirement moves semantic-adjudicator result-shape compatibility out of historical v37:

- `dcoir_review/semantic_adjudication_normalization.py` owns the narrow normalization contract for canonical findings envelopes and the complete flat-single-finding compatibility shape; malformed or partial shapes still fail closed;
- production composition loads `dcoir_review.semantic_adjudication_normalization` at the former v37 position between v36 and v38, preserving the historical semantic ordering without numbered ownership;
- `dcoir_review_required_runtime_patch_v44_execution.py` and stable `dcoir_review/semantic_adjudication_recovery.py` now import the stable normalizer instead of the historical v37 module;
- `dcoir_review_semantic_adjudication_normalization_selftest.py` owns the stable regression contract, including canonical/flat shape handling, capping, malformed-output rejection, the original live-loss seam, and idempotent application;
- the runtime module-loader guard classifies the stable owner as a direct-import module and rejects reintroduction of historical v37 production ownership;
- the historical v37 production module and version-specific self-test are removed; Git history remains the archive.

This slice must not be credited as governed validated until publication readback and separately approved exact-head validation pass on the published PR head.

### Semantic-adjudication confidence retirement

The next bounded retirement moves semantic-adjudicator confidence compatibility out of historical v39:

- `dcoir_review/semantic_adjudication_confidence.py` owns the narrow confidence contract for semantic-adjudicator output, preserving valid supplied confidence and admitting otherwise-complete missing/null confidence only at the configured normal floor for independent verification; malformed confidence remains fail-closed;
- production composition loads `dcoir_review.semantic_adjudication_confidence` at the former v39 position between v38 and v31, preserving historical semantic ordering without numbered ownership;
- stable `dcoir_review/semantic_adjudication_recovery.py` and `dcoir_review_required_runtime_patch_v44_execution.py` import the stable confidence owner instead of historical v39;
- `dcoir_review_semantic_adjudication_confidence_selftest.py` owns the stable regression contract for prompt requirements, supplied-confidence preservation, missing/null confidence admission, verifier handoff, malformed-result rejection, configured-floor validation, and idempotent application;
- the historical debug artifact path `responses/07-v39-confidence-normalized.json` and schema value `dcoir_review_v39_confidence_normalization_v1` remain compatibility/provenance data only;
- the runtime module-loader guard classifies the stable owner as a direct-import module and rejects reintroduction of historical v39 production ownership;
- the historical v39 production module and version-specific self-test are removed; Git history remains the archive.

This slice must not be credited as governed validated until publication readback and separately approved exact-head validation pass on the published PR head.

### Structured-result recovery retirement

The bounded structured-output recovery and near-threshold disposition responsibility is now owned by stable modules rather than historical v52 production ownership:

- `dcoir_review/structured_result_recovery.py` owns the deterministic provider-envelope recovery and bounded low-confidence disposition helper setup; canonical hybrid composition is owned by `dcoir_review.review_orchestration`;
- `dcoir_review/structured_result_provider.py`, `structured_result_disposition.py`, and `structured_result_retry.py` own provider parsing/recovery, candidate-scoped disposition, and fail-closed whole-PR retry fallback respectively;
- production composition loads `dcoir_review.review_orchestration` between the stable prompt review-scope guard and v53; that owner initializes structured-result recovery helpers and composes the hybrid lifecycle once, preserving the characterized execution order without sequential wrapper ownership;
- v54 telemetry imports the stable disposition contract and recognizes the stable retry owner rather than hard-coding the historical v52 module filename;
- the literal `v52` version, `_dcoir_v52_allow_low_confidence_disposition`, `_dcoir_v52_pending_low_confidence_disposition`, `_dcoir_v52_last_structured_output_recovery`, `metadata/v52-structured-low-confidence.json`, and `10-v52-*` debug artifact paths remain compatibility/provenance data because telemetry, diagnostics, and durable artifacts consume those values;
- `dcoir_review_structured_result_recovery_selftest.py` owns the stable behavioral contract for deterministic/fail-closed envelope recovery and single bounded independent disposition;
- the runtime module-loader guard classifies all four stable modules as direct imports and rejects reintroduction of historical v52 production ownership;
- the historical v52 production/helper modules and version-specific self-test are removed; Git history remains the archive.

This slice must not be credited as governed validated until publication readback and exact-head validation pass on the published PR head.
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

### Repair-author/critic contract retirement

The next bounded retirement moves repair-author/critic output-contract hardening out of historical v38:

- `dcoir_review/repair_contract.py` owns the non-semantic repair-author metadata normalization, explicit author/critic prompt contracts, advisory author-confidence posture, and independent critic confidence acceptance/range checks;
- production composition loads `dcoir_review.repair_contract` at the former v38 position between semantic-adjudication normalization and semantic-adjudication confidence, preserving execution order without numbered ownership;
- `dcoir_review_repair_contract_selftest.py` and `dcoir_review_repair_contract_critic_selftest.py` own the stable behavioral/fail-closed regression contract;
- private apply/original-function storage markers use responsibility-based names because no externally meaningful v38 artifact/schema contract requires historical marker preservation;
- the runtime module-loader guard classifies `repair_contract.py` as a direct-import module and rejects reintroduction of historical v38 production ownership;
- the historical v38 production module and version-specific self-tests are removed; Git history remains the archive.

This slice must not be credited as governed validated until publication readback and separately approved exact-head validation pass on the published PR head.

## Patch-chain freeze

v58 was the last permitted numbered production runtime patch and is now retired from production composition. Do not add `dcoir_review_required_runtime_patch_v59.py`, v60, or another numbered production overlay as the normal repair pattern, and do not reintroduce retired v58, v55, v39, v38, or v37 ownership. Historical patch source may remain temporarily during characterization and staged cutover inside the #550 implementation PR, but it must not remain the production composition mechanism at completion.

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

### v50 verified-finding gate retirement

`dcoir_review.verified_finding_gate` now owns incremental unresolved verified-finding gate composition. Pure gate rules and persisted compatibility contracts live in `verified_finding_gate_state.py`, while trusted prior-run artifact/readback logic lives in `verified_finding_gate_prior.py`. Historical v50 production and version-named self-test ownership is retired. The compatibility version `v50`, gate contract identifiers, and `metadata/*-v50.json` artifact paths remain unchanged because prior-run recovery consumes them as durable data rather than source ownership.

### v41 incremental review frontier retirement

`dcoir_review.incremental_review_frontier` now owns Architecture-B incremental review-frontier composition. `incremental_review_state.py` owns trusted prior-review/HMAC provenance parsing, `incremental_review_scope.py` owns incremental-versus-cumulative scope resolution, and `incremental_review_frontier_hooks.py` owns runtime wiring. Historical v41 production/helper/self-test ownership is retired. Compatibility values including `v41`, `architecture-b-v1`, review/base/provenance marker text, trusted workflow identity, and frontier-signature payload semantics remain unchanged. Internal v41-prefixed scope/storage attributes are replaced by responsibility-named implementation markers.

### v42 semantic-review ledger retirement

The historical v42 semantic-ledger patch family is retired from production ownership. `dcoir_review.semantic_review_ledger` is the stable composition owner, with `semantic_review_ledger_builder`, `semantic_review_ledger_contract`, `semantic_review_ledger_fingerprints`, and `semantic_review_ledger_hooks` as explicit responsibility helpers. The `v42` version value, `architecture-b-semantic-ledger-v1` contract, `DCOIR semantic ledger: ` marker, `_dcoir_v42_semantic_review_ledger` client attribute, dependency-context/reuse metadata, and review-context payload fields remain compatibility data rather than source ownership labels.

### v43 semantic-result reuse retirement

The historical v43 semantic-result reuse overlay is retired from production ownership. `dcoir_review.semantic_result_reuse` owns fail-closed reuse orchestration and ledger telemetry, while `semantic_result_reuse_support.py` owns deterministic reuse identity, trusted prior-manifest validation/readback, and manifest persistence. The compatibility version `v43`, `architecture-b-semantic-result-reuse-v1`, `dependency-context-v2`, `exact-semantic-prompt-v1`, and `metadata/semantic-result-reuse-manifest.json` remain durable data contracts. Private runtime state/apply markers are responsibility-named rather than version-named.

### Canonical configuration consolidation

The canonical Pareto loader now parses configuration once and delegates post-base DCOIR settings to `dcoir_review.review_config.apply_review_config`. This replaces the sequential config-loader wrappers formerly installed by v32, v35, v44, publication disposition, v46, verified-finding gate, semantic candidate identity, per-file routing, v54, and v56. Those modules retain only their non-configuration responsibilities; the runtime-loader self-test prevents config-wrapper reintroduction and verifies final loader ownership remains canonical.


### Canonical hybrid-review orchestration consolidation

`dcoir_review.review_orchestration` is the single production owner of `openrouter_review_with_hybrid_first_pass`. The prior runtime shape replaced that callable repeatedly across quality gating, adversarial confirmation, semantic adjudication, confidence normalization, semantic-ledger lifecycle, semantic-result reuse, candidate-scoped escalation, canonical semantic context/adaptive budgets, exact-scope terminal translation, and structured-result disposition. Those responsibilities now expose explicitly named stage builders and no longer install or store their own hybrid wrapper.

The canonical stage order is explicit and mechanically guarded: quality gate -> adversarial confirmation -> semantic adjudication -> adjudication-confidence normalization -> semantic review ledger -> semantic-result reuse -> candidate-scoped escalation -> canonical semantic context/adaptive budgets -> review-scope terminal translation -> structured-result disposition. `review_orchestration` composes those stages around the pre-existing Pareto hybrid implementation and installs one final callable. Reapplication is idempotent, participating modules may not reintroduce `original_hybrid_first_pass` storage shims, and later production modules may not replace the canonical owner.

This consolidation deliberately leaves each participant's non-hybrid responsibilities in place until their own functional areas are dispositioned. For example, semantic-review ledger debug/context hooks, semantic-result per-file reuse, v46 prompt/context projections, review-scope provider/publication guards, and structured-result provider/retry helpers remain separate responsibilities. Historical numbered files are not deleted merely because one of their responsibilities moved; deletion occurs only when every live responsibility in that file has been moved, proven superseded/dead, or retained solely as a compatibility contract.

### Canonical inline finding/comment rendering consolidation

`dcoir_review.finding_comment_render` is the single production owner of `base.build_inline_comment`. Historical runtime layers had installed the same callable fifteen times, but v16 fully superseded the first ten renderer generations. The production-observable rendering chain was therefore v30 deterministic-sentinel canonicalization -> repair rendering -> verified-ordinary rendering -> v20 safe native-suggestion handling -> v16 deterministic base rendering.

The canonical renderer expresses that surviving behavior directly and installs one final callable immediately after v30. Earlier patch layers retain their unrelated detection, selection, prompting, synthesis, and repair responsibilities but no longer replace `build_inline_comment` or store prior renderer callables. `dcoir_review.verified_finding_render` is now a pure helper for verifier-aware ordinary rendering rather than a production installer, and `dcoir_review.repair_pipeline` retains repair synthesis while exposing its stable repair renderer to the canonical owner.

The cutover is guarded mechanically: former renderer owners may not assign `build_inline_comment` or retain `original_build_inline_comment` storage, later production modules may not replace the canonical owner, repeated application is idempotent, and an exact seven-case output corpus locks verified ordinary, deterministic sentinel, repair, native-suggestion, unverified fallback, and YAML/security rendering byte-for-byte to the characterized pre-cutover behavior.

### Canonical per-file review composition

`dcoir_review.per_file_review` is the single production owner of `review_single_file_context`. The previous runtime shape first installed semantic-result reuse and then wrapped that callable again for stage-local routing and telemetry. The canonical owner now composes those responsibilities explicitly in the characterized order: stage-local routing projects the per-file configuration, semantic-result reuse decides reuse versus recomputation using that projected configuration, and the base Pareto per-file review executes only when recomputation is required.

`dcoir_review.semantic_result_reuse` retains reusable semantic state, exact-match eligibility, carry-forward, manifest, and hybrid-lifecycle responsibilities but no longer installs a per-file runtime override. `dcoir_review.per_file_routing` retains config projection, OpenRouter payload routing, Response Healing controls, and request telemetry but no longer installs or stores a prior per-file callable. Production composition removes semantic-result reuse from the runtime patch sequence and installs `dcoir_review.per_file_review` once as the stage-local owner, reducing both the patch application count and the per-file override graph rather than merely renaming historical layers.

### Canonical sanitization ownership

The base redaction implementation is the single production owner of `sanitize_text`. Historical v6 and v7 layers previously wrapped that callable to preserve environment/provenance source text and interpolated Authorization/Bearer examples, storing each prior callable as another runtime shim. The canonical base redaction responsibility now recognizes safe variable-backed header references directly, including Python formatted strings, PowerShell environment variables, and JavaScript template references, while retaining the existing fail-closed treatment of literal, fallback, command-substitution, and static credential values.

The v6 and v7 layers retain their unrelated prompt-review, metadata, ledger, selection, and debug responsibilities but no longer replace `sanitize_text` or store a prior sanitizer callable. Runtime ownership tests require the base sanitizer identity to remain unchanged across the complete production patch sequence and require zero `_dcoir_*sanitize_text` callable shims. This removes a two-stage override chain rather than relocating it, while the base redaction corpus owns the surviving safe-source and static-secret behavior.

### Canonical finding-validation ownership

The assembled base reviewer is the single production owner of `validation_text_for_finding`. Historical v8 and v9 layers previously wrapped that callable in sequence, with each layer storing the prior implementation. The base review layer now resolves supported finding kinds and renders the same semantic validation commands directly in the connector-safe `base/part_06a_finding_validation.py` segment, while ordinary findings still retain supplied validation commands plus path-appropriate defaults.

The v8 and v9 layers retain their unrelated selection, prompt-accounting, progress, and compatibility responsibilities but no longer replace `validation_text_for_finding` or store a prior validation renderer. Runtime ownership tests require the base callable identity to survive the complete production patch sequence, preserve representative explicit and inferred semantic validation output, preserve PowerShell quoting safety, and require zero `_dcoir_*validation_text_for_finding` callable shims.

### Canonical guidance-code classification ownership

The assembled base reviewer is the single production owner of `guidance_value_looks_like_code`. The generic runtime and strict runtime layers previously replaced that classifier in sequence, making the effective definition depend on patch order even though the final responsibility is a deterministic language-aware code-versus-prose decision. The canonical `base/part_06b_guidance_code.py` segment now owns that final behavior directly for Python, PowerShell, YAML/JSON, JavaScript/TypeScript, fenced values, and generic code-like syntax.

The historical runtime layers retain their private classifier helpers where those helpers are still used internally for normalization and repair-field validation, but they no longer mutate the base reviewer classifier. Runtime ownership tests pin the final behavior corpus and require the base callable identity to remain unchanged across the complete production patch sequence. This removes another two-stage production override chain without coupling base code back to historical patch modules.

### Canonical quality-retry decision ownership

`dcoir_review.quality_gate` is the single final production owner of `hardened.review_quality_retry_reason`. The hardened base layer retains `baseline_review_quality_retry_reason` as the explicit baseline predicate for sentinel coverage, structured-finding quality, confidence, and changed-line anchoring. The quality gate composes that baseline with semantic summary-only recovery and the existing bounded low-confidence disposition eligibility in one decision function.

The structured-result recovery layer no longer wraps `review_quality_retry_reason` or stores a prior callable. The two historical prior-function shims for quality-gate and structured-disposition retry logic are removed. Runtime ownership tests require exactly one production replacement, final ownership by `dcoir_review.quality_gate`, and no stored retry-history callables, while the quality-gate and structured-result recovery selftests preserve summary-only retry, near-threshold pending disposition, fail-closed malformed finding, feature-gate, and risk-sentinel behavior.
### Canonical adversarial per-file prompt policy ownership

`dcoir_review.adversarial_prompt_policy` is the current owner of the semantic falsification and predicate/call-site audit text shared by per-file detection and independent confirmation. The Pareto per-file prompt builder applies that final policy directly before any historical runtime patch executes. `dcoir_review_required_runtime_patch_v32` retains only compatibility aliases and its independent confirmation-stage behavior; it no longer wraps `build_per_file_review_prompt` or stores the previous callable.

`dcoir_review.semantic_evidence_hardening` no longer strengthens the prompt by mutating v32 module globals at runtime. Its surviving blank-anchor and verifier-lifecycle responsibilities remain independent. The v46 semantic-context layer may still wrap the canonical prompt builder once for cache/projection reuse, but the prompt semantics no longer depend on v32-to-semantic-evidence mutation order. Runtime ownership tests require the final combined policy before v32 application, exactly one later prompt replacement by v46 in an isolated production-sequence probe, and no v32 stored-original prompt shim. Characterization pins the fully patched prompt bytes across normal and constrained prompt budgets.
