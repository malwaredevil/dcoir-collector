#!/usr/bin/env python3
"""Offline Adva checks for source-coverage verification in first-pass prompts."""
from __future__ import annotations

from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import dcoir_review_historical_recall_cases as historical
from dcoir_review.exact_head_dependency_evidence import (
    MAX_EVIDENCE_CHARS,
    build_exact_head_dependency_evidence,
)
from dcoir_review.source_inventory_contract import (
    _coverage_invariant_note,
    _git_freshness_comparator,
)

def _case_evidence(case):
    def checked_read(path: str, sha: str) -> str:
        assert sha == case["reviewed_head"]
        return case["dependency_sources"][path]

    return build_exact_head_dependency_evidence(
        case["focus_path"], case["focus_source"], case["reviewed_head"], checked_read
    )


def main() -> None:
    bad, safe = historical.cases()
    old = _case_evidence(bad)
    repaired = _case_evidence(safe)

    assert old["coverage_guard"] == "not-evidenced-in-action"
    assert repaired["coverage_guard"] == "pre-analyzer-structural-check"
    for evidence in (old, repaired):
        assert not evidence["errors"], evidence["errors"]
        assert evidence["text"].count("Coverage check (action-local, not a finding)") == 1
        assert evidence["text"].endswith("\n")
        assert len(evidence["text"]) <= MAX_EVIDENCE_CHARS
        assert "validation.success" in evidence["text"]
        assert "P1" not in evidence["text"]  # No leaked scoring truth
        assert "HIDDEN_" not in evidence["text"]
        assert len(evidence["paths"]) <= 4
        assert evidence["truncated"]  # Inventory extras excluded by bounded policy.
    assert "not established by directly invoked steps" in old["text"]
    assert "source is unlisted" not in old["text"]  # No planted expected answer
    assert "action line 22" in repaired["text"]
    assert "verify_powershell_surface_inventory_ci.py" in repaired["text"]

    safe_verifier = safe["dependency_sources"][historical.VERIFIER]
    assert _git_freshness_comparator(safe_verifier)
    spoofed = '''
    # build_inventory(root) source_of_truth != "git ls-files -z"
    # expected.get(field) != current.get(field)
    # raise ValueError("inventory mismatch")
    NOTE = "build_inventory(root); source_of_truth git ls-files -z"
    '''
    assert not _git_freshness_comparator(spoofed)
    assert not _git_freshness_comparator("def broken(:")
    assert not _git_freshness_comparator("x" * 120001)

    checked = dict(safe["dependency_sources"])
    examined = list(repaired["paths"])
    sha = safe["reviewed_head"]
    known = {(sha, path): contents for path, contents in checked.items()}
    direct = [historical.SCRIPT, historical.VERIFIER]

    earlier = f"python {historical.VERIFIER}\npython {historical.SCRIPT}\n"
    later = f"python {historical.SCRIPT}\npython {historical.VERIFIER}\n"
    note, state = _coverage_invariant_note(earlier, direct, sha, examined, known)
    assert state == "pre-analyzer-structural-check" and note.endswith("\n")
    note, state = _coverage_invariant_note(later, direct, sha, examined, known)
    assert state == "not-evidenced-in-action"
    note, state = _coverage_invariant_note(
        "# python " + historical.VERIFIER + "\npython " + historical.SCRIPT,
        direct, sha, examined, known,
    )
    assert state == "not-evidenced-in-action"

    known[(sha, historical.VERIFIER)] = spoofed
    note, state = _coverage_invariant_note(earlier, direct, sha, examined, known)
    assert state == "not-evidenced-in-action"

    # Cache material is scoped to the reviewed commit and source-list for this file.
    fake_head = "0" * 40
    note, state = _coverage_invariant_note(earlier, direct, fake_head, examined, known)
    assert state == "not-applicable"
    print("PASS: actual reviewed-head P1 and repaired control, bounded source-coverage notes")
    print("PASS: fake comments, malformed verifier, late/out-of-order guard, cross-HEAD isolation")


if __name__ == "__main__":
    main()
