#!/usr/bin/env python3
"""PowerShell AST parsing helpers for the function reachability report."""
from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from powershell_function_reachability_contract import Definition, Reference, SourceFile, ast_definition_kind, ast_invocation_kind, scalar
from powershell_function_reachability_parsing import captured_text, has_dynamic_command_text

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
