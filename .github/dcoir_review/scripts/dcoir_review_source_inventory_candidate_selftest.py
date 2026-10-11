#!/usr/bin/env python3
"""Offline Prog/Adva tests for source-backed coverage candidate generation."""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import dcoir_review_historical_recall_cases as h
from dcoir_review.exact_head_dependency_evidence import build_exact_head_dependency_evidence
from dcoir_review.source_inventory_candidate import (
    detect_inventory_coverage_candidate as detect,
)

DATA = json.loads((HERE.parent / "evaluation/historical_pr617_cross_file_gap_v1.json").read_text(encoding="utf-8"))


def arguments(case: dict, label: str) -> dict:
    stored = DATA[label + "_caller_graph_sources"]
    callers = {name: record["source"] for name, record in stored.items()}
    for name, record in stored.items():
        assert hashlib.sha256(record["source"].encode()).hexdigest() == record["sha256"], name
    evidence = build_exact_head_dependency_evidence(
        case["focus_path"], case["focus_source"], case["reviewed_head"],
        lambda path, ref: case["dependency_sources"][path],
    )
    assert not evidence["errors"] and evidence["coverage_guard"] != "not-applicable"
    return {
        "focus_path":case["focus_path"],
        "head_source":case["focus_source"],
        "patch":case["changed_diff"].split("\ndiff --git ",1)[0],
        "reviewed_head":case["reviewed_head"],
        "dependencies":case["dependency_sources"],
        "caller_sources":callers,
        "action_guard_status":evidence["coverage_guard"],
    }


def main() -> None:
    positive, safe = h.cases()
    args = arguments(positive, "original")
    good = detect(**args)
    assert isinstance(good, dict), "Known historical missed P1 not detected"
    assert good["path"] == positive["focus_path"] and good["line"] == 36
    assert good["severity"] == "high"
    assert good["_dcoir_candidate_state"] == "source-backed-pending-independent-verification"
    assert set(good["_dcoir_evidence"]["paths"]) == set(good["_dcoir_evidence"]["hashes"])
    assert len(good["_dcoir_evidence"]["paths"]) == 9
    assert h.BAD_SHA == good["_dcoir_evidence"]["reviewed_head"]
    from dcoir_review.source_inventory_candidate import pending_source_inventory_candidate_count
    assert pending_source_inventory_candidate_count([good], []) == 1
    assert pending_source_inventory_candidate_count([good], [{"path":good["path"],"line":36,
            "severity":"low","title":"Inventory nit","body":"tracked PowerShell omitted"}]) == 1
    assert pending_source_inventory_candidate_count([good], [{"path":good["path"],"line":36,
            "severity":"high","title":"Style","body":None}]) == 1
    assert pending_source_inventory_candidate_count([good], [{"path":good["path"],"line":36,
            "severity":"high","title":"Inventory target coverage",
            "body":"New Git-tracked source omitted from scan"}]) == 0
    assert "newly Git-tracked PowerShell file" in good["body"]
    assert "Check for any additional effective upstream gate" in good["body"]
    assert detect(**arguments(safe, "safe")) is None

    mutations = []
    def alter(**updates: object) -> dict:
        v = dict(args)
        v.update(updates)
        return v

    mutations.extend([
        alter(reviewed_head="main"),
        alter(reviewed_head=h.BAD_SHA.upper()),
        alter(action_guard_status="pre-analyzer-structural-check"),
        alter(focus_path=".github/actions/../../secret/action.yml"),
        alter(patch=""),
        alter(patch=args["patch"].replace("run_powershell_analyzer.py",
                                           "run_different_analyzer.py")),
        alter(head_source=args["head_source"].replace(
            "python project_sources/collector/tools/run_powershell_analyzer.py",
            "python project_sources/collector/tools/new_analyzer.py")),
        alter(dependencies={}),
        alter(caller_sources={}),
    ])
    # Changed RIGHT-side anchor must remain at the *actual* source line.
    mutations.append(alter(patch=args["patch"].replace("+        python", "+    python")))
    # One caller removed, one protected by an independently invoked checker,
    # duplicate caller uses, or modified/missing required-surfaces checker.
    for name in (
        ".github/workflows/reusable-validate-on-pr.yml",
        ".github/workflows/reusable-validate-on-push.yml",
    ):
        sources=dict(args["caller_sources"])
        sources.pop(name)
        mutations.append(alter(caller_sources=sources))
        sources=dict(args["caller_sources"])
        sources[name] = sources[name].replace(
            "        uses: ./.github/actions/run-psscriptanalyzer",
            "        run: python project_sources/collector/tools/verify_powershell_surface_inventory_ci.py\n"
            "        uses: ./.github/actions/run-psscriptanalyzer",
        )
        mutations.append(alter(caller_sources=sources))
        sources=dict(args["caller_sources"])
        sources[name] += "\n        uses: ./.github/actions/run-psscriptanalyzer\n"
        mutations.append(alter(caller_sources=sources))
    sources=dict(args["caller_sources"])
    sources[".github/github_actions/tools/check_required_surfaces.py"] = (
        "def policy(repo):\n"
        "    return build_inventory(repo) == git_tracked_files(repo)\n"
    )
    mutations.append(alter(caller_sources=sources))
    sources=dict(args["caller_sources"])
    sources[".github/actions/verify-required-surfaces/action.yml"] = ""
    mutations.append(alter(caller_sources=sources))
    sources=dict(args["caller_sources"])
    sources.pop(".github/workflows/validate-on-pr.yml")
    mutations.append(alter(caller_sources=sources))
    sources=dict(args["caller_sources"])
    sources[".github/workflows/validate-on-pr.yml"] = "# disconnected PR workflow"
    mutations.append(alter(caller_sources=sources))
    sources=dict(args["caller_sources"])
    sources[".github/github_actions/tools/check_required_surfaces.py"] += (
        "\nimport subprocess\n"
        "def check_all(repo): return subprocess.run(['git','ls-files','-z'])\n"
    )
    mutations.append(alter(caller_sources=sources))
    sources=dict(args["caller_sources"])
    name=".github/workflows/reusable-validate-on-pr.yml"
    sources[name] = sources[name].replace(
        "        uses: ./.github/actions/run-psscriptanalyzer",
        "      - name: Verify PowerShell inventory\n"
        "        uses: ./.github/actions/verify-inventory\n"
        "      - name: Run scanner\n"
        "        uses: ./.github/actions/run-psscriptanalyzer",
    )
    mutations.append(alter(caller_sources=sources))
    scripts=dict(args["dependencies"])
    scripts["project_sources/collector/tools/powershell_analyzer_cli.py"] = (
        "# inventory = load_inventory(repo_root, path)\n"
        "inventory = {'surfaces': []}\n"
    )
    mutations.append(alter(dependencies=scripts))
    scripts=dict(args["dependencies"])
    scripts["project_sources/collector/tools/powershell_analyzer_inventory.py"] = (
        '# for surface in inventory["surfaces"]\n'
        "for surface in tracked_paths:\n    pass\n"
    )
    mutations.append(alter(dependencies=scripts))
    assert all(detect(**variant) is None for variant in mutations), [
        index for index, case in enumerate(mutations) if detect(**case) is not None
    ]

    # Distinguish logical action contract from fixture-specific action name.
    other=copy.deepcopy(args)
    other["focus_path"] = other["focus_path"].replace("run-psscriptanalyzer", "run-new-scanner")
    other["caller_sources"] = {
        k:v.replace("run-psscriptanalyzer", "run-new-scanner")
        for k,v in other["caller_sources"].items()
    }
    other["patch"] = other["patch"].replace("run-psscriptanalyzer", "run-new-scanner")
    assert detect(**other) is not None

    # Production integration uses the same immutable GitHub fetch callback as
    # the source evidence helper. No provider/model/remote network calls.
    from dcoir_review.exact_head_dependency_evidence import enrich_first_pass_contexts
    for case, expected_candidate, expected_fetches in (
        (positive, True, 10), (safe, False, 4),
    ):
        sources={**case["dependency_sources"], **case["caller_sources"]}
        fetched=[]
        def frozen(path: str, head: str) -> str:
            assert head == case["reviewed_head"]
            fetched.append(path)
            return sources[path]
        context={
            "path":case["focus_path"],
            "text":case["focus_source"],
            "item":{
                "filename":case["focus_path"],
                "patch":case["changed_diff"].split("\n" + "diff --git ", 1)[0],
            }
        }
        count = enrich_first_pass_contexts([context], case["reviewed_head"], frozen, max_files=1)
        assert count == 1
        candidate=context["item"].get("_dcoir_source_inventory_candidate")
        assert bool(candidate) is expected_candidate
        if candidate:
            assert candidate["path"] == case["focus_path"]
            assert candidate["line"] == 36
        assert len(fetched) == expected_fetches, (case["id"], fetched)
        assert "findings" not in context["item"], "Advisory candidates must not publish as model findings"

    # Caller retrieval failure must suppress any candidate rather than
    # speculatively treating the missing file as an absent safety gate.
    missing={**positive["dependency_sources"], **positive["caller_sources"]}
    missing.pop(".github/workflows/reusable-validate-on-push.yml")
    failed_context={
        "path":positive["focus_path"], "text":positive["focus_source"],
        "item":{"filename":positive["focus_path"],
                "patch":positive["changed_diff"].split("\n" + "diff --git ", 1)[0]},
    }
    assert enrich_first_pass_contexts([failed_context], positive["reviewed_head"],
                                      lambda path, _head: missing[path],max_files=1)==1
    assert "_dcoir_source_inventory_candidate" not in failed_context["item"]

    print("PASS historic positive/safe production enrichment; advisory-only, no auto-publication")
    print("PASS strict caller graph read-failure suppression and reviewed-HEAD fetch budget")
    print("PASS historical PR617 source-backed HIGH review candidate at original line 36")
    print("PASS repaired-safe opposite polarity, missing guards, changed anchors, fake AST evidence")
    print(f"PASS {len(mutations)} adverse mutations; second scanner action name still detected")
    print("NOTE candidate is advisory and requires independent verification; no automatic GitHub finding")


if __name__ == "__main__":
    main()
