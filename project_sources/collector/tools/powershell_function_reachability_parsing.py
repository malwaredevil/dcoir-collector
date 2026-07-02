#!/usr/bin/env python3
"""PowerShell parsing helpers for the function reachability report."""
from __future__ import annotations

import json
import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from powershell_function_reachability_contract import (
    Definition,
    Reference,
    SourceFile,
    ast_definition_kind,
    ast_invocation_kind,
    context_line,
    line_column,
    normalize_newlines,
    scalar,
)

POWERSHELL_AST_SCRIPT = r"""
param(
  [Parameter(Mandatory = $true)][string]$InputJson,
  [Parameter(Mandatory = $true)][string]$OutputJson
)

$ErrorActionPreference = 'Stop'
$payload = Get-Content -LiteralPath $InputJson -Raw -Encoding UTF8 | ConvertFrom-Json
$items = New-Object System.Collections.Generic.List[object]

foreach ($source in $payload.sources) {
  $path = [string]$source.path
  $repo_path = [string]$source.repo_path
  $load_order = [int]$source.load_order
  $text = Get-Content -LiteralPath $path -Raw -Encoding UTF8
  $tokens = $null
  $parseErrors = $null
  $ast = [System.Management.Automation.Language.Parser]::ParseInput($text, [ref]$tokens, [ref]$parseErrors)
  $errors = @()
  if ($parseErrors) {
    foreach ($err in $parseErrors) {
      $errors += [ordered]@{
        line = $err.Extent.StartLineNumber
        column = $err.Extent.StartColumnNumber
        message = $err.Message
      }
    }
  }

  $defs = @()
  foreach ($fn in $ast.FindAll({ param($node) $node -is [System.Management.Automation.Language.FunctionDefinitionAst] }, $true)) {
    $parent = $fn.Parent
    $nested = $false
    while ($null -ne $parent) {
      if ($parent -is [System.Management.Automation.Language.FunctionDefinitionAst]) {
        $nested = $true
        break
      }
      $parent = $parent.Parent
    }
    $defs += [ordered]@{
      name = $fn.Name
      source_path = $repo_path
      line = $fn.Extent.StartLineNumber
      column = $fn.Extent.StartColumnNumber
      end_line = $fn.Extent.EndLineNumber
      definition_kind = $(if ($nested) { 'nested' } else { 'top_level' })
      load_order = $load_order
    }
  }

  $commands = @()
  foreach ($cmd in $ast.FindAll({ param($node) $node -is [System.Management.Automation.Language.CommandAst] }, $true)) {
    $name = $cmd.GetCommandName()
    $commands += [ordered]@{
      name = $name
      source_path = $repo_path
      line = $cmd.Extent.StartLineNumber
      column = $cmd.Extent.StartColumnNumber
      invocation_operator = [string]$cmd.InvocationOperator
      text = $cmd.Extent.Text
    }
  }

  $items.Add([ordered]@{
    repo_path = $repo_path
    load_order = $load_order
    parse_errors = $errors
    definitions = $defs
    commands = $commands
  })
}

$items | ConvertTo-Json -Depth 10 | Out-File -LiteralPath $OutputJson -Encoding UTF8
"""


def powershell_backtick_tolerant_literal(value: str) -> str:
    return r"`*".join(re.escape(char) for char in value)


FUNCTION_RE = re.compile(r"(?i)(?<![-\w])function\s+([A-Za-z_][A-Za-z0-9_-]*)")
TOKEN_RE = re.compile(r"(?<![-\w])([A-Za-z_][A-Za-z0-9_-]*)(?![-\w])")
INVOKE_EXPRESSION_RE = re.compile(
    r"(?<![-\w])" + powershell_backtick_tolerant_literal("Invoke-Expression") + r"(?![-\w])",
    re.IGNORECASE,
)
AST_DYNAMIC_TEXT_RE = re.compile(r"(?i)(^|\s)(Invoke-Expression|&\s*\$|\.\s*\$|\[ScriptBlock\]::Create)")
DYNAMIC_PATTERNS = (
    ("call_operator_variable", re.compile(r"&[ \t]*\$[A-Za-z_][A-Za-z0-9_]*", re.IGNORECASE)),
    ("dot_source_variable", re.compile(r"\.[ \t]*\$[A-Za-z_][A-Za-z0-9_]*", re.IGNORECASE)),
    ("invoke_expression", INVOKE_EXPRESSION_RE),
    ("scriptblock_create", re.compile(r"\[ScriptBlock\]::Create", re.IGNORECASE)),
)


def captured_text(value: Any, limit: int = 240) -> str:
    return scalar(value).strip()[:limit]


def has_dynamic_command_text(text: str) -> bool:
    return AST_DYNAMIC_TEXT_RE.search(text) is not None or any(pattern.search(text) for _kind, pattern in DYNAMIC_PATTERNS)


def mask_powershell_non_code(text: str) -> str:
    """Mask comments and string bodies while preserving line/column layout."""
    chars = list(normalize_newlines(text))
    i = 0
    state = "code"
    quote = ""
    here_end = ""
    while i < len(chars):
        ch = chars[i]
        nxt = chars[i + 1] if i + 1 < len(chars) else ""
        if state == "code":
            if ch == "<" and nxt == "#":
                chars[i] = chars[i + 1] = " "
                i += 2
                state = "block_comment"
                continue
            if ch == "#":
                while i < len(chars) and chars[i] != "\n":
                    chars[i] = " "
                    i += 1
                continue
            if ch == "@" and nxt in {"'", '"'}:
                quote = nxt
                here_end = nxt + "@"
                chars[i] = chars[i + 1] = " "
                i += 2
                state = "here_string"
                continue
            if ch in {"'", '"'}:
                quote = ch
                chars[i] = " "
                i += 1
                state = "string"
                continue
            i += 1
            continue
        if state == "block_comment":
            if ch == "#" and nxt == ">":
                chars[i] = chars[i + 1] = " "
                i += 2
                state = "code"
                continue
            if ch != "\n":
                chars[i] = " "
            i += 1
            continue
        if state == "string":
            if ch == "`":
                chars[i] = " "
                if i + 1 < len(chars) and chars[i + 1] != "\n":
                    chars[i + 1] = " "
                    i += 2
                else:
                    i += 1
                continue
            if ch == quote:
                if quote == "'" and nxt == "'":
                    chars[i] = chars[i + 1] = " "
                    i += 2
                    continue
                chars[i] = " "
                i += 1
                state = "code"
                continue
            if ch != "\n":
                chars[i] = " "
            i += 1
            continue
        if state == "here_string":
            at_line_start = i == 0 or chars[i - 1] == "\n"
            if at_line_start:
                probe_end = i + len(here_end)
                if "".join(chars[i:probe_end]) == here_end:
                    for j in range(i, probe_end):
                        chars[j] = " "
                    i = probe_end
                    state = "code"
                    continue
            if ch != "\n":
                chars[i] = " "
            i += 1
            continue
    return "".join(chars)


def brace_depths(masked: str) -> list[int]:
    depths: list[int] = [0] * (len(masked) + 1)
    depth = 0
    for i, ch in enumerate(masked):
        depths[i] = depth
        if ch == "{":
            depth += 1
        elif ch == "}" and depth > 0:
            depth -= 1
    depths[len(masked)] = depth
    return depths


def fallback_function_keys(sources: list[SourceFile]) -> set[str]:
    keys: set[str] = set()
    for source in sources:
        text = normalize_newlines(source.path.read_text(encoding="utf-8", errors="ignore"))
        masked = mask_powershell_non_code(text)
        keys.update(match.group(1).casefold() for match in FUNCTION_RE.finditer(masked))
    return keys


def fallback_parse_source(
    source: SourceFile,
    all_function_keys: set[str] | None = None,
) -> tuple[list[Definition], list[Reference], list[dict[str, Any]], list[dict[str, Any]]]:
    text = normalize_newlines(source.path.read_text(encoding="utf-8", errors="ignore"))
    masked = mask_powershell_non_code(text)
    depths = brace_depths(masked)
    definitions: list[Definition] = []
    definition_spans: list[tuple[int, int]] = []
    for match in FUNCTION_RE.finditer(masked):
        name = match.group(1)
        name_start, name_end = match.span(1)
        line, column = line_column(masked, name_start)
        definition_spans.append((name_start, name_end))
        definitions.append(
            Definition(
                name=name,
                source_path=source.repo_path,
                line=line,
                column=column,
                end_line=None,
                definition_kind="nested" if depths[match.start()] > 0 else "top_level",
                load_order=source.load_order,
            )
        )

    definition_name_spans = set(definition_spans)
    function_keys = all_function_keys if all_function_keys is not None else {definition.name.casefold() for definition in definitions}
    references: list[Reference] = []
    for match in TOKEN_RE.finditer(masked):
        name = match.group(1)
        if name.casefold() not in function_keys:
            continue
        if match.span(1) in definition_name_spans:
            continue
        prefix = masked[max(0, match.start() - 10) : match.start()]
        if re.search(r"(?i)\bfunction\s+$", prefix):
            continue
        previous = masked[match.start() - 1] if match.start() > 0 else ""
        if previous in {"$", "-", "."}:
            continue
        line, column = line_column(masked, match.start(1))
        references.append(
            Reference(
                name=name,
                source_path=source.repo_path,
                line=line,
                column=column,
                invocation_kind="literal_token",
                parser="python_lexical_fallback",
            )
        )

    dynamic_sites: list[dict[str, Any]] = []
    for kind, pattern in DYNAMIC_PATTERNS:
        for match in pattern.finditer(masked):
            line, column = line_column(masked, match.start())
            dynamic_sites.append(
                {
                    "kind": kind,
                    "source_path": source.repo_path,
                    "line": line,
                    "column": column,
                    "context": context_line(text, line),
                    "claim": "dynamic invocation site creates bounded static-analysis uncertainty",
                }
            )
    return definitions, references, dynamic_sites, []


def powershell_executable() -> str | None:
    return shutil.which("pwsh") or shutil.which("powershell")


def _text_from_timeout(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return str(value)


def parse_with_powershell_ast(sources: list[SourceFile]) -> tuple[list[Definition], list[Reference], list[dict[str, Any]], list[dict[str, Any]], str]:
    exe = powershell_executable()
    if not exe:
        return [], [], [], [{"message": "PowerShell parser executable not found; used Python lexical fallback."}], "python_lexical_fallback"

    payload = {
        "sources": [
            {"path": source.path.as_posix(), "repo_path": source.repo_path, "load_order": source.load_order}
            for source in sources
        ]
    }
    with tempfile.TemporaryDirectory(prefix="dcoir-reachability-") as temp:
        temp_dir = Path(temp)
        input_json = temp_dir / "input.json"
        output_json = temp_dir / "output.json"
        script_path = temp_dir / "parse.ps1"
        input_json.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        script_path.write_text(POWERSHELL_AST_SCRIPT, encoding="utf-8")
        try:
            proc = subprocess.run(
                [exe, "-NoProfile", "-File", str(script_path), str(input_json), str(output_json)],
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=60,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            return [], [], [], [
                {
                    "message": "PowerShell AST parse timed out; used Python lexical fallback.",
                    "stdout": _text_from_timeout(exc.output),
                    "stderr": _text_from_timeout(exc.stderr),
                }
            ], "python_lexical_fallback"
        if proc.returncode != 0 or not output_json.exists():
            warning = {
                "message": "PowerShell AST parse failed; used Python lexical fallback.",
                "stdout": proc.stdout[-1000:],
                "stderr": proc.stderr[-1000:],
            }
            return [], [], [], [warning], "python_lexical_fallback"
        raw = json.loads(output_json.read_text(encoding="utf-8-sig"))

    raw_items = [raw] if isinstance(raw, dict) else raw if isinstance(raw, list) else []
    definitions: list[Definition] = []
    references: list[Reference] = []
    dynamic_sites: list[dict[str, Any]] = []
    parse_errors: list[dict[str, Any]] = []
    function_names: set[str] = set()

    for item in raw_items:
        if not isinstance(item, dict):
            continue
        for error in item.get("parse_errors", []):
            if isinstance(error, dict):
                parse_errors.append({"source_path": item.get("repo_path"), **error})
        for raw_def in item.get("definitions", []):
            if not isinstance(raw_def, dict):
                continue
            name = scalar(raw_def.get("name")).strip()
            if not name:
                continue
            function_names.add(name.casefold())
            definitions.append(
                Definition(
                    name=name,
                    source_path=scalar(raw_def.get("source_path")).strip(),
                    line=int(raw_def.get("line") or 0),
                    column=int(raw_def.get("column") or 0) or None,
                    end_line=int(raw_def.get("end_line") or 0) or None,
                    definition_kind=ast_definition_kind(raw_def.get("definition_kind")),
                    load_order=int(raw_def.get("load_order") or 0),
                )
            )

    for item in raw_items:
        if not isinstance(item, dict):
            continue
        for raw_cmd in item.get("commands", []):
            if not isinstance(raw_cmd, dict):
                continue
            name = scalar(raw_cmd.get("name")).strip()
            text = scalar(raw_cmd.get("text")).strip()
            source_path = scalar(raw_cmd.get("source_path")).strip()
            line = int(raw_cmd.get("line") or 0)
            column = int(raw_cmd.get("column") or 0) or None
            invocation = ast_invocation_kind(raw_cmd.get("invocation_operator"))
            if name and name.casefold() in function_names:
                references.append(
                    Reference(
                        name=name,
                        source_path=source_path,
                        line=line,
                        column=column,
                        invocation_kind=invocation,
                        parser="powershell_ast",
                    )
                )
            if not name or has_dynamic_command_text(text):
                dynamic_sites.append(
                    {
                        "kind": "ast_dynamic_or_expression_command",
                        "source_path": source_path,
                        "line": line,
                        "column": column,
                        "context": captured_text(text),
                        "claim": "PowerShell AST could not resolve this command to a literal local function name.",
                    }
                )
    return definitions, references, dynamic_sites, parse_errors, "powershell_ast"


def parse_sources(sources: list[SourceFile], parser_mode: str) -> tuple[list[Definition], list[Reference], list[dict[str, Any]], list[dict[str, Any]], str]:
    definitions: list[Definition] = []
    references: list[Reference] = []
    dynamic_sites: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    all_function_keys = fallback_function_keys(sources)
    for source in sources:
        defs, refs, dynamic, parse_warnings = fallback_parse_source(source, all_function_keys)
        definitions.extend(defs)
        references.extend(refs)
        dynamic_sites.extend(dynamic)
        warnings.extend(parse_warnings)
    return definitions, references, dynamic_sites, warnings, "python_lexical_fallback"
