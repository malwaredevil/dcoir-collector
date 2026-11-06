#!/usr/bin/env python3
"""Behavior-parity tests for the canonical workflow-file discovery helper."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from lib.workflow_files import iter_workflow_files
from lib.audit_reusable_contract_helpers import iter_all_workflow_files


class WorkflowFileDiscoveryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.workflow_dir = Path(self.temp.name) / "workflows"
        self.workflow_dir.mkdir()

    def add(self, name: str) -> None:
        file = self.workflow_dir / name
        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_text("name: test\n", encoding="utf-8")

    def test_missing_directory_returns_no_files(self) -> None:
        self.assertEqual(iter_workflow_files(self.workflow_dir / "missing"), [])
        self.assertEqual(iter_workflow_files(self.workflow_dir / "missing", include_reusable=False), [])

    def test_empty_directory_returns_no_files(self) -> None:
        self.assertEqual(iter_workflow_files(self.workflow_dir), [])
        self.assertEqual(iter_workflow_files(self.workflow_dir, include_reusable=False), [])

    def test_yaml_extensions_and_sorted_order(self) -> None:
        for name in ("z.yaml", "b.yml", "a.YAML", "c.txt", "d.yml.bak", "f.YmL"):
            self.add(name)
        expected = ["a.YAML", "b.yml", "f.YmL", "z.yaml"]
        self.assertEqual([p.name for p in iter_workflow_files(self.workflow_dir)], expected)

    def test_primary_excludes_reusable_but_all_includes(self) -> None:
        for name in ("validate.yml", "reusable-build.yml", "reusable-check.yaml", "Reusable-X.yml"):
            self.add(name)
        all_names = [p.name for p in iter_workflow_files(self.workflow_dir)]
        primary = [p.name for p in iter_workflow_files(self.workflow_dir, include_reusable=False)]
        self.assertEqual(all_names, ["Reusable-X.yml", "reusable-build.yml", "reusable-check.yaml", "validate.yml"])
        self.assertEqual(primary, ["Reusable-X.yml", "validate.yml"])

    def test_nested_files_and_directories_are_excluded(self) -> None:
        self.add("top.yml")
        self.add("nested/hidden.yaml")
        (self.workflow_dir / "folder.yml").mkdir()
        self.assertEqual([p.name for p in iter_workflow_files(self.workflow_dir)], ["top.yml"])

    def test_legacy_all_and_primary_semantics_match(self) -> None:
        for name in ("a.yaml", "reusable-1.YAML", "work.yml", "reusable-2.yml", "skip.txt"):
            self.add(name)
        legacy_all = sorted(
            p for p in self.workflow_dir.iterdir()
            if p.is_file() and p.suffix.lower() in {".yml", ".yaml"}
        )
        legacy_primary = sorted(
            p for p in self.workflow_dir.iterdir()
            if p.is_file() and p.suffix.lower() in {".yml", ".yaml"}
            and not p.name.startswith("reusable-")
        )
        self.assertEqual(iter_workflow_files(self.workflow_dir), legacy_all)
        self.assertEqual(iter_workflow_files(self.workflow_dir, include_reusable=False), legacy_primary)


    def test_audit_helper_returns_empty_for_missing_repo_workflows(self) -> None:
        missing_repo = Path(self.temp.name) / "checkout"
        self.assertEqual(iter_all_workflow_files(missing_repo), [])
        (missing_repo / ".github/workflows").mkdir(parents=True)
        self.assertEqual(iter_all_workflow_files(missing_repo), [])

    def test_audit_helper_matches_shared_discovery_with_hostile_layout(self) -> None:
        repo_root = Path(self.temp.name) / "checkout"
        workflows = repo_root / ".github/workflows"
        workflows.mkdir(parents=True)
        for name in (
            "Z.yaml", "alpha.yml", "reusable-child.yml", "mixed.YmL",
            "ignored.txt", "nested/hidden.yaml", "backup.yml.bak",
        ):
            file = workflows / name
            file.parent.mkdir(parents=True, exist_ok=True)
            file.write_text("name: fixture\n", encoding="utf-8")
        (workflows / "directory.yml").mkdir()

        actual = iter_all_workflow_files(repo_root)
        self.assertEqual(actual, iter_workflow_files(workflows))
        self.assertEqual(
            [path.name for path in actual],
            ["Z.yaml", "alpha.yml", "mixed.YmL", "reusable-child.yml"],
        )
        self.assertIn("reusable-child.yml", [path.name for path in actual])


    def test_contract_runner_counts_primary_files_in_the_selected_checkout(self) -> None:
        from unittest.mock import patch
        from lib.audit_reusable_contract_runner import run_contract_audit

        repo_root = Path(self.temp.name) / "alternate-checkout"
        workflows = repo_root / ".github/workflows"
        workflows.mkdir(parents=True)
        for name, body in (
            ("main.yml", "name: Main\non: push\n"),
            ("mixed.YmL", "name: Mixed\non: push\n"),
            ("reusable-build.YAML", "name: Reusable\non:\n  workflow_call:\n"),
            ("nested/hidden.yml", "name: Ignored\n"),
            ("backup.yml.bak", "name: Ignored\n"),
        ):
            path = workflows / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(body, encoding="utf-8")
        (workflows / "directory.yaml").mkdir()

        with patch(
            "lib.audit_reusable_contract_checks.read_contracts",
            return_value={"existing_workflow_count": 2},
        ):
            findings, summary = run_contract_audit(repo_root)

        self.assertEqual(findings, [])
        self.assertEqual(summary["primary_workflows"], 2)
        self.assertEqual(summary["reusable_workflows"], 1)
        self.assertEqual(summary["action_definitions"], 0)
        self.assertEqual(summary["workflow_refs"], 0)

    def test_contract_runner_missing_checkout_does_not_count_the_current_tree(self) -> None:
        from lib.audit_reusable_contract_runner import run_contract_audit

        missing_repo = Path(self.temp.name) / "not-a-checkout"
        findings, summary = run_contract_audit(missing_repo)
        self.assertEqual(summary["primary_workflows"], 0)
        self.assertEqual(summary["reusable_workflows"], 0)
        self.assertTrue(any("no workflow files found" in finding for finding in findings))


    def test_inventory_model_uses_canonical_discovery_for_reusable_variants(self) -> None:
        import os
        from unittest.mock import patch
        from lib.workflow_inventory_core import build_inventory

        repo_root = Path(self.temp.name) / "inventory-checkout"
        workflows = repo_root / ".github/workflows"
        workflows.mkdir(parents=True)
        for name, body in (
            ("validate.yml", "name: Validate\non: push\njobs:\n  call:\n    uses: ./.github/workflows/reusable-mixed.YAML\n"),
            ("manual.YmL", "name: Manual\non: workflow_dispatch\n"),
            ("reusable-standard.yml", "name: Standard\non:\n  workflow_call:\n"),
            ("reusable-mixed.YAML", "name: Mixed\non:\n  workflow_call:\n"),
            ("reusable-alt.yaml", "name: Alternate\non:\n  workflow_call:\n"),
            ("nested/reusable-ignored.yaml", "name: Ignored Nested\n"),
            ("reusable-ignored.yml.bak", "name: Ignored Backup\n"),
        ):
            path = workflows / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(body, encoding="utf-8")
        (workflows / "reusable-directory.yaml").mkdir()

        prior_directory = Path.cwd()
        try:
            os.chdir(repo_root)
            with patch(
                "lib.workflow_inventory_core.read_contracts",
                return_value={
                    "governing_issue": 194,
                    "existing_workflow_count": 2,
                    "workflow_contracts": [],
                },
            ):
                inventory = build_inventory()
        finally:
            os.chdir(prior_directory)

        self.assertEqual(inventory["workflow_count"], 2)
        self.assertEqual(inventory["reusable_workflow_count"], 3)
        self.assertEqual(inventory["local_reusable_workflow_calls"], 1)
        self.assertEqual(inventory["local_composite_action_calls"], 0)
        self.assertEqual(
            [entry["file"] for entry in inventory["workflows"]],
            [".github/workflows/manual.YmL", ".github/workflows/validate.yml"],
        )


    def test_action_metadata_discovery_scopes_directories_and_yaml_suffixes(self) -> None:
        from lib.audit_reusable_contract_helpers import iter_action_metadata_files

        root = Path(self.temp.name) / "action-discovery-checkout"
        actions = root / ".github/actions"
        for name in (
            "a/action.yml", "b/action.yaml", "c/ACTION.YAML",
            "a/nested/action.yml", "d/action.yml.bak", "e/action.ymml",
        ):
            path = actions / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("name: fixture\n", encoding="utf-8")
        (actions / "f/action.yml").mkdir(parents=True)

        direct = iter_action_metadata_files(root, top_level_only=True)
        recursive = iter_action_metadata_files(root)
        self.assertEqual(
            [path.relative_to(actions).as_posix() for path in direct],
            ["a/action.yml", "b/action.yaml", "c/ACTION.YAML"],
        )
        self.assertEqual(
            [path.relative_to(actions).as_posix() for path in recursive],
            ["a/action.yml", "a/nested/action.yml", "b/action.yaml", "c/ACTION.YAML"],
        )
        self.assertEqual(
            iter_action_metadata_files(root / "missing", top_level_only=True), []
        )

    def test_inventory_and_version_audit_share_action_metadata_scope(self) -> None:
        import os
        from unittest.mock import patch
        import check_workflow_action_versions as versions
        from lib.workflow_inventory_core import build_inventory

        root = Path(self.temp.name) / "action-consumer-checkout"
        actions = root / ".github/actions"
        sources = {
            "a/action.yml": "name: A\nruns:\n  using: composite\n  steps:\n    - uses: actions/checkout@v5\n",
            "b/action.yaml": "name: B\nruns:\n  using: composite\n  steps:\n    - uses: ./.github/actions/a\n",
            "c/ACTION.YAML": "name: C\nruns:\n  using: composite\n",
            "a/nested/action.yml": "name: Nested\nruns:\n  using: composite\n",
            "d/action.ymml": "name: Invalid\n",
        }
        for name, content in sources.items():
            path = actions / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")

        prior_directory = Path.cwd()
        try:
            os.chdir(root)
            with patch(
                "lib.workflow_inventory_core.read_contracts",
                return_value={"governing_issue": 194, "workflow_contracts": []},
            ):
                inventory = build_inventory()
            audited = versions.iter_composite_action_files()
            version_findings = [
                finding for path in audited for finding in versions.check_file(path)
            ]
        finally:
            os.chdir(prior_directory)

        self.assertEqual(inventory["workflow_count"], 0)
        self.assertEqual(inventory["composite_action_count"], 3)
        self.assertEqual(inventory["local_composite_action_calls"], 1)
        self.assertEqual(
            [path.relative_to(root / ".github/actions").as_posix() for path in audited],
            ["a/action.yml", "b/action.yaml", "c/ACTION.YAML"],
        )
        self.assertTrue(
            any("actions/checkout@v5 is below approved minimum" in finding for finding in version_findings)
        )


if __name__ == "__main__":
    unittest.main()
