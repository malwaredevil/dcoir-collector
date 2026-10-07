#!/usr/bin/env python3
"""Static name-resolution guard for the manual test runner modules.

The runner modules share names through star imports and explicit import
lists, so a missing import surfaces only as a NameError on the operator's
machine (for example in top_level_failure, after a step has already failed).
Importing the modules here is not an option: dcoir_manual_runner_context parses
sys.argv and loads runner state at import time. This test resolves names from
the source instead, following star imports between the runner modules.
"""
from __future__ import annotations

import ast
import builtins
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
RUNNER_MODULES = (
    'dcoir_manual_runner_context',
    'dcoir_manual_runner_package',
    'dcoir_manual_runner_checks_part_01',
    'dcoir_manual_runner_checks_part_02',
    'dcoir_manual_runner_checks',
    'dcoir_manual_runner_flow',
    'dcoir_manual_test_runner',
)


def parse(module: str) -> ast.Module:
    return ast.parse((HERE / f'{module}.py').read_text(encoding='utf-8'))


def bound_names(nodes: list[ast.AST]) -> set[str]:
    names: set[str] = set()
    for node in nodes:
        for child in ast.walk(node):
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                names.add(child.name)
            elif isinstance(child, ast.Name) and isinstance(child.ctx, (ast.Store, ast.Del)):
                names.add(child.id)
            elif isinstance(child, ast.alias) and child.name != '*':
                names.add((child.asname or child.name).split('.')[0])
            elif isinstance(child, ast.arg):
                names.add(child.arg)
            elif isinstance(child, ast.ExceptHandler) and child.name:
                names.add(child.name)
    return names


def module_namespace(module: str, seen: frozenset[str] = frozenset()) -> set[str]:
    tree = parse(module)
    names = bound_names(tree.body)
    for node in tree.body:
        if isinstance(node, ast.ImportFrom) and any(alias.name == '*' for alias in node.names):
            if node.module in RUNNER_MODULES and node.module not in seen:
                exported = module_namespace(node.module, seen | {module})
                names |= {name for name in exported if not name.startswith('_')}
    return names


def top_level_functions(tree: ast.Module) -> list[ast.FunctionDef | ast.AsyncFunctionDef]:
    functions = []
    for node in tree.body:
        members = node.body if isinstance(node, ast.ClassDef) else [node]
        functions += [m for m in members if isinstance(m, (ast.FunctionDef, ast.AsyncFunctionDef))]
    return functions


def unresolved_names(module: str) -> set[str]:
    available = module_namespace(module) | set(dir(builtins)) | {'__file__', '__name__'}
    missing: set[str] = set()
    for function in top_level_functions(parse(module)):
        # Nested functions and closures are covered by binding over the whole body.
        local = bound_names([function.args, *function.body])
        for child in ast.walk(function):
            if isinstance(child, ast.Name) and isinstance(child.ctx, ast.Load):
                if child.id not in available and child.id not in local:
                    missing.add(f'{function.name}: {child.id}')
    return missing


class ManualRunnerNameResolutionTests(unittest.TestCase):
    def test_every_function_body_name_resolves(self) -> None:
        for module in RUNNER_MODULES:
            with self.subTest(module=module):
                self.assertEqual(unresolved_names(module), set())

    def test_failure_handler_can_reach_cleanup(self) -> None:
        self.assertIn('cleanup_transient_framework_artifacts', module_namespace('dcoir_manual_runner_flow'))


if __name__ == '__main__':
    unittest.main()
