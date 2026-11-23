# Issue #608 Slice 4 Required-Surface Groups Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended when an approved internal worker exists) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (- [ ]) syntax for tracking. In this connector-only session, prefer inline execution with small, independently verified batches and no external agent invocation.

**Goal:** Consolidate the eight duplicate-heavy required-surface base lists into named groups without changing any checked path, its order, the supplement behavior, or the flat-file contract consumed by CI and PowerShell inventory.

**Architecture:** A strictly validated JSON groups manifest owns all base path declarations. A Python module expands it deterministically into the existing flat JSON shape, supports explicit --write and read-only --check, and is called by the existing shipped required-surface validator. The independent PowerShell inventory consumer remains a reader of the unchanged flat JSON contract.

**Tech Stack:** Standard-library Python, unittest, existing GitHub Actions workflow/audit tooling, existing collector inventory and Windows NTFS junction tests. No new third-party dependency.

**Spec:** docs/superpowers/specs/2026-11-23-issue608-slice4-required-surface-groups-design.md (concept approved and written specification approved by the operator on 2026-11-23).

**Starting point:** main fa9b3295279bb12bc6ceffefbb89a4df8973be5f; approved written-spec branch docs/issue608-slice4-profile-groups-20261123 at fb6886c56ef31e55b13732203e5a94089dad4331 before this plan commit.

## Global Constraints

- Preserve all eight *ordered* base arrays and their key order. Baseline lengths: 108, 108, 82, 79, 10, 6, 71 and 31; combined 495 entries over 133 distinct paths. validate_on_push equals validate_on_pr element-for-element.
- Preserve four supplement JSON files, their manifest and ordering, current first-occurrence dedup merging, and *each final ordered expanded list*.
- Current missing-supplement-manifest protection already fails closed. Keep it; do not reimplement or relax it. Preserve existing invalid-path, symlink containment and Windows junction rejection semantics.
- The grouped canonical file is the only editable owner of base profiles. Keep workflow_required_surface_profiles.json as a checked-in generated **flat mapping of path arrays** for PowerShell inventory and external readers. A stale/malformed flat file must fail CI validation, not silently self-repair.
- No modifications to .github/workflows, .github/actions, collector runtime, packages, gate thresholds, reviewer policy or unrelated Draft PR #654; keep parent Issue #608 OPEN. New Python source files must be below 15,000 UTF-8 bytes.
- Draft-first TDD, internal Prog implementation plus Adva hostile review, and exact-head validation apply. User controls all Copilot/external Codex requests, Ready transitions and merges. Paid OpenRouter/DCOIR Review is opted out.
- Anti-freeze execution: 1–3 bounded operations per batch; fresh GitHub branch/head, changed-file and CI readback; never blindly retry a write.
- This plan is the authorized **document**, not authorization for functional implementation or a PR merge. Ask separately before proceeding with execution.

## File map and signatures

- Create .github/github_actions/workflow_required_surface_profile_groups.json: canonical source with exactly schema_version, groups, profiles.
- Create .github/github_actions/tools/required_surface_profile_groups.py: strict JSON loader, grouped expansion, path/source containment, canonical flat output, freshness verifier, atomic writer and CLI.
- Create .github/github_actions/tools/test_required_surface_profile_groups.py: shipped-module tests and hostile fixtures.
- Modify .github/github_actions/workflow_required_surface_profiles.json: generated flat output only.
- Modify .github/github_actions/tools/check_required_surfaces.py and test_check_required_surfaces.py: keep current API, supplement merge and error priorities; add verification.
- Modify project_sources/collector/tools/test_required_surface_windows_junctions.py: keep real NTFS tests working with canonical fixture.
- Read and regression-test, but do not modify without a separately justified fix: project_sources/collector/tools/powershell_surface_inventory_profiles.py and project_sources/collector/tools/powershell_surface_inventory_test_cases/manifest_and_profiles.py.
- Never change .github/github_actions/workflow_required_surface_profile_supplements.json or its four supplement JSONs.

Public names to use consistently:

~~~python
GROUPS_PATH = Path(".github/github_actions/workflow_required_surface_profile_groups.json")
FLAT_PATH = Path(".github/github_actions/workflow_required_surface_profiles.json")
EXPECTED_PROFILES = (
    "validate_on_push", "validate_on_pr", "manual_full_validation",
    "scheduled_health_check", "manual_gemini_bundle_build",
    "manual_gemini_model_comparison",
    "manual_collector_runtime_package_build",
    "manual_openai_gpt_deployment_package_build",
)

def expand_canonical(data: object) -> dict[str, list[str]]: ...
def read_groups(repo_root: Path) -> dict[str, list[str]]: ...
def canonical_flat_text(profiles: dict[str, list[str]]) -> str: ...
def verify_flat(repo_root: Path, base_profiles: dict[str, list[str]] | None = None) -> None: ...
def write_flat(repo_root: Path) -> None: ...
def main() -> int: ...
~~~

Move the current validate_repo_relative_path(path: str, label: str) and ensure_repo_local_source(repo_root: Path, source: Path, label: str) implementation into the new module and re-export via import in the checker, avoiding any circular import. Maintain original error wording for existing negative tests.

---

## Task 1: Strict canonical schema, path rules and expansion

**Files:** Create .github/github_actions/tools/required_surface_profile_groups.py and test_required_surface_profile_groups.py.

**Interface:** expand_canonical is a pure function; read_groups reads the canonical JSON through a within-repo file check and returns an ordered mapping with exactly eight profiles.

- [ ] **Step 1: RED test for valid ordering and basic failures.** Use a temp fixture with eight names and one two-path group. Assert group expansion order, direct-path segment append order, unknown-group rejection and duplicate-path rejection.

~~~python
def minimal_groups():
    return {
        "schema_version": "dcoir_required_surface_profile_groups_v1",
        "groups": {"common": ["README.md", "nested/valid.txt"]},
        "profiles": {name: [{"group": "common"}] for name in EXPECTED_PROFILES},
    }

def test_order(self):
    sample = minimal_groups()
    sample["profiles"]["validate_on_pr"].append({"paths": ["extra.txt"]})
    self.assertEqual(
        groups.expand_canonical(sample)["validate_on_pr"],
        ["README.md", "nested/valid.txt", "extra.txt"],
    )
~~~

- [ ] **Step 2: Run python .github/github_actions/tools/test_required_surface_profile_groups.py -v.** Expected RED because shipped grouped expander does not yet exist. Capture exact failure; fix a broken test harness before treating it as a valid TDD failure.
- [ ] **Step 3: Implement strict schema and validation.** Require exactly schema_version, groups and profiles at top level; version dcoir_required_surface_profile_groups_v1; groups mapping of nonempty string names to nonempty lists of normalized relative strings; profiles mapping with exact eight expected names and insertion order; segments exclusively {"group": str} or {"paths": nonempty list[str]}. Reject computed data, nonliteral paths, extra keys, nested groups, unknown groups, missing profiles and repeated output paths. Preserve all path order.

~~~python
def reject_duplicate_keys(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"Duplicate JSON property: {key}")
        result[key] = value
    return result

def expand_canonical(data: object) -> dict[str, list[str]]:
    if not isinstance(data, dict) or set(data) != {"schema_version", "groups", "profiles"}:
        raise ValueError("Grouped required-surface source must have three exact keys")
    if data["schema_version"] != "dcoir_required_surface_profile_groups_v1":
        raise ValueError("Unsupported grouped required-surface schema version")
    if not isinstance(data["profiles"], dict) or tuple(data["profiles"]) != EXPECTED_PROFILES:
        raise ValueError("Grouped required-surface source must define eight profiles in order")
    # Iterate validated ordered segments. Expand each literal group in place.
    # Verify all groups even if unreferenced. Error on a repeated path in a profile.
    # Return an insertion-ordered mapping, without touching the filesystem.
~~~

- [ ] **Step 4: Hostile tests then GREEN.** Test missing/extra JSON keys, null types, wrong schema, empty group, empty segment, two segment keys, blank/absolute/drive/UNC/traversal/backslash/NUL path, duplicate key in JSON at any nesting, unknown group, cross-segment path collision; add correct safe controls. Parse with json.load(..., object_pairs_hook=reject_duplicate_keys); do not accept duplicate keys silently.
- [ ] **Step 5: Run focused tests and commit parser/test only.** Expected GREEN in a temporary valid fixture, no production code calls this yet. Commit: feat: add strict grouped required-surface expander. Keep file under 15 KB.

## Task 2: Deterministic flat artifact and fail-closed CLI

**Files:** Modify the new module and test file from Task 1.

**Interface:** canonical_flat_text serializes ordered arrays with two-space indentation and trailing newline; verify_flat is read-only and compares strict parsed arrays and exact serialized text; write_flat changes only the flat output atomically.

- [ ] **Step 1: Add RED tests for absent/stale flat file and valid canonical generation.** Build a temporary repository tree, write source at GROUPS_PATH, and call the *shipped* CLI via subprocess with --check --repo-root. Expect failure when output is absent; after --write, expect --check success and repeat --write to yield identical bytes.
- [ ] **Step 2: Add hostile tests.** Reject wrong flat key order, reordered path, changed path, extra/missing profile, duplicate JSON property, JSON syntax error, malicious source symlink, malicious output symlink, source/output directory, broken symlink and loop, no-partial-write failure, and unexpected command flags. Make sure a correct in-root file and benign repeat generation succeed.
- [ ] **Step 3: Implement canonical renderer and read-only verifier.** Use the parser from Task 1 for expected arrays. Validate and read flat as a strict JSON map of eight ordered path arrays. Compare semantic arrays, *then* exact UTF-8 text; a formatting-only manual edit is also stale. Fail on missing source or flat file without regenerating.

~~~python
def canonical_flat_text(profiles: dict[str, list[str]]) -> str:
    return json.dumps(profiles, indent=2, ensure_ascii=True) + "\n"

def verify_flat(repo_root: Path, base_profiles: dict[str, list[str]] | None = None) -> None:
    expected = read_groups(repo_root)
    # Reject outside-root paths, symlink escapes and non-files before reading.
    # Load flat with object_pairs_hook=reject_duplicate_keys.
    # Validate exact eight-profile shape and path normalization.
    # Compare ordered flat arrays, optional already-validated base_profiles,
    # and exact serialized UTF-8. Raise, never write, on mismatch.
~~~

- [ ] **Step 4: Implement atomic --write with explicit --check.** argparse modes are mutually exclusive and required. Resolve the canonical and target files inside the repo before operation. Write only a fully validated result to tempfile.NamedTemporaryFile in target directory; flush/fsync, os.replace, and clean up on exception. Never replace a symlink or directory, and never attempt to create output if canonical parsing failed.

~~~python
parser = argparse.ArgumentParser()
modes = parser.add_mutually_exclusive_group(required=True)
modes.add_argument("--check", action="store_true")
modes.add_argument("--write", action="store_true")
parser.add_argument("--repo-root", default=".")
args = parser.parse_args()
try:
    (verify_flat if args.check else write_flat)(Path(args.repo_root).resolve())
except (FileNotFoundError, OSError, RuntimeError, ValueError) as exc:
    print(exc, file=sys.stderr)
    return 1
return 0
~~~

- [ ] **Step 5: Run tests and commit.** Run python .github/github_actions/tools/test_required_surface_profile_groups.py -v. Demonstrate no mutation on --check and no partial output on errors. Commit: feat: write and verify deterministic flat surface artifact.

## Task 3: Canonical group migration with eight-profile and supplement parity

**Files:** Create .github/github_actions/workflow_required_surface_profile_groups.json; regenerate .github/github_actions/workflow_required_surface_profiles.json. Test via new test file.

**Interface:** Group source is the *single* owner of the original 495 ordered path occurrences; output maps the original eight keys directly to the original eight arrays.

- [ ] **Step 1: Snapshot baseline using the immutable GitHub main commit.** Retrieve the eight original arrays from git show fa9b3295279bb12bc6ceffefbb89a4df8973be5f:.github/github_actions/workflow_required_surface_profiles.json. Capture their before-supplement and final after-supplement lists in scratch test data. Do not commit generated report outputs or change main.
- [ ] **Step 2: Identify meaningful contiguous, repeated path runs and encode named groups.** At minimum share the identical 108-entry PR/push group. Then find long consecutive common runs between manual_full_validation, scheduled_health_check and manual_collector_runtime_package_build. Prefer responsibility names (collector harness/source, workflow tooling, shared validation) to single-path aliases. A group is a literal list only; profiles compose {"group": "..."} and {"paths": [...]}. Never reorder to manufacture a match.

~~~python
# Temporary migration audit, not a new production generator.
def repeated_runs(a, b, min_length=3):
    found = []
    for i in range(len(a)):
        for j in range(len(b)):
            n = 0
            while i+n < len(a) and j+n < len(b) and a[i+n] == b[j+n]:
                n += 1
            if n >= min_length:
                found.append((n, i, j, a[i:i+n]))
    return sorted(found, reverse=True)

def literal_ownership(source):
    return sum(len(v) for v in source["groups"].values()) + sum(
        len(segment.get("paths", []))
        for segments in source["profiles"].values()
        for segment in segments
    )
~~~

- [ ] **Step 3: Before writing flat output, compare each expanded grouped array to the untouched baseline.** Run exact equality, not set equality. Assert 108/108/82/79/10/6/71/31, 495 expanded entries, 133 distinct paths, and identical validate_on_pr/validate_on_push. The canonical source must have literal_ownership <= 371, a reduction of at least 25% from 495. If the threshold fails, identify a genuine shared contiguous responsibility group; do not remove required paths.
- [ ] **Step 4: Run the explicit generator and freshness check.** Run python .github/github_actions/tools/required_surface_profile_groups.py --write --repo-root . followed by --check. Check whether regenerated flat bytes match existing formatting; if formatting alone differs, review that separately rather than claiming path drift.
- [ ] **Step 5: Compare final supplement-merged lists and commit data.** Use the current shipped merge_profile_paths algorithm with the unchanged manifest and four JSON supplements. Require each final ordered list to match before and after. Fail and repair on any mismatch. Commit: refactor: make surface groups canonical with flat parity. Do not change .github/workflows or .github/actions.

## Task 4: Connect grouped freshness to the shipped checker, preserve security tests

**Files:** Modify .github/github_actions/tools/check_required_surfaces.py and test_check_required_surfaces.py.

**Interface:** Keep load_profiles(repo_root: Path) -> dict[str,list[str]] and its CLI outputs. The existing checker validates the flat list and supplement manifest *before* freshness so currently asserted malformed-path and missing-manifest error cases still test the intended control.

- [ ] **Step 1: Update temporary fixture builder.** Valid tests must include a minimal grouped file with *all eight known profile names* and one group containing base.txt. Change valid CLI test --profile to validate_on_pr; preserve the sample supplement behavior by including a supplement for validate_on_pr. Add a fixture function that writes paired valid flat and grouped data for any intended base-list mutation. A stale-file test intentionally changes flat only.

~~~python
def base_map(paths):
    return {name: list(paths) for name in EXPECTED_PROFILES}

def grouped_map(paths):
    return {
        "schema_version": "dcoir_required_surface_profile_groups_v1",
        "groups": {"fixture_base": list(paths)},
        "profiles": {name: [{"group": "fixture_base"}] for name in EXPECTED_PROFILES},
    }
~~~

- [ ] **Step 2: Write RED end-to-end checks.** Corrupt the flat file while keeping groups valid, then call the shipped checker and require exit 1 and a specific stale-artifact message. Change only canonical groups and expect the same. Keep a positive control and a missing-supplement-manifest negative control.
- [ ] **Step 3: Implement one integration point without changing supplement behavior.** The two path-safety functions can be re-exported by import from the new owner. First validate flat profiles with the existing validate_profile_map, then read/validate supplement manifest and additions, then verify_flat(repo_root, base_profiles=base), then merge_profile_paths(base, additions).

~~~python
from required_surface_profile_groups import (
    validate_repo_relative_path, ensure_repo_local_source, verify_flat,
)

def load_profiles(repo_root: Path) -> dict[str, list[str]]:
    profile_file = repo_root / PROFILE_PATH
    ensure_repo_local_source(repo_root, profile_file, "Required surface profile file")
    if not profile_file.is_file():
        raise FileNotFoundError(f"Required surface profile file missing: {PROFILE_PATH.as_posix()}")
    base = validate_profile_map(
        load_json_file(profile_file, PROFILE_PATH.as_posix()),
        PROFILE_PATH.as_posix(),
    )
    additions = load_profile_supplements(repo_root)
    verify_flat(repo_root, base_profiles=base)
    merge_profile_paths(base, additions)
    return base
~~~

- [ ] **Step 4: GREEN all existing tests and new hostile cases.** For each invalid source-path test, keep the flat and grouped fixtures consistent so the path guard is really reached. For existing base/supplement symlink cases, preserve the original targeted message and ensure no Traceback. For stale-only tests, modify only one of the two files.
- [ ] **Step 5: Commit guarded change.** Run python .github/github_actions/tools/test_check_required_surfaces.py -v and python .github/github_actions/tools/test_required_surface_profile_groups.py -v. Commit: fix: reject stale required-surface generated flat profiles.

## Task 5: Windows junction and independent PowerShell inventory parity

**Files:** Modify project_sources/collector/tools/test_required_surface_windows_junctions.py only as needed. Run project_sources/collector/tools/powershell_surface_inventory_test_cases/manifest_and_profiles.py without changing the existing flat-only inventory consumer.

- [ ] **Step 1: Supply consistent canonical fixture data for Windows tests.** Use the eight-profile grouped_map/base_map fixture shapes from Task 4. Update the checker CLI test profile to validate_on_pr. Keep an existing valid sample supplement file and manifest.
- [ ] **Step 2: Preserve real NTFS junction tests.** For a deliberate required-path mutation, update both grouped and flat source so the intended reparse-point guard runs. Confirm normal/inside-repository junction success, outside required-file junction failure, supplement JSON junction containment, parent-source junction escape, and supported file-symlink cases. Add a canonical-group-source junction escape rejection and an in-repo positive control.
- [ ] **Step 3: Confirm inventory remains a flat-file consumer.** Run python -m unittest discover -s project_sources/collector/tools -p 'test_*.py'. Specifically verify PowerShell inventory's read_required_profile_harness_paths yields unchanged harness paths and its regression tests still fail for a deliberately deleted/malformed flat profile. Do not make inventory depend on the grouped source.
- [ ] **Step 4: Adva hostile review.** Test duplicate JSON keys, duplicate expanded paths, stale generated output, traversal, Windows drive/UNC paths, symlink escapes, safe internal links, group cycles disallowed by no nested groups, missing manifest and no partial writes. Check error precedence, cross-file caller behavior and positive controls. Record findings and rerun tests after repairing each valid finding.
- [ ] **Step 5: Commit tested fixtures/evidence.** Commit: test: keep Windows and inventory required-surface behavior. Windows-specific NTFS success must be read from an actual exact-head Windows GitHub Actions run; a local Linux test that skips Windows does not count.

## Task 6: Final Draft verification, scope audit and PR handoff

**Files:** No new functional files. Use prior spec/plan plus implementation commits in one separately approved Draft PR.

- [ ] **Step 1: Compare exact branch to main and verify scope.** Run git diff --name-status main...HEAD; inspect every changed path. No workflow YAML, action metadata, package or collector runtime change. Check new Python source files with wc -c against the 15,000-byte policy. Check generated output with --check.
- [ ] **Step 2: Run focused local checks.**

~~~bash
python .github/github_actions/tools/required_surface_profile_groups.py --check --repo-root .
python .github/github_actions/tools/test_required_surface_profile_groups.py -v
python .github/github_actions/tools/test_check_required_surfaces.py -v
python -m unittest discover -s project_sources/collector/tools -p 'test_*.py'
python .github/github_actions/tools/build_workflow_inventory.py --check
python .github/github_actions/tools/check_workflow_consistency_drift.py
~~~

- [ ] **Step 3: Run all eight shipped positive controls without writing files.**

~~~bash
for name in validate_on_push validate_on_pr manual_full_validation scheduled_health_check manual_gemini_bundle_build manual_gemini_model_comparison manual_collector_runtime_package_build manual_openai_gpt_deployment_package_build; do
  python .github/github_actions/tools/check_required_surfaces.py --profile "$name" --repo-root . || exit 1
done
~~~

- [ ] **Step 4: Recheck unchanged supplement and array parity, hostile negative cases and full module ownership.** Verify 495 expanded entries and 133 unique paths. Verify exactly eight profile names, same order, 25%+ reduction in literal ownership, same full supplement-expanded path lists, and original PowerShell harness coverage. Stop on any gap.
- [ ] **Step 5: Make a Draft PR only after source/commit readback and required cheap checks.** Use the anti-freeze microtransaction: approve implementation, fresh baseline SHA, guarded feature branch creation and comparison, TDD test red/green, one source commit and readback, then Draft PR against main with Issue #608 Slice 4 scope, per-head CI IDs, reports and known Ready/Windows gaps.
- [ ] **Step 6: Maintain operator review gates.** User triggers or separately approves Copilot review while Draft. Do not invoke paid OpenRouter/DCOIR Review or external Codex unapproved. Fix Draft findings and record internal Prog/Adva passes. Separately seek Ready transition, full exact-head PR/Windows/PSScriptAnalyzer/Workflow Audit verification, merge and eventual parent closure permission. Record every governed status in ircore via upsert_github_work_item / record_github_work_item_readback followed by context readback.

## Rollback and handoff

If an ordered baseline array changes, a supplement mapping drifts, NTFS containment fails, or the inventory output differs, stop before Ready. Revert the grouped source and generated flat file *together* in the Draft branch to the last validated pair; never disable the check, weaken required paths, or repair by changing main. Preserve Issue #608 OPEN.

**Current approval state:** The user approved the written design specification on 2026-11-23. Preparing and committing this detailed plan is authorized. No implementation branch, feature source change, PR reviewer request, Draft-to-Ready transition, merge or issue closure is implied.

**Recommended execution choice:** Inline execution with 1–3-operation anti-freeze checkpoints and explicit operator authorization to start this plan; subagent-driven execution is an alternative only if separately authorized and available. Never assume a background job or delegated coding agent was approved.
