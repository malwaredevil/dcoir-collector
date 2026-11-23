# Issue #608 Slice 5: Read-Only Workflow Inventory Freshness Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (- [ ]) syntax for tracking.

**Goal:** Make the GitHub workflow-maintenance audit reject missing or stale *checked-out* workflow inventories before any regeneration, while preserving all existing workflow discovery, counts, audit findings and package outputs.

**Architecture:** The existing builder and renderer remain the only inventory generation/verification implementations. One reusable workflow removes its write-before-check step; existing --check and git-diff defenses remain. Extend the existing Python inventory test module with actual shipped-workflow wiring and CLI subprocess tests, then qualify the result with an exact-head Workflow Audit run.

**Tech Stack:** Python 3 standard library unittest/subprocess/re/pathlib, GitHub Actions YAML, GitHub REST/connector readback, repository workflow audit tools.

**Spec:** docs/superpowers/specs/2026-11-23-issue608-slice5-workflow-inventory-freshness-design.md, operator-approved written specification on commit 259894b51b1c04bba986898c803f194352a18ba0.

## Global Constraints

- **Approval gate:** The operator's latest Yes approved this written specification and creation of this implementation plan, NOT implementation. Before ANY workflow YAML or Python source/test edit, obtain fresh explicit authorization to execute this plan **including the one workflow YAML edit**. Draft PR, reviewer requests, Ready, merge and Issue #608 closure retain separate governance gates.
- **Base:** Protected main 64fb4cc989981bc1088167f54ec3f0f274f46d65, with Slice 4 PR #670 merged and post-merge Main Push Validation #45183721890, Workflow Audit #45183721881 and Documentation Quality #45183721820 SUCCESS. Re-read actual main at execution time, do not assume it remains fixed.
- **Scope:** Single executable workflow file .github/workflows/reusable-workflow-maintenance-audit.yml. One existing test module .github/github_actions/tools/test_workflow_inventory_freshness.py. The generated inventory JSON/Markdown may be changed **only if a reproducible feature-branch --check comparison proves necessary**; document and test their diffs.
- **Frozen:** .github/github_actions/tools/lib/workflow_files.py remains the canonical discovery owner; the drift audit remains 14,999 bytes and must not be edited or expanded; count registry, contract audit, action-version audit, CLI renderer, setup, triggers, permissions, report/artifact contracts, analyzer policy and package output remain unchanged.
- **Intent:** CI must execute build_workflow_inventory.py --check directly against checkout originals; never run the builder's default write mode inside the maintenance audit job.
- **Failure discipline:** Preserve nonzero exit on stale/missing JSON or Markdown; --check must never rewrite output files; retain the existing git diff --quiet guard as independent defense. Do not silently lower security gates.
- **Operator workflow:** Anti-freeze 1–3 operations/batch, explicit SHA/branch preconditions, post-mutation GitHub readback, TDD RED then GREEN before Draft, internal Prog/Adva hostile pass, no automatic external agent or paid OpenRouter/DCOIR Review requests. Copilot and External Codex are operator-controlled.
- **Handoff:** Parent Issue #608 must remain OPEN for Slices 6 and 7. Never modify unrelated Draft PRs, branch protection, or workflow trigger logic.

---

## Current file map and interfaces

- Modify the shipped **workflow integration**, .github/workflows/reusable-workflow-maintenance-audit.yml, solely to delete the named Regenerate workflow inventory step. The immediate Check workflow inventory freshness step must keep its existing build_workflow_inventory.py --check and git diff --quiet lines.
- Modify existing **regression owner**, .github/github_actions/tools/test_workflow_inventory_freshness.py. It already imports check_outputs(inventory: dict, json_output: Path, markdown_output: Path) -> list[str] and write_outputs(inventory: dict, json_output: Path, markdown_output: Path) -> None. Add workflow-wiring and CLI checks here; no second validation implementation.
- Read, do not edit, .github/github_actions/tools/build_workflow_inventory.py. Its main() accepts --check, --json-output and --markdown-output; build_inventory() creates the current repository model. Both output options are Paths.
- Read, do not edit, .github/github_actions/tools/lib/workflow_inventory_core.py and lib/workflow_inventory_outputs.py.
- Read, do not edit, .github/github_actions/tools/check_workflow_modularization_contracts.py. It already includes test_workflow_inventory_freshness in unittest.defaultTestLoader.loadTestsFromNames, so the added tests run in the existing CI audit.
- Conditional-only artifacts: .github/github_actions/workflow_inventory.json and .github/github_actions/workflow_inventory.md. Commit regenerated versions only if the intentional workflow change makes existing outputs genuinely stale; preserve expected counts and all unrelated records.
- Never add/change .github/workflows/workflow-maintenance-audit.yml, action versions, scripts performing package compilation, or any other CI workflow.

## Task 1: RED test for the shipped workflow inventory order

**Files:**
- Modify/test: .github/github_actions/tools/test_workflow_inventory_freshness.py
- Inspect only: .github/workflows/reusable-workflow-maintenance-audit.yml

**Interfaces:** Read the actual YAML as text. Do not create a competing YAML parser. The test targets exact shipped step names and executable builder command lines, using standard library re and pathlib.

- [ ] **Step 1: Refresh authority and isolate the implementation branch.** Get live Issue #608, AGENTS.md, latest main SHA, approved spec and plan, and ircore work-item state. Confirm current main is unchanged or rebase the docs branch deliberately after reading the diff. Create a new named feature branch from the exact approved docs-branch commit and compare against current main: it must show only the spec and plan additions before the first test edit. Record new head and compare. Do not create a PR yet.

Expected branch example: feat/issue608-slice5-inventory-freshness-20261123, based on the verified documentation branch tip. The first working-tree delta must be the test module only.

- [ ] **Step 2: Write the failing shipped-workflow integration test.** Append the following class to the existing module, **above** the if __name__ == "__main__" block, with imports added at top.

~~~python
import re

ROOT = Path(__file__).resolve().parents[3]
MAINTENANCE_WORKFLOW = ROOT / ".github/workflows/reusable-workflow-maintenance-audit.yml"
INVENTORY_COMMAND_RE = re.compile(
    r"(?m)^\s*python3\s+\.github/github_actions/tools/build_workflow_inventory\.py(?:\s+--check)?\s*$"
)


class ShippedWorkflowInventoryWiringTests(unittest.TestCase):
    def workflow_text(self) -> str:
        return MAINTENANCE_WORKFLOW.read_text(encoding="utf-8")

    def test_only_read_only_inventory_command_is_executable(self) -> None:
        workflow = self.workflow_text()
        commands = [match.group().strip() for match in INVENTORY_COMMAND_RE.finditer(workflow)]
        self.assertEqual(
            commands,
            ["python3 .github/github_actions/tools/build_workflow_inventory.py --check"],
        )
        self.assertNotIn("      - name: Regenerate workflow inventory", workflow)

    def test_freshness_after_drift_before_contracts(self) -> None:
        workflow = self.workflow_text()
        names = (
            "      - name: Check workflow consistency drift",
            "      - name: Check workflow inventory freshness",
            "      - name: Check workflow modularization contracts",
            "      - name: Check reusable and composite contract posture",
        )
        indices = [workflow.index(name) for name in names]
        self.assertEqual(indices, sorted(indices))
        self.assertIn("if ! git diff --quiet --", workflow)
        self.assertIn(".github/github_actions/workflow_inventory.json", workflow)
        self.assertIn(".github/github_actions/workflow_inventory.md", workflow)
~~~

The specific command regex anchors at the start of a YAML command line and avoids matching comments or echo prose. If the layout of existing YAML diverged, stop and adjust the test from current source before implementing; never weaken the intended exactly-one-command requirement.

- [ ] **Step 3: Verify RED on the unchanged workflow.** Run:

~~~bash
python .github/github_actions/tools/test_workflow_inventory_freshness.py -v
~~~

Expected: the original tests still pass, but test_only_read_only_inventory_command_is_executable fails because there are **two** executable inventory commands and one Regenerate step. The ordering and git-diff safety test should already pass. Save the exact test name and actual assertion failure, not just a summary.

- [ ] **Step 4: Commit the failing test with a current-blob SHA guard.** If using the GitHub connector, update only the existing Python test module with its fetched SHA; read back both the file blob and new branch head. Locally, the equivalent sequence is:

~~~bash
git add .github/github_actions/tools/test_workflow_inventory_freshness.py
git commit -m "test: reject write-before-check workflow inventory audits (#608)"
git show --name-status --format=fuller HEAD
~~~

This deliberate RED test commit occurs on the isolated feature branch only, not main. A failed publish or timeout requires remote readback before retry.

## Task 2: Remove write-before-check with the smallest YAML edit

**Files:**
- Modify: .github/workflows/reusable-workflow-maintenance-audit.yml
- Test: .github/github_actions/tools/test_workflow_inventory_freshness.py

**Interfaces:** Preserve existing YAML step interfaces. The builder command in the retained step remains exactly python3 .github/github_actions/tools/build_workflow_inventory.py --check; no new env vars or output types.

- [ ] **Step 1: Re-read the workflow's blob SHA on the feature branch.** Confirm the exact removable named step still matches:

~~~yaml
      - name: Regenerate workflow inventory
        shell: bash
        run: |
          set -euo pipefail
          python3 .github/github_actions/tools/build_workflow_inventory.py
~~~

- [ ] **Step 2: Apply one minimal, guarded edit.** Delete that five-line step and its following blank separator. Do **not** remove the subsequent Check workflow inventory freshness step, the --check command, or the git diff block. One unambiguous local edit option:

~~~python
from pathlib import Path

workflow = Path(".github/workflows/reusable-workflow-maintenance-audit.yml")
source = workflow.read_text(encoding="utf-8")
remove = (
    "      - name: Regenerate workflow inventory\n"
    "        shell: bash\n"
    "        run: |\n"
    "          set -euo pipefail\n"
    "          python3 .github/github_actions/tools/build_workflow_inventory.py\n"
    "\n"
)
assert source.count(remove) == 1, "Expected exact existing regeneration step once"
workflow.write_text(source.replace(remove, "", 1), encoding="utf-8")
~~~

GitHub connector alternative: fetch the current blob SHA, replace that exact span once, update_file with the SHA precondition, independently fetch the new blob and compare the changed-file list. No direct-main mutation.

- [ ] **Step 3: Verify GREEN and inspect the actual YAML.** Run:

~~~bash
python .github/github_actions/tools/test_workflow_inventory_freshness.py -v
python .github/github_actions/tools/build_workflow_inventory.py --check
git diff --check
git diff -- .github/workflows/reusable-workflow-maintenance-audit.yml
~~~

Expected: new workflow-wiring tests pass; the diff deletes only the regeneration step. The --check result may legitimately report stale generated inventory because the workflow source changed; if so, preserve the diagnostic and handle ONLY in Task 4. Do not regenerate before proving the test's read-only wiring.

- [ ] **Step 4: Commit and read back the exact workflow source.**

~~~bash
git add .github/workflows/reusable-workflow-maintenance-audit.yml
git commit -m "fix: check committed workflow inventory before regeneration (#608)"
git show --name-status --format=fuller HEAD
~~~

Verify the feature branch head and YAML content from GitHub, and verify no workflow triggers, permissions, setup or reporting changes occurred.

## Task 3: Actual CLI tests for missing, stale and safe output files

**Files:**
- Modify/test: .github/github_actions/tools/test_workflow_inventory_freshness.py
- Read only: .github/github_actions/tools/build_workflow_inventory.py
- Read only: .github/github_actions/tools/lib/workflow_inventory_core.py
- Read only: .github/github_actions/tools/lib/workflow_inventory_outputs.py

**Interfaces:** Invoke actual builder main() via subprocess, using supported --json-output and --markdown-output path arguments and --check. The existing write_outputs/build_inventory functions are used only to prepare explicit disposable fixtures.

- [ ] **Step 1: Add imports and test fixture setup.** Add subprocess and sys imports, and import build_inventory from lib.workflow_inventory_core. Append this class above the existing unittest.main guard:

~~~python
import subprocess
import sys
from lib.workflow_inventory_core import build_inventory

BUILDER = ROOT / ".github/github_actions/tools/build_workflow_inventory.py"


class ShippedInventoryCliTests(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        self.json_path = root / "workflow_inventory.json"
        self.markdown_path = root / "workflow_inventory.md"
        self.inventory = build_inventory()
        write_outputs(self.inventory, self.json_path, self.markdown_path)

    def run_check(self) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [
                sys.executable, str(BUILDER),
                "--json-output", str(self.json_path),
                "--markdown-output", str(self.markdown_path),
                "--check",
            ],
            cwd=ROOT, capture_output=True, text=True,
            check=False, timeout=90,
        )

    def test_valid_outputs_pass_without_rewrite(self) -> None:
        before = (self.json_path.read_bytes(), self.markdown_path.read_bytes())
        result = self.run_check()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(
            (self.json_path.read_bytes(), self.markdown_path.read_bytes()),
            before,
        )

    def test_missing_single_or_both_outputs_fail_without_repair(self) -> None:
        for missing in ("json", "markdown", "both"):
            with self.subTest(missing=missing):
                write_outputs(self.inventory, self.json_path, self.markdown_path)
                if missing in ("json", "both"):
                    self.json_path.unlink()
                if missing in ("markdown", "both"):
                    self.markdown_path.unlink()
                expected_json = self.json_path.read_bytes() if self.json_path.exists() else None
                expected_markdown = self.markdown_path.read_bytes() if self.markdown_path.exists() else None
                result = self.run_check()
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("is missing", result.stdout + result.stderr)
                self.assertEqual(
                    self.json_path.read_bytes() if self.json_path.exists() else None,
                    expected_json,
                )
                self.assertEqual(
                    self.markdown_path.read_bytes() if self.markdown_path.exists() else None,
                    expected_markdown,
                )

    def test_stale_single_outputs_fail_without_repair(self) -> None:
        for stale in ("json", "markdown"):
            with self.subTest(stale=stale):
                write_outputs(self.inventory, self.json_path, self.markdown_path)
                path = self.json_path if stale == "json" else self.markdown_path
                path.write_text("deliberately stale\n", encoding="utf-8")
                before = (self.json_path.read_bytes(), self.markdown_path.read_bytes())
                result = self.run_check()
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("is stale", result.stdout + result.stderr)
                self.assertEqual(
                    (self.json_path.read_bytes(), self.markdown_path.read_bytes()),
                    before,
                )
~~~

The fixture's explicit write_outputs call is **test setup only**; the shipped maintenance workflow must not regenerate. This class operates on disposable output paths, not the checked-in inventory files. The live inventory source remains the actual checkout for the command.

- [ ] **Step 2: Add the existing count-drift control, without mirroring the renderer.** Reuse the existing test_new_source_counts_make_old_outputs_stale pure check. Add a second actual-CLI safe control with explicit regeneration by invoking the builder *without* --check on the disposable two output paths, then verify --check passes and output bytes are stable:

~~~python
    def test_deliberate_maintenance_generation_then_check_succeeds(self) -> None:
        self.json_path.unlink()
        self.markdown_path.unlink()
        generation = subprocess.run(
            [
                sys.executable, str(BUILDER),
                "--json-output", str(self.json_path),
                "--markdown-output", str(self.markdown_path),
            ],
            cwd=ROOT, capture_output=True, text=True,
            check=False, timeout=90,
        )
        self.assertEqual(generation.returncode, 0, generation.stdout + generation.stderr)
        before = (self.json_path.read_bytes(), self.markdown_path.read_bytes())
        self.assertEqual(self.run_check().returncode, 0)
        self.assertEqual(
            (self.json_path.read_bytes(), self.markdown_path.read_bytes()),
            before,
        )
~~~

- [ ] **Step 3: Run the complete inventory tests and observe both polarities.**

~~~bash
python .github/github_actions/tools/test_workflow_inventory_freshness.py -v
python .github/github_actions/tools/check_workflow_modularization_contracts.py
~~~

Expected: shipped-check positive and negative tests pass; all original freshness tests still pass. If a new test fails unexpectedly, fix the test fixture or legitimate logic rather than bypass/rewrite the tested --check behavior. Only the Task 1 integration regression is required to be RED before the YAML fix; these direct-CLI tests characterize an existing fail-closed interface.

- [ ] **Step 4: Commit tests and verify the committed content.**

~~~bash
git add .github/github_actions/tools/test_workflow_inventory_freshness.py
git commit -m "test: exercise shipped inventory check against missing and stale outputs (#608)"
git show --name-status --format=fuller HEAD
~~~

Use guarded GitHub writes for remote-only execution and read back exact branch, file and commit. Keep the Python test module within the repository's 15,000-byte code policy.

## Task 4: Adversarial evidence, inventory parity and Draft PR qualification

**Files:**
- Inspect/test: .github/github_actions/tools/test_workflow_inventory_freshness.py
- Inspect/test: .github/workflows/reusable-workflow-maintenance-audit.yml
- Conditional modify: .github/github_actions/workflow_inventory.json and .github/github_actions/workflow_inventory.md
- No unrelated source files permitted

**Interfaces:** The two generated inventories must match build_workflow_inventory.py outputs byte-for-byte after the intentional source change. The reusable Workflow Audit job remains the deployment-side authority.

- [ ] **Step 1: Run final local/source checks in the feature checkout without pre-regenerating.**

~~~bash
python .github/github_actions/tools/test_workflow_inventory_freshness.py -v
python .github/github_actions/tools/build_workflow_inventory.py --check
python .github/github_actions/tools/check_workflow_modularization_contracts.py
python .github/github_actions/tools/audit_reusable_contracts.py
python .github/github_actions/tools/check_workflow_consistency_drift.py
python .github/github_actions/tools/check_workflow_action_versions.py
git diff --check
~~~

**Important conditional:** A nonzero --check because the one intentional workflow edit changed the derived inventory is expected evidence that the gate now detects real drift. Inspect its complete diagnostic **before** regenerating. If that happens, deliberately run the next command on the feature branch and inspect both output diffs, then rerun all checks:

~~~bash
python .github/github_actions/tools/build_workflow_inventory.py
git diff -- .github/github_actions/workflow_inventory.json .github/github_actions/workflow_inventory.md
git add .github/github_actions/workflow_inventory.json .github/github_actions/workflow_inventory.md
git commit -m "docs: refresh workflow inventory after audit ordering change (#608)"
python .github/github_actions/tools/build_workflow_inventory.py --check
~~~

Do not commit generated files if they are unchanged. Do not modify generator logic or the count registry merely to produce green output. Fail closed on unexpected drift.

- [ ] **Step 2: Internal Adva hostile and safe controls.** On disposable fixtures, seed these variants and require the observed outcome stated below:
  1. **Missing original JSON** with valid Markdown: actual --check rejects and never recreates JSON.
  2. **Missing original Markdown** with valid JSON: rejects and never recreates Markdown.
  3. **Both missing**: rejects both.
  4. **Corrupt JSON** and **stale Markdown**, individually and together: rejects and does not rewrite either output.
  5. **Changed source/count against old generated artifacts**: --check rejects by exact byte comparison; the intentional manual write then makes artifacts valid.
  6. **Opposite-polarity safe fixture**: fresh model plus matching outputs passes without any changed bytes.
  7. **Workflow repair attack:** check actual YAML has no earlier writer command; a text fixture with an inserted Regenerate step makes the RED wiring test fail. Verify comments and echo strings do not trick the exact-command test.
  8. **Cross-caller safety:** shared discovery and the declared workflow/action counts still pass their existing tests; drift findings have not been suppressed or substituted with a new parser.
  
Record Prog scope, Adva findings and repair disposition. Do not declare the internal hostile gate passed solely because the basic unit tests pass.

- [ ] **Step 3: Check all relevant changed-file boundaries.**

~~~bash
git diff --name-status main...HEAD
git diff --check main...HEAD
python .github/github_actions/tools/build_workflow_inventory.py --check
~~~

Only approved spec/plan files, the single reusable audit workflow, the existing inventory test module and objectively necessary generated inventories may differ. Preserve source tool code, trigger workflows, action files, package inputs and security enforcement. The drift checker must remain 14,999 bytes. Compare its blob to protected main.

- [ ] **Step 4: Create a Draft PR only after independent branch/source readback.** Use the verified isolated feature-branch head and base main. Confirm GitHub reports expected changes, compare ahead/behind, current workflow blob and test blob; create a Draft PR targeting main, reference Issue #608 Slice 5 and the design spec, report TDD RED/GREEN, new CLI tests, Adva variants, generated-inventory artifact disposition and any unverified platform checks. On ambiguous GitHub write result, read the remote PR state before any retry. Do not automatically request any reviewer.

- [ ] **Step 5: Read exact-head Draft CI, then stop at review/Ready gates.** Workflow Audit is triggered for the scoped workflow/tool changes. Read its actual run ID, event, exact head SHA, job conclusion, the Check workflow inventory freshness step, the modularization-contract regression tests and artifacts. Inspect any required cheap PR validations. On failure, keep Draft, repair with bounded tests and re-read GitHub; do not move Ready.

- [ ] **Step 6: Operator-controlled review and Ready transitions.** Present Draft PR, unresolved findings, exact latest head and checks. The operator controls Copilot and External Codex review requests. **No paid OpenRouter/DCOIR Review.** Separate operator approval required to mark Ready, run the higher-cost full Windows/security checks, merge, or close Issue #608. A clean Draft workflow audit does not constitute a Ready or merge approval.

## Final acceptance checklist

- [ ] Approved scoped workflow YAML change only; no other workflow or action mutations.
- [ ] RED shipped-workflow integration test on original write-first YAML; GREEN after deleting only that step.
- [ ] Original test fixtures plus shipped CLI negative and positive cases pass, read-only behavior verified.
- [ ] No default write-mode builder execution in the Workflow Audit; retained --check and git diff guard.
- [ ] Existing shared file discovery, count source and drift-checking behavior remain unchanged; drift checker under 15,000 bytes.
- [ ] Generated JSON and Markdown either unchanged or intentionally updated with a reviewed diff; --check passes.
- [ ] Adva hostile/safe variants and any valid-finding fixes documented.
- [ ] Draft PR opens only after GitHub source readback; current-head Workflow Audit and other applicable checks are read by ID and result.
- [ ] External review, Ready, merge and parent closure are individually operator-gated.
- [ ] GitHub and ircore receipts reflect exact branch/head/PR state and remaining gaps; cumulative turnover updated.
