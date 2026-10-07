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
    class BindingCollector(ast.NodeVisitor):
        def __init__(self) -> None:
            self.names: set[str] = set()
            self.declared: set[str] = set()

        def visit_Global(self, node: ast.Global) -> None:
            self.declared.update(node.names)

        def visit_Nonlocal(self, node: ast.Nonlocal) -> None:
            self.declared.update(node.names)

        def visit_Name(self, node: ast.Name) -> None:
            if isinstance(node.ctx, (ast.Store, ast.Del)):
                self.names.add(node.id)

        def visit_arg(self, node: ast.arg) -> None:
            self.names.add(node.arg)
            if node.annotation:
                self.visit(node.annotation)

        def visit_alias(self, node: ast.alias) -> None:
            if node.name != '*':
                self.names.add((node.asname or node.name).split('.')[0])

        def visit_ExceptHandler(self, node: ast.ExceptHandler) -> None:
            if node.name:
                self.names.add(node.name)
            self.generic_visit(node)

        def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
            self._visit_function_header(node)

        visit_AsyncFunctionDef = visit_FunctionDef

        def visit_ClassDef(self, node: ast.ClassDef) -> None:
            self.names.add(node.name)
            for item in (*node.decorator_list, *node.bases, *node.keywords):
                self.visit(item)

        def visit_Lambda(self, node: ast.Lambda) -> None:
            self._visit_arguments(node.args)

        def visit_ListComp(self, node: ast.ListComp) -> None:
            self._visit_comprehension(node)

        visit_SetComp = visit_ListComp
        visit_GeneratorExp = visit_ListComp
        visit_DictComp = visit_ListComp

        def _visit_arguments(self, args: ast.arguments) -> None:
            for arg in (*args.posonlyargs, *args.args, *args.kwonlyargs):
                if arg.annotation:
                    self.visit(arg.annotation)
            if args.vararg and args.vararg.annotation:
                self.visit(args.vararg.annotation)
            if args.kwarg and args.kwarg.annotation:
                self.visit(args.kwarg.annotation)
            for default in (*args.defaults, *(value for value in args.kw_defaults if value)):
                self.visit(default)

        def _visit_function_header(
            self, node: ast.FunctionDef | ast.AsyncFunctionDef
        ) -> None:
            self.names.add(node.name)
            for item in node.decorator_list:
                self.visit(item)
            self._visit_arguments(node.args)
            if node.returns:
                self.visit(node.returns)

        def _visit_comprehension(
            self, node: ast.ListComp | ast.SetComp | ast.GeneratorExp | ast.DictComp
        ) -> None:
            for generator in node.generators:
                self.visit(generator.iter)
                for condition in generator.ifs:
                    self.visit(condition)
            if isinstance(node, ast.DictComp):
                self.visit(node.key)
                self.visit(node.value)
            else:
                self.visit(node.elt)

    collector = BindingCollector()
    for node in nodes:
        collector.visit(node)
    return collector.names - collector.declared


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


class FunctionNameResolver(ast.NodeVisitor):
    def __init__(
        self,
        *,
        globals_: set[str],
        enclosing: set[str],
        local: set[str],
        captures: set[str],
        label: str,
        missing: set[str],
    ) -> None:
        self.globals = globals_
        self.enclosing = enclosing
        self.local = local
        self.captures = captures
        self.label = label
        self.missing = missing

    def visit_Name(self, node: ast.Name) -> None:
        if (
            isinstance(node.ctx, ast.Load)
            and node.id not in self.globals | self.enclosing | self.local
        ):
            self.missing.add(f'{self.label}: {node.id}')

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._visit_function_header(node)
        analyze_function(
            node,
            globals_=self.globals,
            enclosing=self.captures,
            label=f'{self.label}.{node.name}',
            missing=self.missing,
        )

    visit_AsyncFunctionDef = visit_FunctionDef

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        for item in (*node.decorator_list, *node.bases, *node.keywords):
            self.visit(item)
        class_scope = FunctionNameResolver(
            globals_=self.globals,
            enclosing=self.captures,
            local=bound_names(node.body),
            captures=self.captures,
            label=f'{self.label}.{node.name}',
            missing=self.missing,
        )
        for item in node.body:
            class_scope.visit(item)

    def visit_Lambda(self, node: ast.Lambda) -> None:
        for default in (*node.args.defaults, *(value for value in node.args.kw_defaults if value)):
            self.visit(default)
        analyze_lambda(
            node,
            globals_=self.globals,
            enclosing=self.captures,
            label=f'{self.label}.<lambda>',
            missing=self.missing,
        )

    def visit_ListComp(self, node: ast.ListComp) -> None:
        self._visit_comprehension(node)

    visit_SetComp = visit_ListComp
    visit_GeneratorExp = visit_ListComp
    visit_DictComp = visit_ListComp

    def _visit_function_header(
        self, node: ast.FunctionDef | ast.AsyncFunctionDef
    ) -> None:
        for item in node.decorator_list:
            self.visit(item)
        self.visit(node.args)
        if node.returns:
            self.visit(node.returns)

    def _visit_comprehension(
        self, node: ast.ListComp | ast.SetComp | ast.GeneratorExp | ast.DictComp
    ) -> None:
        if not node.generators:
            return
        self.visit(node.generators[0].iter)
        bound_targets: set[str] = set()
        for index, generator in enumerate(node.generators):
            if index:
                self._visit_comprehension_expression(generator.iter, bound_targets)
            self._visit_comprehension_expression(generator.target, bound_targets)
            bound_targets.update(
                child.id
                for child in ast.walk(generator.target)
                if isinstance(child, ast.Name) and isinstance(child.ctx, ast.Store)
            )
            for condition in generator.ifs:
                self._visit_comprehension_expression(condition, bound_targets)
        if isinstance(node, ast.DictComp):
            self._visit_comprehension_expression(node.key, bound_targets)
            self._visit_comprehension_expression(node.value, bound_targets)
        else:
            self._visit_comprehension_expression(node.elt, bound_targets)

    def _visit_comprehension_expression(
        self, node: ast.AST, bound_targets: set[str]
    ) -> None:
        scope = FunctionNameResolver(
            globals_=self.globals,
            enclosing=self.captures,
            local=bound_targets,
            captures=self.captures,
            label=self.label,
            missing=self.missing,
        )
        scope.visit(node)


def analyze_function(
    function: ast.FunctionDef | ast.AsyncFunctionDef,
    *,
    globals_: set[str],
    enclosing: set[str],
    label: str,
    missing: set[str],
) -> None:
    local = bound_names([function.args, *function.body])
    visitor = FunctionNameResolver(
        globals_=globals_,
        enclosing=enclosing,
        local=local,
        captures=enclosing | local,
        label=label,
        missing=missing,
    )
    for statement in function.body:
        visitor.visit(statement)


def analyze_lambda(
    node: ast.Lambda,
    *,
    globals_: set[str],
    enclosing: set[str],
    label: str,
    missing: set[str],
) -> None:
    local = bound_names([node.args, node.body])
    visitor = FunctionNameResolver(
        globals_=globals_,
        enclosing=enclosing,
        local=local,
        captures=enclosing | local,
        label=label,
        missing=missing,
    )
    visitor.visit(node.body)


def unresolved_names_in_tree(tree: ast.Module, available: set[str]) -> set[str]:
    available = available | set(dir(builtins)) | {'__file__', '__name__'}
    missing: set[str] = set()
    for function in top_level_functions(tree):
        header_scope = FunctionNameResolver(
            globals_=available,
            enclosing=set(),
            local=set(),
            captures=set(),
            label=function.name,
            missing=missing,
        )
        header_scope._visit_function_header(function)
        analyze_function(
            function,
            globals_=available,
            enclosing=set(),
            label=function.name,
            missing=missing,
        )
    return missing


def unresolved_names(module: str) -> set[str]:
    return unresolved_names_in_tree(parse(module), module_namespace(module))


class ManualRunnerNameResolutionTests(unittest.TestCase):
    def test_every_function_body_name_resolves(self) -> None:
        for module in RUNNER_MODULES:
            with self.subTest(module=module):
                self.assertEqual(unresolved_names(module), set())

    def test_failure_handler_can_reach_cleanup(self) -> None:
        self.assertIn('cleanup_transient_framework_artifacts', module_namespace('dcoir_manual_runner_flow'))

    def test_nested_scope_bindings_do_not_hide_outer_missing_names(self) -> None:
        tree = ast.parse(
            'def outer():\n'
            '    def inner(missing):\n'
            '        missing = 1\n'
            '        return missing\n'
            '    return missing\n'
        )

        self.assertEqual(
            unresolved_names_in_tree(tree, set()),
            {'outer: missing'},
        )

    def test_comprehension_targets_do_not_bind_the_enclosing_function(self) -> None:
        tree = ast.parse(
            'def outer():\n'
            '    values = [missing for missing in (1,)]\n'
            '    return missing\n'
        )

        self.assertEqual(
            unresolved_names_in_tree(tree, set()),
            {'outer: missing'},
        )

    def test_comprehension_attribute_target_reads_are_checked(self) -> None:
        tree = ast.parse(
            'def outer():\n'
            '    return [0 for missing.attribute in (1,)]\n'
        )

        self.assertEqual(
            unresolved_names_in_tree(tree, set()),
            {'outer: missing'},
        )

    def test_comprehension_iterables_respect_target_binding_order(self) -> None:
        unsafe = ast.parse(
            'def outer():\n'
            '    return [x for x in (1,) for y in y]\n'
        )
        safe = ast.parse(
            'def outer():\n'
            '    return [y for x in (1,) for y in (x,)]\n'
        )

        self.assertEqual(unresolved_names_in_tree(unsafe, set()), {'outer: y'})
        self.assertEqual(unresolved_names_in_tree(safe, set()), set())

    def test_class_bindings_do_not_bind_the_enclosing_function(self) -> None:
        tree = ast.parse(
            'def outer():\n'
            '    class Inner:\n'
            '        missing = 1\n'
            '    return missing\n'
        )

        self.assertEqual(
            unresolved_names_in_tree(tree, set()),
            {'outer: missing'},
        )

    def test_class_bindings_do_not_leak_into_nested_class_or_comprehension_scopes(self) -> None:
        tree = ast.parse(
            'def outer():\n'
            '    class Outer:\n'
            '        local_only = 1\n'
            '        class Inner:\n'
            '            value = local_only\n'
            '        values = [local_only for _ in (1,)]\n'
        )

        self.assertEqual(
            unresolved_names_in_tree(tree, set()),
            {
                'outer.Outer.Inner: local_only',
                'outer.Outer: local_only',
            },
        )

    def test_nested_function_can_read_a_real_closure_binding(self) -> None:
        tree = ast.parse(
            'def outer():\n'
            '    captured = 1\n'
            '    def inner():\n'
            '        return captured\n'
            '    return inner()\n'
        )

        self.assertEqual(unresolved_names_in_tree(tree, set()), set())

    def test_function_definition_header_names_are_checked_in_module_scope(self) -> None:
        tree = ast.parse(
            'def outer(value=missing):\n'
            '    missing = 1\n'
            '    return value\n'
        )

        self.assertEqual(
            unresolved_names_in_tree(tree, set()),
            {'outer: missing'},
        )


if __name__ == '__main__':
    unittest.main()
