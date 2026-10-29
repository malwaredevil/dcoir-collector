#!/usr/bin/env python3
"""Issue #557: static Draft/Ready PR gate and event-matrix regression tests.

The validator inspects actual GitHub workflow YAML text. The matrix models
event/state expectations but does not claim to execute GitHub Actions.
"""
from __future__ import annotations

import re
import tempfile
import unittest
from pathlib import Path

from run_pr_draft_fail_fast import check_python_syntax

ROOT = Path(__file__).resolve().parents[3]
ENTRY = ROOT / ".github/workflows/validate-on-pr.yml"
REUSABLE = ROOT / ".github/workflows/reusable-validate-on-pr.yml"
UNFILTERED_CANCEL = ROOT / ".github/workflows/cancel-pr-validation-on-draft.yml"
EVENTS = {
    "opened",
    "reopened",
    "synchronize",
    "ready_for_review",
}
CANCEL_EVENTS = {"converted_to_draft"}


def contract_errors(entry: str, reusable: str, unfiltered_cancel: str) -> list[str]:
    errors: list[str] = []
    match = re.search(
        r"(?m)^  pull_request:\n    types:\n(?P<events>(?:      - [a-z_]+\n)+)",
        entry,
    )
    found = (
        set(re.findall(r"(?m)^      - ([a-z_]+)$", match["events"].rstrip("\n")))
        if match
        else set()
    )
    if found != EVENTS:
        errors.append(f"PR event set differs: {sorted(found)}")
    if not re.search(r"(?m)^    paths:\s*$", entry):
        errors.append("path-filtered validation trigger missing")
    if not re.search(r"(?m)^  workflow_dispatch:\s*$", entry):
        errors.append("manual baseline workflow_dispatch removed")
    entry_group = re.search(
        r"(?m)^  group: (?P<group>validate-on-pr-.*)$",
        entry,
    )
    if not entry_group:
        errors.append("per-PR concurrency group missing")
    if not re.search(r"(?m)^  cancel-in-progress: true\s*$", entry):
        errors.append("stale-head cancellation missing")
    if "  validate:\n    uses: ./.github/workflows/reusable-validate-on-pr.yml" not in entry:
        errors.append("original entry validate job or reusable call missing")
    if "caller_event_name: ${{ github.event_name }}" not in entry:
        errors.append("entry no longer forwards caller event")
    if "pull_request_target:" in entry or "issue_comment:" in entry:
        errors.append("unapproved privileged/reviewer trigger")
    cancel_match = re.search(
        r"(?m)^  pull_request:\n    types:\n(?P<events>(?:      - [a-z_]+\n)+)",
        unfiltered_cancel,
    )
    cancel_found = (
        set(re.findall(r"(?m)^      - ([a-z_]+)$", cancel_match["events"].rstrip("\n")))
        if cancel_match
        else set()
    )
    if cancel_found != CANCEL_EVENTS:
        errors.append(f"unfiltered cancellation event set differs: {sorted(cancel_found)}")
    if re.search(r"(?m)^    paths:\s*$", unfiltered_cancel):
        errors.append("Draft conversion cancellation must not have a path filter")
    cancel_group = re.search(
        r"(?m)^  group: (?P<group>validate-on-pr-.*)$",
        unfiltered_cancel,
    )
    if not cancel_group:
        errors.append("unfiltered cancellation concurrency group missing")
    elif entry_group and cancel_group["group"] != entry_group["group"]:
        errors.append("unfiltered cancellation must use the validation concurrency group")
    if not re.search(r"(?m)^  cancel-in-progress: true\s*$", unfiltered_cancel):
        errors.append("unfiltered cancellation must supersede in-flight validation")
    if not re.search(r"(?m)^  contents: none\s*$", unfiltered_cancel):
        errors.append("unfiltered cancellation workflow must not receive repository access")
    if re.search(r"(?m)^      contents: (?:read|write)\s*$", unfiltered_cancel):
        errors.append("unfiltered cancellation job must not receive repository access")
    if "actions/checkout" in unfiltered_cancel:
        errors.append("unfiltered cancellation workflow must not check out repository code")
    sections = re.search(
        r"(?ms)^jobs:\n  draft_fail_fast:\n(?P<fast>.*?)^  validate:\n(?P<heavy>.*)$",
        reusable,
    )
    if not sections:
        errors.append("Draft gate and original validate job must coexist in that order")
        return errors
    fast, heavy = sections["fast"], sections["heavy"]
    if "runs-on: ubuntu-24.04" not in fast:
        errors.append("Draft gate should be on inexpensive Linux runner")
    if not re.search(r"(?m)^      contents: read\s*$", fast):
        errors.append("Draft gate read-only permission missing")
    if "Run cheap Draft validation" not in fast:
        errors.append("Draft fast check missing")
    if "run_pr_draft_fail_fast.py" not in fast:
        errors.append("Draft gate runner missing")
    if (
        "        uses: actions/checkout@v7\n"
        "        with:\n"
        "          persist-credentials: false\n"
        not in fast
    ):
        errors.append("Draft checkout must not persist credentials")
    if re.search(r"(?m)^    if:", fast):
        errors.append("Draft gate must not be skipped in Draft")
    if not re.search(r"(?m)^    needs: draft_fail_fast\s*$", heavy):
        errors.append("Ready heavyweight check no longer depends on Draft gate")
    if not re.search(
        r"(?m)^    if: .*(!cancelled\(\)).*(caller_event_name == 'workflow_dispatch' \|\| github\.event\.pull_request\.draft == false)",
        heavy,
    ):
        errors.append("Ready guard must handle failed prerequisite and Draft state")
    if "!cancelled() && needs.draft_fail_fast.result != 'success'" not in heavy:
        errors.append("Ready job is no longer fail-closed on fast gate")
    fail_closed = heavy.find("throw 'Draft fail-fast gate failed")
    checkout = heavy.find("- name: Checkout repository")
    if fail_closed < 0 or checkout < 0 or fail_closed >= checkout:
        errors.append("Ready must fail before checkout after a failed fast gate")
    return errors


class LifecyclePolicyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.entry = ENTRY.read_text(encoding="utf-8")
        cls.reusable = REUSABLE.read_text(encoding="utf-8")
        cls.unfiltered_cancel = UNFILTERED_CANCEL.read_text(encoding="utf-8")

    def test_current_files_meet_contract(self) -> None:
        self.assertEqual(
            [],
            contract_errors(self.entry, self.reusable, self.unfiltered_cancel),
        )

    def test_draft_ready_and_conversion_matrix(self) -> None:
        for event in sorted(EVENTS | CANCEL_EVENTS):
            for draft in (True, False):
                # GitHub's event and draft status are both checked; a conversion
                # to Draft always reports draft=true in a real webhook.
                if event == "ready_for_review" and draft:
                    continue
                if event == "converted_to_draft" and not draft:
                    continue
                with self.subTest(event=event, draft=draft):
                    fast = event in EVENTS
                    heavy = fast and not draft
                    if event == "converted_to_draft":
                        self.assertIn(event, CANCEL_EVENTS)
                        self.assertNotIn(event, EVENTS)
                        self.assertFalse(re.search(r"(?m)^    paths:\s*$", self.unfiltered_cancel))
                        self.assertTrue(re.search(
                            r"(?m)^  cancel-in-progress: true\s*$",
                            self.unfiltered_cancel,
                        ))
                        self.assertFalse(fast)
                        self.assertFalse(heavy)
                        continue
                    self.assertTrue(fast)
                    self.assertEqual(not draft, heavy)
                    if event == "ready_for_review":
                        self.assertTrue(heavy)

    def test_changed_ready_head_reruns_heavy_gate(self) -> None:
        for event in ("opened", "reopened", "synchronize", "ready_for_review"):
            with self.subTest(event=event):
                self.assertIn(event, EVENTS)
                self.assertIn("github.event.pull_request.draft == false", self.reusable)

    def test_malformed_python_fails_fast(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / "bad.py").write_text("def broken(:\n", encoding="utf-8")
            with self.assertRaises(SyntaxError):
                check_python_syntax(root, [Path("bad.py")])

    def test_python_syntax_check_never_runs_untrusted_code(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / "code.py").write_text(
                "from pathlib import Path\nPath('should-not-exist').write_text('oops')\n",
                encoding="utf-8",
            )
            check_python_syntax(root, [Path("code.py")])
            self.assertFalse((root / "should-not-exist").exists())

    def test_missing_tracked_python_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaises(FileNotFoundError):
                check_python_syntax(Path(folder), [Path("missing.py")])

    def test_python_syntax_check_rejects_outside_and_symlink_paths(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            base = Path(folder)
            root = base / "checkout"
            root.mkdir()
            outside = base / "outside.py"
            outside.write_text("pass\n", encoding="utf-8")
            with self.assertRaises(ValueError):
                check_python_syntax(root, [Path("../outside.py")])
            with self.assertRaises(ValueError):
                check_python_syntax(root, [outside])
            with self.assertRaises(ValueError):
                check_python_syntax(root, [Path(".")])
            link = root / "linked.py"
            try:
                link.symlink_to(outside)
            except (NotImplementedError, OSError) as exc:
                self.skipTest(f"symlink creation unavailable: {exc}")
            with self.assertRaises(ValueError):
                check_python_syntax(root, [Path("linked.py")])

    def test_missing_or_downgraded_guards_rejected(self) -> None:
        variants = (
            (self.entry.replace("      - ready_for_review\n", ""), self.reusable),
            (self.entry.replace("cancel-in-progress: true", "cancel-in-progress: false"), self.reusable),
            (self.entry.replace("caller_event_name: ${{ github.event_name }}", "caller_event_name: push"), self.reusable),
            (self.entry.replace("  workflow_dispatch:\n", ""), self.reusable),
            (self.entry, self.reusable.replace("    needs: draft_fail_fast\n", "")),
            (self.entry, self.reusable.replace("!cancelled()", "success()")),
            (self.entry, self.reusable.replace("github.event.pull_request.draft == false", "true")),
            (self.entry, self.reusable.replace("!cancelled() && needs.draft_fail_fast.result != 'success'", "false")),
            (self.entry, self.reusable.replace("!cancelled() && needs.draft_fail_fast.result", "needs.draft_fail_fast.result")),
            (self.entry, self.reusable.replace("throw 'Draft fail-fast gate failed", "Write-Host 'Draft fail-fast gate failed")),
            (self.entry, self.reusable.replace("  draft_fail_fast:\n", "  removed_fast_gate:\n")),
            (self.entry.replace("  pull_request:\n", "  pull_request_target:\n"), self.reusable),
            (self.entry.replace("  workflow_dispatch:\n", "  issue_comment:\n"), self.reusable),
            (self.entry.replace("  validate:\n    uses:", "  full_validate:\n    uses:"), self.reusable),
            (self.entry, self.reusable.replace("  draft_fail_fast:\n", "  draft_fail_fast:\n    if: ${{ github.event.pull_request.draft == false }}\n")),
            (self.entry, self.reusable.replace("  draft_fail_fast:\n    name: draft_fail_fast\n    runs-on: ubuntu-24.04\n    permissions:\n      contents: read", "  draft_fail_fast:\n    name: draft_fail_fast\n    runs-on: ubuntu-24.04\n    permissions:\n      contents: write")),
            (self.entry, self.reusable.replace("          persist-credentials: false\n", "")),
            (self.entry, self.reusable.replace("          persist-credentials: false", "          persist-credentials: true")),
        )
        for index, (entry, reusable) in enumerate(variants):
            with self.subTest(mutation=index):
                self.assertTrue(
                    contract_errors(entry, reusable, self.unfiltered_cancel),
                    f"unsafe workflow mutation {index} passed validation",
                )
        cancel_variants = (
            self.unfiltered_cancel.replace("      - converted_to_draft\n", ""),
            self.unfiltered_cancel.replace("cancel-in-progress: true", "cancel-in-progress: false"),
            self.unfiltered_cancel.replace("  contents: none", "  contents: read"),
            self.unfiltered_cancel.replace(
                "      - converted_to_draft\n",
                "      - converted_to_draft\n    paths:\n      - 'project_sources/**'\n",
            ),
            self.unfiltered_cancel.replace(
                "validate-on-pr-${{ github.event.pull_request.number || github.run_id }}",
                "validate-on-pr-${{ github.run_id }}",
            ),
        )
        for index, unfiltered_cancel in enumerate(cancel_variants):
            with self.subTest(cancel_mutation=index):
                self.assertTrue(
                    contract_errors(self.entry, self.reusable, unfiltered_cancel),
                    f"unsafe cancellation mutation {index} passed validation",
                )


if __name__ == "__main__":
    unittest.main()
