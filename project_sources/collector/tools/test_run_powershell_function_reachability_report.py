#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
import run_powershell_function_reachability_report as reach
import validate_powershell_function_reachability_report as reach_gate

REPO_ROOT = Path(__file__).resolve().parents[3]


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


class PowerShellFunctionReachabilityReportTests(unittest.TestCase):
    def make_repo(
        self,
        *,
        wrapper_text: str,
        part_texts: dict[str, str],
    ) -> tempfile.TemporaryDirectory[str]:
        temp = tempfile.TemporaryDirectory()
        root = Path(temp.name)
        wrapper_path = "project_sources/collector/source/DCOIR_Collector.ps1"
        part_paths = [f"project_sources/collector/source/parts/{name}" for name in part_texts]
        write(root / wrapper_path, textwrap.dedent(wrapper_text))
        for name, text in part_texts.items():
            write(root / "project_sources/collector/source/parts" / name, textwrap.dedent(text))
        write(
            root / reach.DEFAULT_MANIFEST,
            json.dumps(
                {
                    "collector_wrapper_source": wrapper_path,
                    "collector_part_files": part_paths,
                },
                indent=2,
            )
            + "\n",
        )
        return temp

    def args(self, root: Path, **overrides: object) -> argparse.Namespace:
        values: dict[str, object] = {
            "repo_root": str(root),
            "manifest": reach.DEFAULT_MANIFEST.as_posix(),
            "json_output": reach.DEFAULT_JSON_OUTPUT.as_posix(),
            "markdown_output": reach.DEFAULT_MARKDOWN_OUTPUT.as_posix(),
            "parser_mode": "python_lexical_fallback",
            "entrypoint": [],
            "no_write": True,
            "no_powershell": False,
        }
        values.update(overrides)
        return argparse.Namespace(**values)

    def build(self, root: Path, **overrides: object) -> dict[str, object]:
        return reach.build_report(self.args(root, **overrides))

    def test_real_collector_scope_counts_match_report_only_contract(self) -> None:
        report = self.build(REPO_ROOT)

        self.assertTrue(report["validation"]["success"])
        self.assertEqual(report["summary"]["source_file_count"], 44)
        self.assertEqual(report["summary"]["function_count"], 171)
        self.assertEqual(report["summary"]["classification_counts"]["literal_referenced"], 167)
        self.assertEqual(report["summary"]["classification_counts"]["dynamic_invocation_uncertain"], 4)
        self.assertEqual(report["summary"]["classification_counts"].get("static_unreferenced", 0), 0)
        self.assertEqual(report["summary"]["coverage_state"], "not_collected")
        self.assertEqual(report["summary"]["dynamic_invocation_site_count"], 1)
        self.assertTrue(any("safe to delete" in claim for claim in report["non_claims"]))

    def test_real_reachability_report_matches_committed_summary_gate(self) -> None:
        generated = self.build(REPO_ROOT)
        committed = json.loads((REPO_ROOT / reach.DEFAULT_JSON_OUTPUT).read_text(encoding="utf-8"))

        self.assertEqual([], reach_gate.compare_reports(generated, committed))

    def test_markdown_parity_carries_scope_counts_dynamic_sites_and_non_claims(self) -> None:
        report = self.build(REPO_ROOT)
        markdown = reach.render_markdown(report)

        self.assertEqual([], reach.validate_report(report))
        for fragment in (
            "PowerShell Function Reachability Report",
            "Runtime-lane coverage: `not_collected`",
            "`dynamic_invocation_uncertain` | 4",
            "This report does not claim any function is safe to delete.",
            "project_sources/collector/source/DCOIR_Collector.ps1",
        ):
            self.assertIn(fragment, markdown)

    def test_python_fallback_tracks_cross_file_literal_references_before_dynamic_uncertainty(self) -> None:
        with self.make_repo(
            wrapper_text="""
            function Invoke-Wrapper { Invoke-PartOne }
            . $partPath
            """,
            part_texts={
                "PartA.ps1": """
                function Invoke-PartOne { Invoke-PartTwo }
                function Invoke-Uncalled { 'not directly called' }
                """,
                "PartB.ps1": """
                function Invoke-PartTwo { Invoke-Wrapper }
                """,
            },
        ) as temp:
            report = self.build(Path(temp))

        self.assertTrue(report["validation"]["success"])
        self.assertEqual(report["summary"]["function_count"], 4)
        self.assertEqual(report["summary"]["classification_counts"]["literal_referenced"], 3)
        self.assertEqual(report["summary"]["classification_counts"]["dynamic_invocation_uncertain"], 1)
        self.assertEqual(report["summary"]["dynamic_invocation_site_count"], 1)
        by_name = {item["name"]: item for item in report["functions"]}
        self.assertEqual(by_name["Invoke-Uncalled"]["classification"], "dynamic_invocation_uncertain")
        self.assertEqual(by_name["Invoke-PartTwo"]["reference_count"], 1)

    def test_python_fallback_detects_backtick_obfuscated_invoke_expression(self) -> None:
        with self.make_repo(
            wrapper_text="""
            function Invoke-Wrapper { 'entry' }
            """,
            part_texts={
                "PartA.ps1": """
                function Invoke-Uncalled { 'not directly called' }
                I`n`v`o`k`e`-`E`x`p`r`e`s`s`i`o`n $scriptText
                """,
            },
        ) as temp:
            report = self.build(Path(temp), entrypoint=["Invoke-Wrapper"])

        self.assertTrue(report["validation"]["success"])
        self.assertEqual(report["summary"]["dynamic_invocation_site_count"], 1)
        self.assertEqual(report["dynamic_invocation_sites"][0]["kind"], "invoke_expression")
        by_name = {item["name"]: item for item in report["functions"]}
        self.assertEqual(by_name["Invoke-Uncalled"]["classification"], "dynamic_invocation_uncertain")

    def test_python_fallback_detects_case_variant_invoke_expression(self) -> None:
        with self.make_repo(
            wrapper_text="""
            function Invoke-Wrapper { 'entry' }
            """,
            part_texts={
                "PartA.ps1": """
                function Invoke-Uncalled { 'not directly called' }
                invoke-expression $scriptText
                """,
            },
        ) as temp:
            report = self.build(Path(temp), entrypoint=["Invoke-Wrapper"])

        self.assertTrue(report["validation"]["success"])
        self.assertEqual(report["summary"]["dynamic_invocation_site_count"], 1)
        self.assertEqual(report["dynamic_invocation_sites"][0]["kind"], "invoke_expression")
        by_name = {item["name"]: item for item in report["functions"]}
        self.assertEqual(by_name["Invoke-Uncalled"]["classification"], "dynamic_invocation_uncertain")

    def test_no_powershell_flag_forces_python_fallback_without_subprocess(self) -> None:
        parsed = reach.parse_args(["--no-powershell"])
        self.assertTrue(parsed.no_powershell)
        with self.make_repo(
            wrapper_text="""
            function Invoke-Wrapper { Invoke-PartOne }
            """,
            part_texts={
                "PartA.ps1": """
                function Invoke-PartOne { 'called' }
                """,
            },
        ) as temp:
            with patch.object(
                reach,
                "parse_with_powershell_ast",
                side_effect=AssertionError("PowerShell AST path should not run when --no-powershell is set"),
            ):
                report = self.build(Path(temp), parser_mode="auto", no_powershell=True)

        self.assertTrue(report["validation"]["success"])
        self.assertEqual(report["summary"]["parser_mode"], "python_lexical_fallback")
        self.assertEqual(report["generated_from"]["parser_mode"], "python_lexical_fallback")

    def test_powershell_ast_timeout_falls_back_with_text_warnings(self) -> None:
        with self.make_repo(
            wrapper_text="function Invoke-Wrapper { Invoke-PartOne }\n",
            part_texts={"PartA.ps1": "function Invoke-PartOne { }\n"},
        ) as temp:
            root = Path(temp)
            _manifest, sources, errors = reach.resolve_sources(root, root / reach.DEFAULT_MANIFEST)
            self.assertEqual([], errors)
            timeout = reach.subprocess.TimeoutExpired(
                cmd=["pwsh"],
                timeout=60,
                output=b"stdout bytes",
                stderr=b"stderr bytes",
            )
            with patch.object(reach, "powershell_executable", return_value="pwsh"):
                with patch.object(reach.subprocess, "run", side_effect=timeout):
                    definitions, references, dynamic_sites, warnings, parser_mode = reach.parse_with_powershell_ast(sources)

        self.assertEqual([], definitions)
        self.assertEqual([], references)
        self.assertEqual([], dynamic_sites)
        self.assertEqual("python_lexical_fallback", parser_mode)
        self.assertEqual("stdout bytes", warnings[0]["stdout"])
        self.assertEqual("stderr bytes", warnings[0]["stderr"])
        json.dumps(warnings)
