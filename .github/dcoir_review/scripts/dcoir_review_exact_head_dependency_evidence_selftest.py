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
from dcoir_review import semantic_context_runtime as runtime
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

    limited = build(FOCUS, DOC["safe_after_repair"]["head_content"], SAFE, fetch,
                    max_fetches=1)
    assert "direct-script-budget-exceeded" in limited["errors"]
    assert not limited["text"]
    print("PASS: two exact refs, bounded evidence and same-SHA cache; no live requests")
    print("PASS: path traversal, malformed refs, oversized source, missing fetch, prompt-cache invalidation")


if __name__ == "__main__":
    main()
