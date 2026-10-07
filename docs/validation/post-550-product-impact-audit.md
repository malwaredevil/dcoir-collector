# Post-#550 product-impact audit

Issue #223 audits the repository after the #550 architecture migration for
dead code, duplicated owners, runtime overrides and competing implementations,
and ranks each finding by its effect on what the repository delivers:

- the Gemini agent bundle;
- the OpenAI GPT packages;
- the DCOIR collector;
- the validation evidence that governs all three.

The audit ran alongside PR #603. Fixes small enough to land safely there were
made in that PR. Everything else is recorded here as a follow-up, or as
retained with the reason.

## Scope and method

The inventory used a frozen snapshot of PR #603 at `8a73800`, split into six
areas:

| Area | Surfaces |
| --- | --- |
| Gemini entrypoints | `project_sources/gemini/tools/*.py` CLIs and runners |
| Gemini replay library | `project_sources/gemini/tools/lib/gemini_behavioral_replay_*` |
| Gemini bundle library | the other `project_sources/gemini/tools/lib` modules |
| Agent runtime | `project_sources/agent_runtime` tools, tests and manifests |
| Operator and workflow tooling | `.github/actions`, `.github/github_actions/tools`, `.github/ops/tools`, `.github/scripts` |
| Collector helpers | `project_sources/collector/tools`, harness tooling, manual-test framework |

Each area went through four steps:

1. One pass built the inventory and proposed findings.
2. A separate verifier reproduced each finding on scratch copies.
3. The verifier refuted or corrected anything it could not reproduce.
4. It assigned a classification, an impact and the affected deliverables.

Classifications:

- **Delete**: dead or orphaned, with no consumer.
- **Consolidate**: real duplication, or a competing owner.
- **Retain**: an intentional facade, or harmless repetition.

Impact is:

- **high** when a deliverable or gate can be wrong today;
- **medium** when a demonstrated defect or a gate gap is one edit away;
- **low** when the issue only costs maintenance.

The collector duplicate-function protection boundary was out of scope for
consolidation and stays intact; see below.

## Decision table

Status values:

- **Fixed**: the change landed in PR #603, at the commit named.
- **Partly fixed**: the demonstrated defect is fixed, and the remaining
  consolidation is a follow-up.
- **Follow-up**: confirmed, but too large, too risky or too
  workflow-dependent for PR #603.
- **Retain**: deliberate.

### Gemini entrypoints

| ID | Class | Impact | Finding | Status |
| --- | --- | --- | --- | --- |
| gemini-entrypoints-1 | Consolidate | high | Release build inspected and delivered a glob-selected zip (`3_0_5` sorts after `3_0_10`), not the zip the compiler produced | Fixed `706c1f6` |
| gemini-entrypoints-2 | Consolidate | medium | Release "output contract regressions" stage self-tests a private analyzer that diverges from the replay scorer | Follow-up |
| gemini-entrypoints-3 | Consolidate | low | Manifest, repo-root and attachment-naming helpers duplicated across producer and checkers | Partly fixed `7ca54cc`, `706c1f6`, `2fbdd7a`; scenario and output-contract validators still keep inline copies |
| gemini-entrypoints-4 | Consolidate | low | Two Gemini API clients with different model-alias rules | Follow-up |
| gemini-entrypoints-5 | Consolidate | medium | Replay gate not triggered by edits to its own driver; lane-separation cases ran through a subprocess script | Fixed `eabf43b` |
| gemini-entrypoints-6 | Delete | medium | Dead, unredacted `write_reports` beside the real report writer | Fixed `eabf43b` |
| gemini-entrypoints-7 | Delete | low | Compatibility forwarders for semantic-precision selftests | Fixed `eabf43b` |
| gemini-entrypoints-8 | Consolidate | low | OpenAI DCOIR replay runner hard-codes its model id; selftest asserts source text | Follow-up |
| gemini-entrypoints-9 | Consolidate | low | USB replay runner loads its scorer across trees with a file-load shim | Follow-up |
| gemini-entrypoints-10 | Consolidate | low | Fixture validator and score CLI re-implement lib fixture loading | Follow-up |
| gemini-entrypoints-11 | Consolidate | low | Two same-named reassembler selftests | Fixed `645d45d` |
| gemini-entrypoints-12 | Retain | low | Provider-specific runners and thin CLIs over shared lib owners | Retain |

### Gemini bundle library

| ID | Class | Impact | Finding | Status |
| --- | --- | --- | --- | --- |
| gemini-lib-other-1 | Consolidate | medium | Two Prime-chunk reassembly owners; the validator copy skipped sha256 checks, so a tampered chunk passed | Fixed `d78fbc3` |
| gemini-lib-other-2 | Consolidate | medium | Governance-leak guard matched only retired `_v1` ircore names and never scanned chunks | Fixed `d78fbc3` |
| gemini-lib-other-3 | Consolidate | medium | Production-like harness hard-coded construct counts the manifests own | Fixed `706c1f6` |
| gemini-lib-other-4 | Consolidate | low | Model-comparison lane re-implements the Gemini REST client | Follow-up (with gemini-entrypoints-4) |
| gemini-lib-other-5 | Consolidate | low | Warning-only `VISIBILITY_CHECKS` duplicates the scenario marker catalog | Follow-up |
| gemini-lib-other-6 | Consolidate | low | Three vocabularies judge internal-state leakage | Follow-up |
| gemini-lib-other-7 | Consolidate | low | Harness re-scanned the build zip with its own leak check | Fixed `706c1f6` |
| gemini-lib-other-8 | Consolidate | low | Manifest access helpers re-declared in seven tools | Partly fixed (see gemini-entrypoints-3) |
| gemini-lib-other-9 | Consolidate | low | Harness keeps a legacy scenario matrix that inflates reported coverage | Follow-up |
| gemini-lib-other-10 | Retain | low | Bundle-validation package: one orchestrator, four responsibility modules | Retain |
| gemini-lib-other-11 | Retain | low | Production-like harness modules are cohesive single-caller responsibilities | Retain |

### Gemini replay library

| ID | Class | Impact | Finding | Status |
| --- | --- | --- | --- | --- |
| gemini-lib-replay-1 | Consolidate | high | Two negation/assertion engines; required and forbidden scoring combine them differently | Follow-up; current composition documented below |
| gemini-lib-replay-2 | Consolidate | medium | "governed source" result computed and then replaced; false passes on rejected phrasings | Fixed `0543d22` |
| gemini-lib-replay-3 | Consolidate | low | Gemini and OpenAI live-replay HTTP code duplicated; retry policies diverged | Follow-up |
| gemini-lib-replay-4 | Delete | medium | Dead `write_reports`/`ensure_dir`/`write_json` | Fixed `eabf43b`, `7ee77b5` |
| gemini-lib-replay-5 | Delete | medium | Dead competing lane-separation check | Fixed `eabf43b` |
| gemini-lib-replay-6 | Consolidate | medium | Lane vocabularies diverged; six regex fragments copied verbatim | Partly fixed `0543d22`, `21a9ac3` (one shared vocabulary module, compiled patterns unchanged); merging the remaining vocabularies is a follow-up |
| gemini-lib-replay-7 | Consolidate | low | Compatibility-forwarder self-tests and nested self-test chains in the lib | Partly fixed `eabf43b` (forwarders deleted); nested chains are a follow-up |
| gemini-lib-replay-8 | Retain | low | The only 15,000-byte size gate is a hand-written list in a replay self-test | Retain; widen its coverage with the replay-1 work |
| gemini-lib-replay-9 | Consolidate | low | Alias hops hide owners | Partly fixed `eabf43b` (`_lane_target_head_index`); the `_occurrence_is_negated` alias waits for size headroom in `scoring.py` |
| gemini-lib-replay-10 | Consolidate | low | `OPTIONAL_TURN_LIST_KEYS` defined twice | Fixed `eabf43b` |
| gemini-lib-replay-11 | Retain | low | Replay core is deliberately shared with the OpenAI GPT lanes | Retain |
| gemini-lib-replay-12 | Retain | low | Test-only module patching that is always restored | Retain |

### Agent runtime

| ID | Class | Impact | Finding | Status |
| --- | --- | --- | --- | --- |
| agent-runtime-1 | Consolidate | medium | Two near-duplicate OpenAI package builders with drifted validation | Follow-up |
| agent-runtime-2 | Consolidate | medium | Three local repo-path resolvers diverge from the shared owner | Fixed `acabc63`, `645d45d`, `e6bf0dc` |
| agent-runtime-3 | Consolidate | medium | WebUI limits and target identity hard-coded in three places | Follow-up |
| agent-runtime-4 | Consolidate | low | Two source-commit resolvers with different precedence | Follow-up |
| agent-runtime-5 | Consolidate | low | Parity, USB scorer and live-replay selftests run only through the USB package selftest | Follow-up |
| agent-runtime-6 | Retain | low | USB semantics case libraries without an entrypoint | Retain |
| agent-runtime-7 | Consolidate | low | Misplaced second reassembler selftest | Fixed `645d45d` |
| agent-runtime-8 | Consolidate | low | Issue-numbered selftest extends the base one by executing it | Follow-up |
| agent-runtime-9 | Consolidate | low | USB scorer keeps a second copy of the incident-field vocabulary | Follow-up |
| agent-runtime-10 | Retain | low | USB scorer facade over four semantics modules | Retain |
| agent-runtime-11 | Retain | low | Knowledge-consolidation evaluator is an active decision tool | Retain |
| agent-runtime-12 | Retain | low | Small identical utility helpers | Retain |

### Operator and workflow tooling

| ID | Class | Impact | Finding | Status |
| --- | --- | --- | --- | --- |
| operator-workflow-tooling-1 | Consolidate | medium | Two PSScriptAnalyzer implementations share one report schema; CI runs the one that ignores the repo policy | Follow-up (same as collector-helpers-2) |
| operator-workflow-tooling-2 | Consolidate | medium | Delivery-zip identity chosen by three heuristics | Fixed `706c1f6`; the collector harness globs are safe because those directories are wiped first |
| operator-workflow-tooling-3 | Consolidate | medium | Second, divergent Gemini manifest validator in CI; an unlisted `Sub_Agent_*.txt` shipped when validation was skipped | Fixed `2fbdd7a` |
| operator-workflow-tooling-4 | Consolidate | medium | Apply-patch lane let `.github/actions` and `.github/ops/tools` targets through without workflow approval | Fixed `72462da` |
| operator-workflow-tooling-5 | Consolidate | medium | Static-analysis gate has two owners; the central gate read missing counts as 0 | Partly fixed `6900dfb` (central gate fails closed; READMEs name it); removing the unused `fail-on-*` inputs needs a workflow edit and is a follow-up |
| operator-workflow-tooling-6 | Consolidate | low | Collector source discovery and harness assembly copied across three actions | Follow-up |
| operator-workflow-tooling-7 | Consolidate | low | Required-surface profiles duplicate every path per profile | Follow-up |
| operator-workflow-tooling-8 | Consolidate | low | Three workflow audits re-check the same invariants | Follow-up |
| operator-workflow-tooling-9 | Delete | low | `generate_workflow_inventory.py` alias with no consumer | Fixed `aaeca80` |
| operator-workflow-tooling-10 | Delete | low | Two unused scaffold actions and a forwarding `setup-python-runtime` | Follow-up (workflow edit) |
| operator-workflow-tooling-11 | Consolidate | low | Review-assist action post-processes the canonical report | Follow-up |
| operator-workflow-tooling-12 | Consolidate | low | Duplicate-function report path guard exists three times | Follow-up |
| operator-workflow-tooling-13 | Retain | low | Profile-driven surface gate, shared surfacer, cohesive lib splits | Retain |

### Collector helpers

| ID | Class | Impact | Finding | Status |
| --- | --- | --- | --- | --- |
| collector-helpers-1 | Consolidate | medium | Three hand-written PowerShell lexers fed CI gates and hid code after `"a``"` and `` 'C:\temp`' `` | Fixed `febb6d9` |
| collector-helpers-2 | Consolidate | medium | Two PowerShell analyzer implementations write the same report | Follow-up |
| collector-helpers-3 | Delete | medium | Rule-risk facade monkey-patched helpers; "not hashed" tests were vacuous | Fixed `cc0b049`, `21a9ac3` |
| collector-helpers-4 | Consolidate | medium | Most collector tool test suites have no CI runner | Follow-up; new suites from this audit are wired in |
| collector-helpers-5 | Consolidate | low | Seven or more collector path-safety implementations | Follow-up |
| collector-helpers-6 | Consolidate | low | CI validators hard-code historical part filenames | Follow-up |
| collector-helpers-7 | Consolidate | medium | Orphaned DefaultNoFlags regression script; default collect path otherwise uncovered | Follow-up |
| collector-helpers-8 | Delete | low | Orphaned `verify_dcoir_bundle.py` checking a layout no builder produces | Fixed `9f4ebcf` |
| collector-helpers-9 | Consolidate | low | Reachability CLI forwarding wrapper; two `parse_sources` with different semantics | Follow-up |
| collector-helpers-10 | Consolidate | low | Surface-inventory YAML helpers split behind a forwarding facade | Follow-up |
| collector-helpers-11 | Consolidate | medium | Manual-test failure handler raised `NameError` (missing import hidden by star imports) | Partly fixed `23113f7` (the defect and a static name guard); splitting the checks by responsibility is a follow-up |
| collector-helpers-12 | Retain | low | Harness assembly, launcher and run-validation ownership are clean | Retain |

## Real risks fixed in PR #603

These findings had a reproduced effect on a deliverable or a gate. They are
fixed, each with a regression test that fails on the previous code.

- **Wrong Gemini zip delivered.** The release build and the surfacer took the
  lexicographically last zip in the output directory. Both now use the zip the
  compiler reports (`lib/gemini_bundle_zip_contract.py`).
- **Tampered Prime chunk passed validation.** The chunk plan now has one
  owner (`lib/gemini_prime_agent_chunks.py`), with per-chunk and reassembly
  sha256 checks shared by the reassembler and the validator.
- **Governance-leak guard blind to current names.** The guard now matches the
  unversioned ircore names and any `_vN` form. It also scans the Prime chunks
  and the knowledge sources.
- **Unlisted sub-agent shipped.** The CI manifest helper now runs the
  canonical validator rules (`2fbdd7a`).
- **Policy gates blind after some strings.** The runtime-package, event-text
  and reachability gates share one PowerShell lexer
  (`collector/tools/powershell_lexical_mask.py`).
- **Composite actions changeable without workflow approval.** The apply-patch
  lane now gates `.github/actions/` and `.github/ops/tools/` like workflows.
- **Static-analysis gate could pass on missing counts.** It now fails closed.
- **Replay false passes.** Rejected "governed source" phrasings no longer
  satisfy the required marker.
- **Vacuous security tests.** The rule-risk "unsafe path is not hashed"
  tests now go through the real hashing owner, and a positive control shows
  they can fail.
- **Manual-test crash on failure.** The failure handler can reach its
  cleanup function again.

## Explicit composition for gemini-lib-replay-1

A full consolidation of the two negation engines is an open-ended scorer
redesign. The verifier showed that routing required markers through the
polarity engine breaks a real positive control. Until that work lands, this
is the current composition, so a maintainer does not have to reconstruct it:

- **Required markers.** `gemini_behavioral_replay_scoring` decides these with
  engine A only: `text_scoring` `_occurrence_is_rejected_before`/`_after`
  plus `negation_context`, driven by `rejection_patterns`. Marker-specific
  augmentation runs in `marker_semantics.augment_semantic_marker_matches`,
  which honors post-marker rejection after `0543d22`.
- **Forbidden markers.** These go through engine A first
  (`_find_contextual_term_hits` with `skip_negated`, `skip_quoted` and
  `reject_unverified`). Engine B then runs:
  `semantic_assertions.analyze_semantics(...).occurrence_is_assertive`, built
  on `assertion_polarity`. Then `_marker_only_in_not_proven_bullets` and
  `_marker_only_in_bounded_rejection` run.
- **Shared frame check.** Engine A's `text_scoring` and `negation_context`
  call engine B's `prefix_has_affirming_negated_truth_frame` for
  affirming-negated frames. It is the only engine B function engine A uses.
- **Known gap.** "Do not make one controlled repair step" still satisfies the
  required marker "one controlled repair step", because `make` is not a
  rejected action verb.
- **Constraint.** `scoring.py` is 14,991 bytes, 9 bytes under the
  15,000-byte policy, so any routing change must first free space there.

Suggested follow-up slices:

1. A no-behavior-change shared predicate vocabulary, with a parity check on
   the compiled patterns.
2. A single `occurrence_is_asserted` owner, built corpus-first, with
   known-bad controls for the gap above and the existing "smallest recovery
   artifact" positive control.

## Collector duplicate-function protection

This protection is intact, and PR #603 does not change it:

- `validate_dcoir_runtime_ordering.validate_unique_function_definitions`;
- the `run-duplicate-function-check` action and its PowerShell script;
- `validate_duplicate_function_reports.py`;
- `test_duplicate_function_action_contract.py`.

The runtime-package gate still reports 171 unique functions and 0
duplicates. Two related surfaces changed:

- The central `Test-DcoirStaticAnalysisValidationGate.ps1` now fails closed
  when a duplicate-function count is missing.
- The action README was corrected to name that script as the merge-gate
  owner.

## Guards added

Each guard covers a recurrence the audit demonstrated:

- `collector/tools/test_powershell_lexical_mask.py`: quoting-rule table and
  gate regressions. Runs in `run-collector-runtime-package-validation`.
- `.github/github_actions/tools/test_check_gemini_manifest_surfaces.py`:
  helper/validator agreement. Runs in `verify-required-surfaces`.
- `.github/ops/tools/apply_patch_request_selftest.py`: governed-target and
  request-id cases. Not yet run by CI; see follow-ups.
- `manual_test_framework/test_dcoir_manual_runner_imports.py`: static
  name-resolution guard. Not in the operator bundle.
- `lib/gemini_bundle_validation_selftest.py` and
  `lib/gemini_bundle_zip_contract_selftest.py`: chunk integrity, leak guard
  and zip identity. These, the shared path-safety selftests and
  `test_surface_delivery_zip.py` run through `run-path-safety-selftests`.
- `lib/gemini_behavioral_replay_lane_separation_regressions.py`: 73 lane
  cases, run in-process by the replay suite.

## Follow-ups

The confirmed follow-ups are listed in the decision table. Group them into
issue-sized work:

1. **Replay scorer polarity** (gemini-lib-replay-1, -6, -7, -8, -9).
2. **OpenAI package builder consolidation** (agent-runtime-1, -3, -4, -9).
   It should land after PR #603, which owns the shared path-safety module
   they use.
3. **One PowerShell analyzer owner** (collector-helpers-2,
   operator-workflow-tooling-1).
4. **Run the collector tool test suites in CI** (collector-helpers-4,
   agent-runtime-5, and the apply-patch selftest). This needs workflow
   approval.
5. **Workflow-surface cleanup** (operator-workflow-tooling-5 inputs, -6, -7,
   -8, -10, -11, -12). This needs workflow approval.
6. **Gemini client and validator helper consolidation** (gemini-entrypoints-2,
   -3, -4, -8, -9, -10, gemini-lib-other-4, -5, -6, -8, -9).
7. **Collector helper consolidation** (collector-helpers-5, -6, -7, -9, -10,
   -11).

## Pre-existing issues observed

None of these is caused by PR #603:

- On Python 3.13, `test_run_powershell_analyzer` and
  `test_run_powershell_analyzer_baseline` fail on symlink fixtures. They fail
  the same way on `main`.
- The checked-in `powershell_function_reachability_report.json` records
  collector source hashes that predate later collector edits. It is a
  report-only artifact. Regenerating it gives the same function
  classifications.

## Validation commands

```bash
python3 project_sources/collector/tools/test_powershell_lexical_mask.py
python3 project_sources/collector/tools/validate_dcoir_collector_runtime_package.py --source-dir . --output-dir <out>
python3 project_sources/collector/tools/validate_event_text_query_bound_policy.py --source-dir . --output-dir <out>
python3 .github/github_actions/tools/test_check_gemini_manifest_surfaces.py
python3 .github/github_actions/tools/check_gemini_manifest_surfaces.py --source-root project_sources/gemini/bundle_source
python3 .github/ops/tools/apply_patch_request_selftest.py
python3 project_sources/validation/manual_test_framework/test_dcoir_manual_runner_imports.py
python3 project_sources/gemini/tools/build_dcoir_gemini_release.py --source-root project_sources/gemini/bundle_source --output-dir <out>
python3 project_sources/gemini/tools/run_gemini_behavioral_replay_validation_suite.py --output-dir <out>
python3 .github/github_actions/tools/check_workflow_consistency_drift.py
python3 .github/github_actions/tools/check_workflow_modularization_contracts.py
python3 .github/github_actions/tools/audit_reusable_contracts.py
python3 .github/github_actions/tools/build_workflow_inventory.py --check
```
