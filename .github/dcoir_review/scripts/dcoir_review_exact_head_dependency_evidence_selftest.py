#!/usr/bin/env python3
"""Adva/Prog offline tests for immutable source-backed per-file review evidence."""
from __future__ import annotations

import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from dcoir_review.exact_head_dependency_evidence import (
    MAX_EVIDENCE_CHARS,
    build_exact_head_dependency_evidence as build,
    enrich_first_pass_contexts,
    valid_source_path,
)
from dcoir_review.source_inventory_contract import (
    MAX_SOURCE_CHARS, _potential_pre_analyzer_guard, _logical_shell_commands,
)
from dcoir_review import semantic_context_runtime as runtime
from dcoir_review.unittest_source_guard import (
    fetch_verified_unittest_root_tree,
    _unittest_origin_verified,
)
import openrouter_pr_review_pareto_context as review

DOC = json.loads((HERE.parent / "evaluation" / "historical_pr617_cross_file_gap_v1.json").read_text(encoding="utf-8"))
BAD = DOC["historical_reference"]["reviewed_head"]
SAFE = DOC["safe_after_repair"]["commit"]
FOCUS = DOC["action"]["path"]
ROOT = "project_sources/collector/tools/run_powershell_analyzer.py"


def main() -> None:
    all_sources = {
        BAD: {**DOC["original_full_dependency_sources"], **{k: v["source"] for k, v in DOC["original_caller_graph_sources"].items()}},
        SAFE: {**DOC["safe_full_dependency_sources"], **{k: v["source"] for k, v in DOC["safe_caller_graph_sources"].items()}},
    }
    log: list[tuple[str, str]] = []

    def fetch(path: str, sha: str) -> str:
        log.append((sha, path))
        return all_sources[sha][path]

    # Copilot P1: locally executed -m analyzer is mandatory exact-HEAD code,
    # never silently accepted as an optional import or absent Python source.
    dotted = "project_sources.collector.tools.run_powershell_analyzer"
    module_cmd = "python -m " + dotted
    module_src = DOC["action"]["head_content"].replace(
        "python " + ROOT, module_cmd, 1,
    )
    assert module_src != DOC["action"]["head_content"]
    for invocation in (
        module_cmd, "python3.11 -m " + dotted,
        "py -3.11 -m " + dotted,
        "python -I -m " + dotted,
        'python -m "' + dotted + '"',
        "python -m" + dotted,
        'python "-m" ' + dotted,
        "python '-m' " + dotted,
    ):
        action = DOC["action"]["head_content"].replace("python " + ROOT, invocation, 1)
        proof = build(FOCUS, action, BAD, fetch)
        assert ROOT in proof["required_paths"] and ROOT in proof["paths"], (
            "python -m executable bypassed immutable source check", invocation, proof
        )
        assert proof["coverage_guard"] == "not-evidenced-in-action", (invocation, proof)
    # Copilot third P1 reproduction: pwsh's backtick continues one Python
    # invocation across two physical YAML run lines, not two commands.
    continued = "python " + chr(96) + "\n        -m " + dotted
    continued_bad = DOC["action"]["head_content"].replace(
        "python " + ROOT, continued, 1,
    )
    continued_evidence = build(FOCUS, continued_bad, BAD, fetch)
    assert ROOT in continued_evidence["required_paths"], (
        "pwsh continuation bypassed mandatory exact-head module source",
        continued_evidence,
    )
    assert ROOT in continued_evidence["paths"], continued_evidence
    assert continued_evidence["coverage_guard"] == "not-evidenced-in-action"
    # Doubled backticks are a literal backtick, not a continued command.
    assert len(_logical_shell_commands(
        "python " + chr(96) * 2 + "\n        -m " + dotted
    )) == 2
    assert len(_logical_shell_commands(continued)) == 1
    safe_continued = DOC["safe_after_repair"]["head_content"].replace(
        "python " + ROOT, continued, 1,
    )
    safe_continued_evidence = build(FOCUS, safe_continued, SAFE, fetch)
    assert ROOT in safe_continued_evidence["required_paths"]
    assert safe_continued_evidence["coverage_guard"] == "pre-analyzer-structural-check"
    # A preceding continued Python module may be an unseen guard: never
    # publish deterministic HIGH before proving it is not a safety preflight.
    assert _potential_pre_analyzer_guard([
        "        python " + chr(96),
        "          -m project_sources.collector.tools.unknown_precheck",
    ])
    assert _potential_pre_analyzer_guard(["        python " + chr(96)])
    assert not _potential_pre_analyzer_guard(["        $ErrorActionPreference = 'Stop'"])

    safe_module = DOC["safe_after_repair"]["head_content"].replace(
        "python " + ROOT, module_cmd, 1,
    )
    assert safe_module != DOC["safe_after_repair"]["head_content"]
    safe_module_proof = build(FOCUS, safe_module, SAFE, fetch)
    assert safe_module_proof["coverage_guard"] == "pre-analyzer-structural-check"
    for safe_invocation in (
        "python -m" + dotted,
        'python "-m" ' + dotted,
        "python '-m' " + dotted,
    ):
        safe_action = DOC["safe_after_repair"]["head_content"].replace(
            "python " + ROOT, safe_invocation, 1,
        )
        safe_evidence = build(FOCUS, safe_action, SAFE, fetch)
        assert ROOT in safe_evidence["required_paths"]
        assert safe_evidence["coverage_guard"] == "pre-analyzer-structural-check", (
            safe_invocation, safe_evidence
        )

    for unknown in (
        "python -m external.analyzer",
        "python -X utf8 -m " + dotted,
        "python -m $env:ANALYZER",
        "python " + chr(96) + "\n        -m $env:ANALYZER",
        "python " + chr(96) + "\n        $env:SCRIPT",
        "python " + chr(96) * 3 + "\n        -m " + dotted,
        "python -m" + dotted + "$env:SUFFIX",
        'python "-m" ' + dotted + "${SUFFIX}",
        'python "-m' + dotted + '"',
        "python -m ../secret",
        "python -m project_sources.collector.bad-name",
    ):
        action = DOC["action"]["head_content"].replace("python " + ROOT, unknown, 1)
        evidence = build(FOCUS, action, BAD, fetch)
        assert "unresolved-python-module-invocation" in evidence["errors"], (unknown, evidence)
        try:
            enrich_first_pass_contexts([
                {"path": FOCUS, "text": action, "item": {"filename": FOCUS}}
            ], BAD, fetch)
        except RuntimeError as exc:
            assert "exact-head executable dependency unavailable" in str(exc)
        else:
            raise AssertionError("unresolved direct module must fail closed: " + unknown)
    # Issue #636: named collector unittest discovery is a standard-library
    # test runner, not an unresolved repository analyzer executable.
    # Its exact static invocation must not abort review of a related workflow.
    collector_discovery = (
        "python -m unittest discover -s project_sources/collector/tools "
        "-p 'test_*.py'"
    )
    safe_root = {
        "commit_sha": BAD, "expected_tree_sha": SAFE,
        "sha": SAFE, "truncated": False,
        "tree": [
            {"path": ".github", "type": "tree"},
            {"path": "project_sources", "type": "tree"},
            {"path": "AGENTS.md", "type": "blob"},
        ],
    }
    def collector_workflow(module_command: str) -> str:
        return (
            "name: Collector source-coverage workflow\n"
            "jobs:\n  validate:\n    runs-on: windows-latest\n    steps:\n"
            "      - name: Run collector tool unit tests\n"
            "        shell: pwsh\n        run: |\n"
            f"          {module_command}\n"
            "          if ($LASTEXITCODE -ne 0) {\n"
            "            throw 'Collector tool unit tests failed.'\n"
            "          }\n"
            "      - name: Validate analyzer\n"
            "        shell: pwsh\n        run: |\n"
            f"          python {ROOT}\n"
        )

    for workflow_path in (
        ".github/workflows/reusable-validate-on-pr.yml",
        ".github/workflows/reusable-validate-on-push.yml",
    ):
        source = collector_workflow(collector_discovery)
        proof = build(workflow_path, source, BAD, fetch, root_tree=safe_root)
        assert not proof["errors"], (workflow_path, proof)
        assert ROOT in proof["required_paths"] and ROOT in proof["paths"], (
            workflow_path, proof
        )
        contexts = [{"path": workflow_path, "text": source,
                     "item": {"filename": workflow_path}}]
        assert enrich_first_pass_contexts(
            contexts, BAD, fetch, fetch_root_tree=lambda ref: safe_root
        ) == 1
        assert contexts[0]["item"].get("_dcoir_exact_head_dependency_evidence")

        # Adva negative controls: the narrow exception may not swallow
        # external/local unknown modules, shell chaining, dynamic paths,
        # unsafe interpreter switches, or malformed unittest invocations.
        hostile_commands = (
            "python -m unittest",
            "python -m unittest discover",
            "python -m unittest discover -s $env:TESTS -p 'test_*.py'",
            collector_discovery + " --unknown-option",
            collector_discovery + "; python -m external.analyzer",
            collector_discovery + " | python -m external.analyzer",
            collector_discovery + " && python -m external.analyzer",
            "python -X utf8 -m unittest discover -s "
            "project_sources/collector/tools -p 'test_*.py'",
            "python -m project_sources.collector.tools.unknown_test discover "
            "-s project_sources/collector/tools -p 'test_*.py'",
        )
        for hostile in hostile_commands:
            bad_source = source.replace(collector_discovery, hostile, 1)
            evidence = build(workflow_path, bad_source, BAD, fetch, root_tree=safe_root)
            # Unknown local modules are syntactically resolvable but must
            # still fail closed when exact-HEAD source cannot be fetched.
            if "project_sources.collector.tools.unknown_test" in hostile:
                missing = "project_sources/collector/tools/unknown_test.py"
                assert missing in evidence["required_paths"], evidence
                assert missing not in evidence["paths"], evidence
                expected_reason = "required-dependency-excerpt-unavailable"
            else:
                assert "unresolved-python-module-invocation" in evidence["errors"], (
                    workflow_path, hostile, evidence
                )
                expected_reason = "unresolved-python-module-invocation"
            try:
                enrich_first_pass_contexts([
                    {"path": workflow_path, "text": bad_source,
                     "item": {"filename": workflow_path}}
                ], BAD, fetch, fetch_root_tree=lambda ref: safe_root)
            except RuntimeError as exc:
                assert expected_reason in str(exc), (hostile, str(exc))
            else:
                raise AssertionError("unsafe module command was accepted: " + hostile)


        # Codex P1: a top-level repository module/package shadows stdlib
        # even when the command text matches the allowlist exactly.
        for shadow in ("unittest.py", "unittest", "UNITTEST.py",
                       "UnItTeSt", "unittest.pyc", "unittest.pyd",
                       "unittest.cpython-312-x86_64-linux-gnu.so"):
            shadow_root = {
                **safe_root,
                "tree": [*safe_root["tree"],
                         {"path": shadow, "type": "tree" if "." not in shadow else "blob"}],
            }
            bad = build(workflow_path, source, BAD, fetch, root_tree=shadow_root)
            assert "unresolved-python-module-invocation" in bad["errors"], (shadow, bad)
            try:
                enrich_first_pass_contexts(
                    [{"path": workflow_path, "text": source,
                      "item": {"filename": workflow_path}}],
                    BAD, fetch, fetch_root_tree=lambda ref: shadow_root,
                )
            except RuntimeError as exc:
                assert "unresolved-python-module-invocation" in str(exc)
            else:
                raise AssertionError("shadowing root was trusted: " + shadow)

        # Fail closed on absent, stale, truncated, incomplete, duplicate or
        # structurally invalid immutable root-tree API responses.
        invalid_trees = (
            None,
            {},
            {**safe_root, "sha": BAD},
            {**safe_root, "commit_sha": SAFE},
            {**safe_root, "expected_tree_sha": BAD},
            {**safe_root, "truncated": True},
            {**safe_root, "truncated": None},
            {**safe_root, "tree": []},
            {**safe_root, "tree": [{"path": ".github", "type": "tree"}]},
            {**safe_root, "tree": [
                {"path": ".github", "type": "tree"},
                {"path": "project_sources", "type": "blob"}]},
            {**safe_root, "tree": [
                *safe_root["tree"], {"path": ".github", "type": "tree"}]},
            {**safe_root, "tree": [
                *safe_root["tree"], {"path": "parent/unittest.py", "type": "blob"}]},
        )
        for bad_tree in invalid_trees:
            ev = build(workflow_path, source, BAD, fetch, root_tree=bad_tree)
            assert "unresolved-python-module-invocation" in ev["errors"], bad_tree
        assert "unresolved-python-module-invocation" in build(
            workflow_path, source, BAD, fetch
        )["errors"], "Missing tree proof must fail closed"
        try:
            enrich_first_pass_contexts(
                [{"path": workflow_path, "text": source,
                  "item": {"filename": workflow_path}}], BAD, fetch,
                fetch_root_tree=lambda ref: (_ for _ in ()).throw(OSError("API unavailable")),
            )
        except RuntimeError as exc:
            assert "unresolved-python-module-invocation" in str(exc)
        else:
            raise AssertionError("GitHub tree API failure was trusted")

        # Python import spelling is platform-sensitive. Exemption must be
        # case-sensitive even though the older parser looks for modules
        # without case restrictions.
        for hostile in (collector_discovery.replace("unittest", "UNITTEST"),
                        collector_discovery.replace("python", "Python")):
            case_ev = build(workflow_path,
                            source.replace(collector_discovery, hostile),
                            BAD, fetch, root_tree=safe_root)
            assert "unresolved-python-module-invocation" in case_ev["errors"], hostile

        # Codex second P1: no ambient path/cwd/alias state may shadow unittest.
        # These all still contain the exact discovery line and safe root tree.
        mutants = (
            source.replace(
                "      - name: Run collector tool unit tests",
                "      - name: Change path\n        shell: pwsh\n"
                "        run: |\n          Set-Location project_sources/collector/tools\n"
                "      - name: Run collector tool unit tests", 1),
            source.replace(
                "      - name: Run collector tool unit tests",
                "      - name: Change path\n        shell: pwsh\n"
                "        run: |\n"
                "          $env:PYTHONPATH = 'project_sources/collector/tools'\n"
                "      - name: Run collector tool unit tests", 1),
            source.replace(
                "      - name: Run collector tool unit tests",
                "      - name: Change path\n        shell: pwsh\n"
                "        run: |\n          $env:Path = 'project_sources/collector/tools'\n"
                "      - name: Run collector tool unit tests", 1),
            source.replace(
                "      - name: Run collector tool unit tests",
                "      - name: Change path\n        shell: pwsh\n"
                "        run: |\n          Set-Alias python attacker\n"
                "      - name: Run collector tool unit tests", 1),
            source.replace(
                "      - name: Run collector tool unit tests",
                "      - name: Change path\n        shell: pwsh\n"
                "        run: |\n          cd project_sources/collector/tools\n"
                "      - name: Run collector tool unit tests", 1),
            source.replace(
                "        shell: pwsh\n        run: |\n",
                "        working-directory: project_sources/collector/tools\n"
                "        shell: pwsh\n        run: |\n", 1),
            source.replace(
                "        shell: pwsh\n        run: |\n",
                "        env:\n          PYTHONPATH: project_sources/collector/tools\n"
                "        shell: pwsh\n        run: |\n", 1),
            source.replace(
                "      - name: Validate analyzer",
                "        env:\n          PATH: project_sources/collector/tools\n"
                "      - name: Validate analyzer", 1),
            source.replace(
                "    runs-on: windows-latest\n",
                "    runs-on: windows-latest\n"
                "    defaults:\n      run:\n        working-directory: project_sources/collector/tools\n", 1),
            source + "    env:\n      PYTHONPATH: project_sources/collector/tools\n",
            source.replace(
                "        run: |\n          " + collector_discovery,
                "        run: |\n          function python { Write-Output hacked }\n"
                "          " + collector_discovery, 1),
            source.replace(
                "        run: |\n          " + collector_discovery,
                "        run: |\n          Add-Content -Path $env:GITHUB_PATH -Value 'bad'\n"
                "          " + collector_discovery, 1),
        )
        for mutant in mutants:
            result = build(workflow_path, mutant, BAD, fetch, root_tree=safe_root)
            assert "unresolved-python-module-invocation" in result["errors"], (
                workflow_path, mutant, result
            )
            try:
                enrich_first_pass_contexts([
                    {"path": workflow_path, "text": mutant,
                     "item": {"filename": workflow_path}}
                ], BAD, fetch, fetch_root_tree=lambda ref: safe_root)
            except RuntimeError as exc:
                assert "unresolved-python-module-invocation" in str(exc)
            else:
                raise AssertionError("import-path altered runner accepted")

    # Only one immutable GitHub tree fetch for multiple matching contexts.
    contexts = []
    for name in ("reusable-validate-on-pr.yml", "reusable-validate-on-push.yml"):
        path = ".github/workflows/" + name
        contexts.append({
            "path": path,
            "text": collector_workflow(collector_discovery),
            "item": {"filename": path},
        })
    root_fetches = []
    def fetch_root_once(ref):
        root_fetches.append(ref)
        return safe_root
    assert enrich_first_pass_contexts(
        contexts, BAD, fetch, fetch_root_tree=fetch_root_once
    ) == 2
    assert root_fetches == [BAD], root_fetches

    # Codex P1: commit SHA and Git tree SHA are distinct. The caller must
    # resolve the commit object, query its exact tree hash, and cross-check.
    class HeadGitHub:
        repo = "example/repo"
        def __init__(self, commit=None, tree=None):
            self.requests = []
            self.commit = commit if commit is not None else {
                "sha": BAD, "tree": {"sha": SAFE}}
            self.tree = tree if tree is not None else {
                "sha": SAFE, "truncated": False,
                "tree": list(safe_root["tree"])}
        def request(self, method, path):
            self.requests.append((method, path))
            if path.endswith("/git/commits/" + BAD):
                return self.commit
            if path.endswith("/git/trees/" + SAFE):
                return self.tree
            raise AssertionError("Unexpected GitHub path: " + path)

    good_api = HeadGitHub()
    verified = fetch_verified_unittest_root_tree(good_api, BAD)
    assert verified == safe_root, (verified, safe_root)
    assert _unittest_origin_verified(verified, BAD)
    assert good_api.requests == [
        ("GET", "/repos/example/repo/git/commits/" + BAD),
        ("GET", "/repos/example/repo/git/trees/" + SAFE),
    ], good_api.requests
    for bad_api in (
        HeadGitHub(commit={"sha": SAFE, "tree": {"sha": SAFE}}),
        HeadGitHub(commit={"sha": BAD, "tree": {}}),
        HeadGitHub(commit={"sha": BAD, "tree": {"sha": "not-a-sha"}}),
        HeadGitHub(tree={"sha": BAD, "truncated": False,
                         "tree": safe_root["tree"]}),
        HeadGitHub(tree={"sha": SAFE, "truncated": True,
                         "tree": safe_root["tree"]}),
    ):
        checked = fetch_verified_unittest_root_tree(bad_api, BAD)
        assert not _unittest_origin_verified(checked, BAD), (bad_api.requests, checked)

    unknown_local = "project_sources.collector.tools.no_such_analyzer"
    absent = build(FOCUS, "python -m " + unknown_local, BAD, fetch)
    assert "project_sources/collector/tools/no_such_analyzer.py" in absent["required_paths"]
    assert not absent["paths"], "missing module source was treated as verified"
    assert build(".github/workflows/simple-check.yml", "python -m external.analyzer", BAD, fetch)["errors"] == []

    # Mixed script/module actions must require both executable sources, not
    # silently skip an added -m module behind the preferred direct analyzer.
    hidden_module = "project_sources.collector.tools.hidden_analyzer"
    mixed_source = DOC["action"]["head_content"].replace(
        "python " + ROOT,
        "python -m " + hidden_module + "\n        python " + ROOT, 1,
    )
    missing_source = "project_sources/collector/tools/hidden_analyzer.py"
    mixed = build(FOCUS, mixed_source, BAD, fetch)
    assert ROOT in mixed["required_paths"] and missing_source in mixed["required_paths"]
    assert missing_source not in mixed["paths"]
    try:
        enrich_first_pass_contexts([
            {"path": FOCUS, "text": mixed_source, "item": {"filename": FOCUS}}
        ], BAD, fetch)
    except RuntimeError as exc:
        assert "exact-head executable dependency unavailable" in str(exc)
    else:
        raise AssertionError("mixed direct/module action skipped a mandatory -m source")

    known_module = "project_sources.collector.tools.powershell_analyzer_cli"
    known_mix = DOC["action"]["head_content"].replace(
        "python " + ROOT,
        "python -m " + known_module + "\n        python " + ROOT, 1,
    )
    known_proof = build(FOCUS, known_mix, BAD, fetch)
    assert "project_sources/collector/tools/powershell_analyzer_cli.py" in known_proof["required_paths"]
    assert "project_sources/collector/tools/powershell_analyzer_cli.py" in known_proof["paths"]

    # Copilot fourth P1: input accepted by GitHub can exceed the parser's
    # strict size bound. A relevant action must fail closed, not look clean.
    original = DOC["action"]["head_content"]
    oversized_prefix = "#" + ("x" * 140_000) + "\n"
    assert len(oversized_prefix) > MAX_SOURCE_CHARS
    for reviewed_head, action in (
        (BAD, original),
        (SAFE, DOC["safe_after_repair"]["head_content"]),
    ):
        big = oversized_prefix + action  # executable occurs beyond parse limit
        assert "python " + ROOT in big[MAX_SOURCE_CHARS:]
        log.clear()
        proof = build(FOCUS, big, reviewed_head, fetch)
        assert "oversized-source-coverage-action" in proof["errors"], proof
        assert not log, "oversized action should abort before dependency reads"
        try:
            enrich_first_pass_contexts([
                {"path": FOCUS, "text": big, "item": {"filename": FOCUS}}
            ], reviewed_head, fetch)
        except RuntimeError as exc:
            assert "exact-head executable dependency unavailable" in str(exc)
        else:
            raise AssertionError("oversized relevant action must fail closed")
    # At the exact character limit the complete command remains parseable.
    border = "#" + "x" * (MAX_SOURCE_CHARS - len(original) - 2) + "\n" + original
    assert len(border) == MAX_SOURCE_CHARS
    assert ROOT in build(FOCUS, border, BAD, fetch)["required_paths"]
    # An otherwise ordinary action can hide the security-relevant command
    # AFTER the parse limit. Scan relevance across full fetched source, then
    # fail closed rather than trusting the truncated prefix.
    hidden = build(".github/actions/custom-check/action.yml", oversized_prefix + original, BAD, fetch)
    assert "oversized-source-coverage-action" in hidden["errors"]
    # Ordinary unrelated workflows retain their existing opt-out behavior.
    unrelated = build(".github/workflows/simple-check.yml", oversized_prefix, BAD, fetch)
    assert not unrelated["errors"]

    log.clear()
    first = build(FOCUS, DOC["action"]["head_content"], BAD, fetch)
    assert first["paths"] and ROOT in first["paths"]
    assert not first["errors"], first["errors"]
    assert len(first["text"]) <= MAX_EVIDENCE_CHARS
    assert all(ref == BAD for ref, _ in log)
    assert 'inventory = load_inventory(repo_root, inventory_path)' in first["text"]
    assert 'for surface in inventory' in first["text"]
    assert "powershell_analyzer_cli.py" in first["text"]
    assert "for surface in inventory" in first["text"]

    safe = build(FOCUS, DOC["safe_after_repair"]["head_content"], SAFE, fetch)
    assert safe["paths"] and ROOT in safe["paths"]
    assert all(ref in {SAFE, BAD} for ref, _ in log)
    assert "verify_powershell_surface_inventory_ci.py" in DOC["safe_after_repair"]["head_content"]
    assert safe["text"] != first["text"]

    item = {"filename": FOCUS, "status": "modified", "patch": DOC["action"]["patch"]}
    before = {"path": FOCUS, "text": DOC["action"]["head_content"], "item": dict(item)}
    contexts = [before, {"path": FOCUS, "text": DOC["action"]["head_content"], "item": dict(item)}]
    log.clear()
    assert enrich_first_pass_contexts(contexts, BAD, fetch) == 2
    assert len(log) <= 10, log
    assert contexts[0]["item"].get("_dcoir_source_inventory_candidate", {}).get("line") == 36
    assert contexts[0]["item"]["_dcoir_exact_head_dependency_paths"]
    assert contexts[0]["item"]["_dcoir_exact_head_dependency_evidence"] == first["text"]
    assert contexts[0]["item"]["_dcoir_source_coverage_guard"] == "not-evidenced-in-action"

    config = review.load_pareto_context_config(str(HERE.parent / "openrouter-pr-review-pareto.yml"))
    params = ({"number": 617, "title": "Historical regression"}, contexts[0]["item"],
              DOC["action"]["head_content"], DOC["action"]["patch"], config, [], "first-pass-deep")
    enriched_prompt = review.build_per_file_review_prompt(*params)
    vanilla_prompt = review.build_per_file_review_prompt(
        params[0], item, params[2], params[3], params[4], params[5], params[6]
    )
    assert "Exact-reviewed-head dependency evidence" in enriched_prompt
    assert "Exact-reviewed-head dependency evidence" not in vanilla_prompt
    assert "inventory = load_inventory" in enriched_prompt
    assert len(enriched_prompt) <= config.max_prompt_chars
    k1 = runtime.per_file_prompt_key(review, *params)
    k2 = runtime.per_file_prompt_key(
        review, params[0], item, params[2], params[3], params[4], params[5], params[6]
    )
    assert k1 != k2, "semantic prompt cache failed to bind source evidence"

    invalid = [
        "../secret.py", ".github/../secret.py", ".github//bad.py", "https://host/a.py",
        "C:/evil.py", ".github\\a.py", "project_sources\\code.py", "/absolute/a.py",
        ".github/scripts/a.txt", ".github/scripts/b.py\ninject", ".github/scripts/./a.py",
    ]
    assert all(not valid_source_path(path) for path in invalid)
    count = len(log)
    for sha in ("main", "deadbeef", BAD + "0", BAD.upper()):
        assert build(FOCUS, DOC["action"]["head_content"], sha, fetch)["text"] == ""
    assert len(log) == count
    injection = "python ../secret.py\npython project_sources/../../secret.py"
    assert build(FOCUS, injection, BAD, fetch)["text"] == ""
    assert len(log) == count
    hostile = "python project_sources/collector/tools/run_powershell_analyzer.py"
    def huge(path: str, sha: str) -> str:
        assert path == ROOT and sha == BAD
        return "X" * 120001
    denied = build(FOCUS, hostile, BAD, huge)
    assert denied["errors"] == [ROOT]
    assert "unavailable" in denied["text"]
    assert denied["paths"] == []
    try:
        enrich_first_pass_contexts([
            {"path": FOCUS, "text": hostile, "item": {"filename": FOCUS}}
        ], BAD, huge)
    except RuntimeError as exc:
        assert "exact-head executable dependency unavailable" in str(exc)
    else:
        raise AssertionError("Missing directly invoked source must block clean review")
    assert build(FOCUS, hostile, BAD, fetch, max_chars=100)["text"] == ""
    assert build(FOCUS, hostile, BAD, fetch, max_fetches=0)["text"] == ""
    assert build("docs/readme.md", hostile, BAD, fetch)["text"] == ""

    # No direct script, malformed import, or injected comments may create
    # filesystem access or arbitrary GitHub references.
    assert build("project_sources/collector/tools/example.py",
                 "from .. import secret\n", BAD, fetch)["text"] == ""
    assert build(FOCUS, "# python ../secret.py", BAD, fetch)["text"] == ""
    def unwanted_fetch(path: str, sha: str) -> str:
        raise AssertionError("Unrelated YAML review should not fetch dependencies")
    unrelated_action = ".github/workflows/simple-check.yml"
    benign_command = "python project_sources/collector/tools/simple_tool.py"
    assert build(unrelated_action, benign_command, BAD, unwanted_fetch)["text"] == ""
    # P1 regression: an ordinary non-verifier helper is not selected for
    # source evidence; its presence must not abort the entire review.
    extra = "project_sources/collector/tools/check_environment.py"
    extra_action = DOC["action"]["head_content"].replace(
        "        python project_sources/collector/tools/run_powershell_analyzer.py",
        f"        python {extra} --probe\n"
        "        python project_sources/collector/tools/run_powershell_analyzer.py", 1,
    )
    probe = {"path": FOCUS, "text": extra_action,
             "item": {"filename": FOCUS, "patch": DOC["action"]["patch"]}}
    assert enrich_first_pass_contexts([probe], BAD, fetch, max_files=1) == 1
    assert extra in build(FOCUS, extra_action, BAD, fetch)["direct_paths"]
    assert extra not in probe["item"]["_dcoir_exact_head_dependency_paths"]
    assert "_dcoir_source_inventory_candidate" not in probe["item"]
    # Adva: optional inventory/manifest/policy helpers may outrank a generic
    # analyzer by name, but must never displace the actual analyzer root.
    for helper_name in ("inventory_probe.py", "manifest_probe.py", "policy_probe.py"):
        priority_helper = f"project_sources/collector/tools/{helper_name}"
        priority_action = DOC["action"]["head_content"].replace(
            "        python project_sources/collector/tools/run_powershell_analyzer.py",
            f"        python {priority_helper} --check\n"
            "        python project_sources/collector/tools/run_powershell_analyzer.py", 1,
        )
        root_evidence = build(FOCUS, priority_action, BAD, fetch)
        assert ROOT in root_evidence["required_paths"], root_evidence
        assert priority_helper not in root_evidence["required_paths"], root_evidence
        priority_context = {"path": FOCUS, "text": priority_action,
                            "item": {"filename": FOCUS, "patch": DOC["action"]["patch"]}}
        assert enrich_first_pass_contexts([priority_context], BAD, fetch, max_files=1) == 1
        assert "_dcoir_source_inventory_candidate" not in priority_context["item"]
    # Selected verifier scripts still fail closed if their HEAD source is
    # unavailable; excluding benign helpers must not weaken that protection.
    verifier = "project_sources/collector/tools/verify_missing_contract.py"
    guarded = DOC["action"]["head_content"].replace(
        "        python project_sources/collector/tools/run_powershell_analyzer.py",
        f"        python {verifier}\n"
        "        python project_sources/collector/tools/run_powershell_analyzer.py", 1,
    )
    try:
        enrich_first_pass_contexts([
            {"path": FOCUS, "text": guarded, "item": dict(item)}
        ], BAD, fetch, max_files=1)
    except RuntimeError as exc:
        assert "exact-head executable dependency unavailable" in str(exc)
    else:
        raise AssertionError("Unfetched selected verifier must fail closed")

    # A Python test/import dependency is optional context, not an executable
    # explicitly required by an action. A readable but uninteresting sibling
    # must not abort review of an entire many-file pull request.
    optional_focus = "project_sources/collector/tools/test_run_powershell_analyzer_core.py"
    optional_source = "from powershell_analyzer_execution import run\n"
    optional_dep = "project_sources/collector/tools/powershell_analyzer_execution.py"
    optional_reads: list[tuple[str, str]] = []
    def optional_fetch(path: str, sha: str) -> str:
        optional_reads.append((sha, path))
        assert (sha, path) == (BAD, optional_dep)
        return "def run():\n    return 42\n"  # valid source, no matching excerpt
    optional = build(optional_focus, optional_source, BAD, optional_fetch)
    assert optional["required_paths"] == [], optional
    assert optional_dep in optional["attempted"], optional
    assert not optional["paths"] and "no-bounded-source-evidence" in optional["errors"]
    optional_context = {
        "path": optional_focus, "text": optional_source,
        "item": {"filename": optional_focus,
                 "patch": "@@ -0,0 +1,1 @@\n+from powershell_analyzer_execution import run\n"},
    }
    assert enrich_first_pass_contexts([optional_context], BAD, optional_fetch) == 0
    assert "_dcoir_exact_head_dependency_evidence" not in optional_context["item"]
    # In contrast, an action-executed analyzer remains mandatory even when
    # its content has no excerptable contract lines.
    no_excerpt = lambda path, sha: "def main():\n    return 42\n"
    required = build(FOCUS, "python " + ROOT, BAD, no_excerpt)
    assert required["required_paths"] == [ROOT], required
    try:
        enrich_first_pass_contexts([
            {"path": FOCUS, "text": "python " + ROOT,
             "item": {"filename": FOCUS, "patch": DOC["action"]["patch"]}}
        ], BAD, no_excerpt)
    except RuntimeError:
        pass
    else:
        raise AssertionError("Directly executed action source must fail closed")
    # Full PR617 regression: the high-risk action was 23rd among changed
    # contexts. It must be enriched even when six eligible ordinary imports
    # appear first, without widening the six-context dependency budget.
    many_contexts = []
    for index in range(8):
        name = f"project_sources/collector/tools/test_powershell_analyzer_mock_{index}.py"
        snippet = "from powershell_analyzer_cli import load_inventory\n"
        many_contexts.append({
            "path": name, "text": snippet,
            "item": {"filename": name,
                     "patch": "@@ -0,0 +1,1 @@\n+from powershell_analyzer_cli import load_inventory\n"},
        })
    many_contexts.append({
        "path": FOCUS, "text": DOC["action"]["head_content"],
        "item": {"filename": FOCUS, "status": "modified", "patch": DOC["action"]["patch"]},
    })
    enriched = enrich_first_pass_contexts(many_contexts, BAD, fetch, max_files=6)
    assert 0 < enriched <= 6, enriched
    assert many_contexts[-1]["item"].get(
        "_dcoir_source_inventory_candidate", {}
    ).get("line") == 36, "a high-risk changed action was starved behind other contexts"
    assert sum("_dcoir_exact_head_dependency_evidence" in ctx["item"]
               for ctx in many_contexts) <= 6
    limited = build(FOCUS, DOC["safe_after_repair"]["head_content"], SAFE, fetch,
                    max_fetches=1)
    assert "direct-script-budget-exceeded" in limited["errors"]
    assert not limited["text"]
    print("PASS: two exact refs, bounded evidence and same-SHA cache; no live requests")
    print("PASS: path traversal, malformed refs, oversized source, missing fetch, prompt-cache invalidation")


if __name__ == "__main__":
    main()
