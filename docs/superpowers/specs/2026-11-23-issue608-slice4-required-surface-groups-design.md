# Issue #608 Slice 4: Required-Surface Profile Groups with a Compatible Flat Artifact

**Date:** 2026-11-23
**Status:** Conceptual grouped-source design approved by the operator on 2026-11-23. This written specification is submitted for separate operator review. It is not implementation, Ready, reviewer-request, merge, or parent-issue closure authorization.
**Parent issue:** https://github.com/malwaredevil/dcoir-collector/issues/608
**Base commit:** fa9b3295279bb12bc6ceffefbb89a4df8973be5f (merged Slice 3 PR #656 and passing post-merge validation).
**Scope:** Issue #608 Slice 4 only; repository-owned required-surface profile data and tools.

## Problem and current evidence

The current ".github/github_actions/workflow_required_surface_profiles.json" contains eight ordered lists totaling 495 entries but only 133 distinct repository-relative paths. The "validate_on_push" and "validate_on_pr" base lists are exactly equal (108 entries each), and none of the eight base lists contains duplicates internally. Repeated path strings create multiple maintenance owners and drift risk.

The separate supplement manifest ".github/github_actions/workflow_required_surface_profile_supplements.json" currently enumerates four JSON supplements. ".github/github_actions/tools/check_required_surfaces.py" already **fails closed** when the supplement manifest is absent, malformed, or references a missing supplement. Existing tests verify this. Do not repeat that completed hardening or weaken it.

A second consumer, "project_sources/collector/tools/powershell_surface_inventory_profiles.py", reads the current flat profile JSON directly and expects a mapping from profile names to lists of paths. It also reads supplement data. Replacing the flat file with an incompatible nested/grouped object would break this consumer or require a separate parser migration. Preserve the existing flat read contract.

The parent issue's original figures and line references predate later merged slices. The above numbers were checked against the 2026-11-23 main baseline and are the source of truth for this specification.

## Goals and mandatory invariants

1. Have one maintainable canonical definition of shared base-profile paths using named groups, while retaining the current flat profile JSON as a generated, checked compatibility artifact.
2. Preserve the **exact ordered list** for each of all eight base profiles, not merely equal sets. The source migration must not insert, remove, rename, duplicate, or reorder any required path.
3. Preserve the four existing supplement files, manifest, merge precedence, and each final post-supplement expanded profile list. Supplement additions remain append-only in the existing merge order with first-occurrence deduplication.
4. Retain all existing path-safety, within-repository resolution, missing-file, and fail-closed validation. Any malformed group source, unknown group, invalid member, stale flat artifact, or unsafe path must stop the relevant required-surface checker with a nonzero exit status.
5. Keep the existing flat consumer compatible without updating its runtime data contract. CI must reject an out-of-sync generated flat file instead of silently consuming it.
6. Make no changes to ".github/workflows", ".github/actions", gate thresholds, required-surface policy, analyzer rules, collector runtime, agent packages, or parent issue state in this slice.
7. This slice addresses *profile consolidation only*. Other Issue #608 slices and the unrelated Draft PR #654 remain untouched.

## Approaches considered

**Chosen: grouped canonical source with a deterministic flat compatibility artifact.** This reduces duplicated editable path declarations, allows existing consumers to keep working, and makes drift detectable by the already-invoked checker. The cost is a new small generation/verification tool and a second checked-in file that is explicitly generated rather than independently edited.

**Alternative: teach every consumer the grouped format and remove the flat file.** This avoids a generated artifact but expands changes into the independent PowerShell inventory code and its tests. Reject for this slice because it increases regression risk and violates its narrow boundary.

**Alternative: retain independent flat lists and only add equality tests.** This catches some divergence but keeps duplicated ownership and conflicts with the parent issue's architectural goal. Reject.

## Source ownership and file contract

### Canonical data

Add ".github/github_actions/workflow_required_surface_profile_groups.json" as the **sole editable owner** for the eight base profiles. Use version "dcoir_required_surface_profile_groups_v1" with exactly these top-level keys: "schema_version", "groups", and "profiles".

- "groups" is an ordered mapping from meaningful, stable names to nonempty arrays of normalized repository-relative path strings. A group contains only literal paths, not other groups: **no nested references or cycles**.
- "profiles" is an ordered mapping of the same eight current profile names to an ordered array of segments. A segment is either {"group": "group_name"} or {"paths": ["repo/relative/path", ...]}; never both. Empty or unknown segments fail.
- A group's literal paths are expanded in their defined order at every reference. A direct "paths" segment expands in place. The resulting list preserves segment order. A path repeated within one resulting base profile fails validation, rather than silently deduplicating or changing ordering.
- Profile names, initial ordering, and path lists match the main-baseline flat file exactly. Group names should convey stable responsibilities (shared validation, collector harness/source, agent runtime, workflow tooling, etc.). Prefer substantive reusable groups over many one-path aliases. One reference group may supply the identical full base list used by "validate_on_push" and "validate_on_pr".
- No globs, environment substitutions, computed paths, filesystem-dependent discovery, implicit suffixes, case-folding, or script execution. This is a declarative list expansion only.

Illustrative structure (paths shown here are examples, not a replacement for the baseline):

~~~json
{
  "schema_version": "dcoir_required_surface_profile_groups_v1",
  "groups": {
    "validation_shared": ["README.md", ".gitattributes"]
  },
  "profiles": {
    "validate_on_push": [{"group": "validation_shared"}],
    "validate_on_pr": [{"group": "validation_shared"}]
  }
}
~~~

The actual canonical file must supply all eight complete profiles with the original 495 ordered path appearances; the example above is deliberately partial and must never be installed as source data.

### Generated compatibility file

Retain ".github/github_actions/workflow_required_surface_profiles.json" as a checked-in **generated artifact**, with the same public shape used today: an ordered JSON object whose eight keys map to arrays of normalized path strings. No schema keys or group references may appear in this flat file. During initial migration, compare the generated expansion against the untouched current flat file before replacing or committing it, profile by profile and element by element. Preserve the original key order and, where achievable, existing two-space JSON formatting and final newline.

Generate only from the canonical grouped source. Human edits belong in the grouped source; direct flat edits are treated as stale generated output. Never auto-regenerate silently as part of a validation read.

### Tool and validation boundary

Add a narrowly scoped Python tool ".github/github_actions/tools/required_surface_profile_groups.py" that owns strict JSON/schema parsing, safe ordered expansion, canonical output formatting, and generation/check operations. Keep it below the repository's 15,000-byte source-file limit; split only by genuine responsibility if necessary.

- Explicit "--write" updates the generated flat file; "--check" compares it to current canonical expansion without modifying anything. Use a common pure expansion function in both modes; reject unknown flags or ambiguous combinations.
- Reject missing/grouped JSON with malformed schema, duplicate JSON keys (including nested group/profile objects), non-string group names or path entries, empty required arrays, unknown or repeated group references within a profile when they duplicate a path, invalid literal path syntax, and unknown or missing expected profiles. The parser must not accept a valid-looking prefix while ignoring additional undeclared fields.
- Validate each path with the existing normalized repository-relative path rules, and resolve the source and output within the repository before reading/writing, rejecting outside-repository symlinks and unexpected path types.
- Emit actionable error messages identifying the profile/group and failing path or reference. Never silently return empty profiles or an empty supplement mapping on an invalid canonical source.
- On "--check", compare **both** strict parsed arrays (including ordering) and canonical serialized output. A logically equivalent but hand-edited flat file should be treated as stale until regenerated, so regeneration is deterministic and reviewable. Compare with the old baseline *semantically* first; byte-for-byte old-file identity is desirable, not a prerequisite if harmless whitespace differs.
- Implement writes atomically to a temporary file in the same directory followed by replace only after the entire source validates. Do not mutate generated data if any check fails. Preserve repository-relative safety on Windows as well as Linux.

Update the existing ".github/github_actions/tools/check_required_surfaces.py" to call the shared pure verification before it accepts profiles. **Do not change workflow YAML**: existing CI entry points already invoke this checker. Keep its published function behavior and CLI error convention compatible. Validate the flat profile shape and path safety before or alongside grouped-source freshness so existing hostile input tests still prove the intended protection rather than merely producing an unrelated stale-file error.

Leave "project_sources/collector/tools/powershell_surface_inventory_profiles.py" as a consumer of the unchanged flat file format. Its existing inventory output and control semantics remain unchanged; this is the key compatibility rationale for generating flat JSON.

The supplement manifest, four supplement JSON files, their ordering, and the existing "merge_profile_paths" behavior in the checker remain untouched. A missing supplement manifest must continue to fail closed, independently of grouped-source validity.

## Error handling and adversarial behavior

- Missing canonical group source, wrong schema_version, unknown group, malformed segment, duplicate paths, bad path, duplicate JSON property, and generated-output mismatch are all hard errors with no fallback to a stale flat file.
- Path traversal, absolute and drive-qualified paths, backslashes, empty segments, leading/trailing whitespace, NUL characters, and symlinks resolving outside the repository remain forbidden.
- Unknown profile or omitted expected profile is a hard error; preserve the eight names and ordering at migration. A later deliberate profile addition is a separately reviewed expansion of this contract.
- Valid groups and valid generated flat data must behave identically on clean input. Positive controls are necessary alongside the hostile cases so security checks do not reject legitimate existing paths.
- For an intermediate worktree with an intentionally missing canonical file, the generator/checker must fail rather than unconditionally trust the checked-in flat JSON. Existing test fixtures will need corresponding minimal canonical group data when they intentionally construct a valid repository.

## Verification and acceptance criteria

**Migration parity (hard gate before functional changes):**
- Save a main-baseline snapshot of the eight base arrays and their order. Generated arrays must be element-for-element identical to it: counts 108, 108, 82, 79, 10, 6, 71, 31 (495 total entries, 133 distinct paths), with no per-profile duplicates. All eight original profile names remain in the same order.
- The post-supplement result of "load_profiles" must match the pre-migration implementation for every profile, not just base path sets.
- "validate_on_pr" and "validate_on_push" must still have identical ordered base arrays. The independent PowerShell inventory must find the same profile-required harness paths and produce the same success/failure result and relevant report fields.
- The canonical source must materially reduce repeated literal path ownership; the spec targets at least a **25% reduction** from the 495 pre-change base-list path occurrences while keeping groups understandable. Do not achieve this by creating a large number of single-path groups solely for a metric.

**Tests, including shipped-code hostile cases:**
- Add focused generation/check tests for byte-stable repeat generation, stale output, malformed grouped JSON, unknown/missing groups, wrong segment keys, bad path formats, duplicate output, invalid schema, missing/duplicate profile, duplicate JSON keys, outside-repo symlinks, and no partial writes.
- Update ".github/github_actions/tools/test_check_required_surfaces.py" fixtures to include minimal valid canonical group definitions. Retain existing fail-closed assertions for missing supplement manifest and missing/unsafe supplement paths. Preserve targeted error assertions by adjusting fixtures where the grouped/flat parity check would otherwise mask a deliberately tested path error.
- Recheck "project_sources/collector/tools/test_required_surface_windows_junctions.py" fixtures and PowerShell surface-inventory regression tests for assumptions about the former flat-only checkout. Do not replace shipped PowerShell/inventory checks with a Python behavioral mirror.
- Run a positive control using the existing CI checker for each of the eight profiles. Run relevant Workflow Audit, inventory freshness and regression suites, plus the repository's routine Draft cheap validations; do not infer full Ready checks from Draft-skipped jobs.
- Ensure new Python files comply with the repository's 15 KB rule, existing Python compatibility, and no new dependency installation.

**Adversarial review:** Perform an internal Prog implementation pass and Adva hostile pass covering cross-file dependencies, malformed input, and safe controls. Fix and re-review valid findings on the Draft branch. A Copilot review or other external agent is never auto-requested; every request remains operator-controlled. Paid OpenRouter/DCOIR Review remains opted out.

## Execution, review and rollback

1. This document is the **written-spec review checkpoint**, not code implementation. User approval of the conceptual design authorizes drafting and committing this specification on an isolated branch. Written-spec approval remains separate before writing the step-by-step implementation plan and implementing the generator.
2. After written-spec approval, write the implementation plan and implement one guarded, small, independently verifiable batch at a time on a feature branch, using the repo's anti-freeze protocol. The first functional change should be a failing test against the intended new source contract, followed by the minimum parser/generator implementation (TDD), parity verification, and consumer integration.
3. Keep any implementation PR **Draft** during coding, hostile review and user-triggered/approved Copilot review/fix cycles. Do not request a review, use paid review, invoke external agents, transition Ready, merge, or close Issue #608 without the corresponding separate authorization.
4. Ready validation must include all required exact-head checks, Windows PowerShell tests, PSScriptAnalyzer/static analysis, and applicable workflow inventory and documentation checks. Do not change branch protection or CI triggers as a cost shortcut.
5. If exact array parity, supplemental merge parity, inventory compatibility, or security tests fail, stop; restore the last-known-good flat file and grouped source on the feature branch rather than weakening the checker or altering production workflows.

## Out of scope

Issue #608 Slice 5 workflow-file discovery, Slices 6-7 review-assist/path-guard changes, unrelated Draft PR #654, OpenAI/Gemini package modifications, new collector behaviors, changing thresholds or required paths, and closing parent Issue #608.

## Operator written-spec review gate

The operator approved the conceptual design on 2026-11-23. Review this written specification before authorizing the implementation plan or source edits. The next step after that separate written-spec approval is to invoke the writing-plans skill; do not treat this document's creation as evidence that implementation, reviewer requests, Ready transition, merge, or parent-issue closure are authorized.
