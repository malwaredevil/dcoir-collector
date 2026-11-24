#!/usr/bin/env python3
"""Focused self-tests for apply-patch push-path resolution."""
from __future__ import annotations

import unittest

from lib.apply_patch_request_resolver import resolve_from_changed_records


class ApplyPatchRequestResolverTests(unittest.TestCase):
    def test_empty_push_change_scan_fails_closed(self) -> None:
        with self.assertRaises(SystemExit) as caught:
            resolve_from_changed_records([], "push")
        self.assertIn("produced no paths", str(caught.exception))

    def test_empty_non_push_change_scan_remains_noop(self) -> None:
        self.assertEqual(resolve_from_changed_records([], "workflow_call"), (None, True))

    def test_root_level_readme_push_is_clean_noop(self) -> None:
        self.assertEqual(
            resolve_from_changed_records(
                [("M", ".github/ops/requests/apply_patch/README.md")],
                "push",
            ),
            (None, True),
        )

    def test_root_level_scaffold_push_is_clean_noop(self) -> None:
        self.assertEqual(
            resolve_from_changed_records(
                [("A", ".github/ops/requests/apply_patch/.gitkeep")],
                "push",
            ),
            (None, True),
        )

    def test_valid_request_json_resolves(self) -> None:
        request_path = ".github/ops/requests/apply_patch/demo/request.json"
        self.assertEqual(
            resolve_from_changed_records([("A", request_path)], "push"),
            (request_path, False),
        )

    def test_patch_only_maps_to_request_for_later_missing_file_failure(self) -> None:
        request_path = ".github/ops/requests/apply_patch/demo/request.json"
        self.assertEqual(
            resolve_from_changed_records(
                [("A", ".github/ops/requests/apply_patch/demo/change.patch")],
                "push",
            ),
            (request_path, False),
        )

    def test_unrecognized_added_request_directory_path_fails_closed(self) -> None:
        with self.assertRaises(SystemExit) as caught:
            resolve_from_changed_records(
                [("A", ".github/ops/requests/apply_patch/demo/notes.txt")],
                "push",
            )
        self.assertEqual(caught.exception.code, 1)

    def test_malformed_request_id_path_fails_closed(self) -> None:
        with self.assertRaises(SystemExit) as caught:
            resolve_from_changed_records(
                [("A", ".github/ops/requests/apply_patch/bad id/request.json")],
                "push",
            )
        self.assertEqual(caught.exception.code, 1)

    def test_cleanup_only_deleted_request_directory_path_is_noop(self) -> None:
        self.assertEqual(
            resolve_from_changed_records(
                [("D", ".github/ops/requests/apply_patch/demo/old-report.txt")],
                "push",
            ),
            (None, True),
        )


if __name__ == "__main__":
    unittest.main()
