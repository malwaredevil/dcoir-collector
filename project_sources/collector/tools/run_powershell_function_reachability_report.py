#!/usr/bin/env python3
"""Build a report-only collector PowerShell function reachability report.

This #306 report is intentionally conservative. It checks only the
manifest-declared collector runtime source, records literal function references,
and reports dynamic invocation uncertainty without making deletion-readiness
claims. When PowerShell is available, it uses the PowerShell parser AST for
function and command discovery. Otherwise it falls back to a deterministic
Python lexical pass that masks comments, strings, and here-strings before
looking for definitions and literal references.
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

from powershell_function_reachability_contract import (
    CLASSIFICATIONS,
    DEFAULT_JSON_OUTPUT,
    DEFAULT_MANIFEST,
    DEFAULT_MARKDOWN_OUTPUT,
    ISSUE_NUMBER,
    NON_CLAIMS,
    PARENT_ISSUE_NUMBER,
    SCHEMA_VERSION,
    AnalyzerContractError,
    Definition,
    ReachabilityError,
    Reference,
    SourceFile,
    ast_definition_kind,
    ast_invocation_kind,
    context_line,
    line_column,
    normalize_newlines,
    read_json,
    repo_relative_input_path,
    resolve_sources,
    safe_manifest_source_path,
    safe_output_path,
    scalar,
    sha256_file,
    write_json,
)
import powershell_function_reachability_parsing as _parsing
from powershell_function_reachability_parsing import (
    AST_DYNAMIC_TEXT_RE,
    DYNAMIC_PATTERNS,
    FUNCTION_RE,
    INVOKE_EXPRESSION_RE,
    POWERSHELL_AST_SCRIPT,
    TOKEN_RE,
    brace_depths,
    captured_text,
    fallback_function_keys,
    fallback_parse_source,
    has_dynamic_command_text,
    mask_powershell_non_code,
    parse_sources as _parse_sources,
    parse_with_powershell_ast as _parse_with_powershell_ast,
    powershell_backtick_tolerant_literal,
    powershell_executable,
)
from powershell_function_reachability_reporting import (
    classify_functions,
    build_report as _build_report,
    reference_entry,
    render_markdown,
    validate_report,
    write_outputs,
)


def parse_with_powershell_ast(sources: list[SourceFile]) -> tuple[list[Definition], list[Reference], list[dict[str, object]], list[dict[str, object]], str]:
    original_powershell_executable = _parsing.powershell_executable
    _parsing.powershell_executable = powershell_executable
    try:
        return _parse_with_powershell_ast(sources)
    finally:
        _parsing.powershell_executable = original_powershell_executable


def parse_sources(sources: list[SourceFile], parser_mode: str) -> tuple[list[Definition], list[Reference], list[dict[str, object]], list[dict[str, object]], str]:
    if parser_mode in {"auto", "powershell_ast"}:
        definitions, references, dynamic_sites, warnings, mode = parse_with_powershell_ast(sources)
        if mode == "powershell_ast" or parser_mode == "powershell_ast":
            return definitions, references, dynamic_sites, warnings, mode
    return _parse_sources(sources, parser_mode)


def build_report(args: argparse.Namespace) -> dict[str, object]:
    return _build_report(args, parse_sources_func=parse_sources)


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", default=".", help="Repository root")
    parser.add_argument("--manifest", default=DEFAULT_MANIFEST.as_posix(), help="Collector runtime manifest")
    parser.add_argument("--json-output", default=DEFAULT_JSON_OUTPUT.as_posix(), help="Output JSON report path")
    parser.add_argument("--markdown-output", default=DEFAULT_MARKDOWN_OUTPUT.as_posix(), help="Output Markdown report path")
    parser.add_argument("--parser-mode", choices=("auto", "powershell_ast", "python_lexical_fallback"), default="auto")
    parser.add_argument("--no-powershell", action="store_true", help="Force the deterministic Python lexical fallback and never invoke PowerShell.")
    parser.add_argument("--entrypoint", action="append", default=[], help="Known entrypoint function name; repeatable")
    parser.add_argument("--no-write", action="store_true", help="Build report without writing output files")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv if argv is not None else sys.argv[1:])
    try:
        report = build_report(args)
        repo_root = Path(args.repo_root).resolve()
        if not args.no_write:
            write_outputs(repo_root, report, Path(args.json_output), Path(args.markdown_output))
    except ReachabilityError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    if report["validation"]["success"]:
        return 0
    for error in report["validation"]["errors"]:
        print(f"ERROR: {error}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
