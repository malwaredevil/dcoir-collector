#!/usr/bin/env python3
"""Offline exact-Git-source replay for historical PR617's second P1.

No network, provider, model, review bot, or production file modification.
The second P1 was independently reported; DCOIR Review never saw its bad SHA.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import types
from pathlib import Path
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(REPO / "project_sources/collector/tools"))
from dcoir_review.exact_head_dependency_evidence import (
    MAX_EVIDENCE_CHARS,
    build_exact_head_dependency_evidence as build,
    enrich_first_pass_contexts,
)
from dcoir_review.source_inventory_contract import _git_freshness_comparator
import openrouter_pr_review_pareto_context as review
from powershell_surface_inventory_outputs import build_inventory
from powershell_surface_inventory_test_cases.common import InventoryTestCase, write

FIXTURE = HERE.parent / "evaluation/historical_pr617_git_fallback_p1_v1.json"
DATA = json.loads(FIXTURE.read_text(encoding="utf-8"))
BAD = "959e916a6671c9d89e25842f4a170b917ad08b93"
SAFE = "13ef93fe52851a5800bcdf6714733abecc1ce76a"
ACTION = ".github/actions/run-psscriptanalyzer/action.yml"
VERIFIER = "project_sources/collector/tools/verify_powershell_surface_inventory_ci.py"


def digest(source: str) -> str:
    return hashlib.sha256(source.encode("utf-8")).hexdigest()


def offline_verify(source: str):
    # Historical committed Python, embedded verbatim and hash-pinned.
    mod = types.ModuleType("historical_inventory_verifier")
    mod.__file__ = "<pinned PR617 Git source>"
    exec(compile(source, mod.__file__, "exec"), mod.__dict__)
    return mod.verify_inventory


def historical_sources(ref: str) -> dict[str, str]:
    sources = dict(DATA["shared_dependency_sources"])
    sources[VERIFIER] = (DATA["historical_bad_verifier"] if ref == BAD
                         else DATA["repaired_safe_verifier"])
    return sources


def main() -> None:
    assert DATA["schema_version"] == "dcoir_historical_git_fallback_p1_v1"
    assert DATA["bad_sha"] == BAD and DATA["repaired_sha"] == SAFE
    assert DATA["focus_action"] == ACTION and DATA["verifier_path"] == VERIFIER
    assert DATA["historical_pr"] == 617
    assert "did not run" in DATA["historical_reviewer_boundary"]
    assert digest((REPO / DATA["discovery_path"]).read_text(encoding="utf-8")) == DATA["discovery_sha256"]
    for path, source in DATA["shared_dependency_sources"].items():
        assert digest(source) == DATA["shared_dependency_sha256"][path]
    assert digest(DATA["historical_bad_verifier"]) == DATA["bad_verifier_sha256"]
    assert digest(DATA["repaired_safe_verifier"]) == DATA["safe_verifier_sha256"]
    assert digest(DATA["verifier_repair_patch"]) == DATA["verifier_repair_patch_sha256"]
    assert digest(DATA["historical_action_patch"]) == DATA["historical_action_patch_sha256"]
    assert "+        if current.get('source_of_truth') != 'git ls-files -z':" in DATA["verifier_repair_patch"]

    bad, safe = (offline_verify(DATA["historical_bad_verifier"]),
                 offline_verify(DATA["repaired_safe_verifier"]))
    assert not _git_freshness_comparator(DATA["historical_bad_verifier"])
    assert _git_freshness_comparator(DATA["repaired_safe_verifier"])

    # Genuine new tracked source absent in the working tree. A filesystem
    # fallback can falsely match the checked-in inventory and report success.
    with InventoryTestCase().make_minimal_repo() as temporary:
        root = Path(temporary)
        subprocess.run(["git", "init", "-q", str(root)], check=True, capture_output=True)
        subprocess.run(["git", "-C", str(root), "add", "-A"],
                       check=True, capture_output=True)
        inventory = root / "inventory.json"
        original = build_inventory(root)
        assert original["source_of_truth"] == "git ls-files -z"
        inventory.write_text(json.dumps(original), encoding="utf-8")
        observed = {
            "healthy_bad": bad(root, Path("inventory.json")),
            "healthy_safe": safe(root, Path("inventory.json")),
        }
        missing = ".github/scripts/index_only_bad.ps1"
        write(root / missing, "Invoke-Expression $untrusted\n")
        subprocess.run(["git", "-C", str(root), "add", missing],
                       check=True, capture_output=True)
        (root / missing).unlink()
        observed["missing_bad"] = bad(root, Path("inventory.json"))
        observed["missing_safe"] = safe(root, Path("inventory.json"))
        with patch("powershell_surface_inventory_discovery.subprocess.run",
                   side_effect=OSError("simulated missing Git executable")):
            fallback = build_inventory(root)
            assert fallback["source_of_truth"] == "filesystem recursive scan fallback"
            assert fallback["surfaces"] == original["surfaces"]
            observed["oserror_bad"] = bad(root, Path("inventory.json"))
            observed["oserror_safe"] = safe(root, Path("inventory.json"))
        failed = subprocess.CompletedProcess(
            args=["git"], returncode=128, stdout=b"", stderr=b"simulated failure"
        )
        with patch("powershell_surface_inventory_discovery.subprocess.run",
                   return_value=failed):
            observed["nonzero_bad"] = bad(root, Path("inventory.json"))
            observed["nonzero_safe"] = safe(root, Path("inventory.json"))
    assert observed == {
        "healthy_bad": 0, "healthy_safe": 0, "missing_bad": 1, "missing_safe": 1,
        "oserror_bad": 0, "oserror_safe": 1,
        "nonzero_bad": 0, "nonzero_safe": 1,
    }, observed

    for ref, expected_guard in ((BAD, "not-evidenced-in-action"),
                                (SAFE, "pre-analyzer-structural-check")):
        sources = historical_sources(ref)
        fetches: list[tuple[str, str]] = []
        def fetch(path: str, sha: str) -> str:
            assert sha == ref and path in sources
            fetches.append((sha, path))
            return sources[path]
        proof = build(ACTION, sources[ACTION], ref, fetch)
        assert proof["coverage_guard"] == expected_guard, (ref, proof)
        assert not proof["errors"], (ref, proof["errors"])
        assert set(proof["required_paths"]).issubset(proof["paths"]), proof
        assert 0 < len(proof["text"]) <= MAX_EVIDENCE_CHARS
        assert proof["used_chars"] == len(proof["text"])
        assert proof["omission_count"] >= len(proof["omissions"])
        assert proof["truncated"] == bool(proof["omission_count"])
        assert len(fetches) <= 4 and all(sha == ref for sha, _ in fetches)
        assert "Coverage check (action-local, not a finding)" in proof["text"]
        assert "HIDDEN_TRUTH" not in proof["text"]
        if ref == BAD:
            assert "not established by directly invoked steps" in proof["text"]
        else:
            assert "structural preflight" in proof["text"]

        item = {"filename": ACTION, "patch": DATA["historical_action_patch"]}
        context = {"path": ACTION, "text": sources[ACTION], "item": item}
        assert enrich_first_pass_contexts([context], ref, fetch) == 1
        details = context["item"]["_dcoir_exact_head_dependency_diagnostics"]
        assert details["evidence_chars"] <= MAX_EVIDENCE_CHARS
        assert details["truncated"] == proof["truncated"]
        assert details["omission_count"] == proof["omission_count"]
        assert context["item"]["_dcoir_source_coverage_guard"] == expected_guard
        assert "_dcoir_source_inventory_candidate" not in context["item"], (
            "Historical second-P1 structural evidence alone is not an independently "
            "verified GitHub finding."
        )

        # Exercise the real first-pass debug writer without provider calls.
        # Evidence omissions are audit metadata, not model findings.
        receipts = []
        config = review.load_pareto_context_config(
            str(HERE.parent / "openrouter-pr-review-pareto.yml")
        )
        with patch.object(review.hardened, "openrouter_review",
                          return_value=({"summary": "offline", "findings": []},
                                        "offline", "none")), patch.object(
                          review.hardened, "write_debug_text_artifact_safely"), patch.object(
                          review.hardened, "write_debug_json_artifact_safely",
                          side_effect=lambda _cfg, name, payload: receipts.append((name, payload))):
            result = review.review_single_file_context(
                0, context, {"number": 617, "title": "Offline historical fixture"},
                DATA["historical_action_patch"], {}, config, [], "first-pass-deep"
            )
        assert result["result"]["findings"] == []
        metadata = [payload for name, payload in receipts if name.startswith("metadata/per-file/")]
        assert len(metadata) == 1, receipts
        assert metadata[0]["exact_head_dependency_diagnostics"] == details
        assert metadata[0]["source_coverage_guard_status"] == expected_guard

    # Adva: a truly unavailable direct verifier must still block the review.
    sources = historical_sources(SAFE)
    def missing_verifier(path: str, sha: str) -> str:
        if path == VERIFIER:
            raise OSError("simulated source retrieval failure")
        assert sha == SAFE
        return sources[path]
    try:
        enrich_first_pass_contexts(
            [{"path": ACTION, "text": sources[ACTION],
              "item": {"filename": ACTION, "patch": DATA["historical_action_patch"]}}],
            SAFE, missing_verifier,
        )
    except RuntimeError as exc:
        assert "required-dependency-excerpt-unavailable" in str(exc)
    else:
        raise AssertionError("Missing selected verifier was allowed to pass")
    # The note itself is mandatory even if the caller insists on tiny budgets.
    tiny = build(ACTION, sources[ACTION], SAFE,
                 lambda path, sha: sources[path], max_chars=600)
    assert "coverage-invariant-exceeds-budget" in tiny["errors"], tiny
    assert not tiny["text"]
    # Adva: mandatory-direct-script fetch overflow is visibly accounted for
    # before any partial evidence can be mistaken for a clean review.
    overflow = build(ACTION, sources[ACTION], SAFE,
                     lambda *_: (_ for _ in ()).throw(AssertionError("unexpected fetch")),
                     max_fetches=1)
    assert "direct-script-budget-exceeded" in overflow["errors"], overflow
    assert overflow["omission_count"] == len(overflow["omissions"]) >= 1
    assert all(x["reason"] == "direct-script-budget-exceeded"
               for x in overflow["omissions"])
    assert not overflow["text"]
    assert not _git_freshness_comparator(
        '# source_of_truth != "git ls-files -z"\n'
        '# expected.get(field) != current.get(field)\n'
        'NOTE = "build_inventory(root) and raise ValueError"\n'
    )
    invalid = build(ACTION, sources[ACTION], "main", lambda *_: None)
    assert invalid["errors"] == ["invalid-reviewed-head"]
    assert invalid["text"] == ""

    print("PASS: PR617 second P1 original bad/safe verifier replay, 8/8 outcomes")
    print("PASS: both authentic Git heads, 2100-char note budget and auditable omissions")
    print("PASS: no speculative finding, Git-source failure guard, hostile metadata/budget")


if __name__ == "__main__":
    main()
