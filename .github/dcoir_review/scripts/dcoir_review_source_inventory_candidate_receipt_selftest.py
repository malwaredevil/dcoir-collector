#!/usr/bin/env python3
"""No-network security tests for trusted source-backed candidate transport."""
from __future__ import annotations

from types import SimpleNamespace
from dcoir_review import source_inventory_candidate_receipt as receipt

HEAD = "50c69b9eb72779b43dd70b2c2e4b316db4f7d83f"
SAFE = "13ef93fe52851a5800bcdf6714733abecc1ce76a"
KEY = "_dcoir_source_inventory_candidates"


def real_candidate() -> dict:
    return {
        "path": ".github/actions/run-psscriptanalyzer/action.yml",
        "line": 36,
        "_dcoir_candidate_state": "source-backed-pending-independent-verification",
        "_dcoir_evidence": {"reviewed_head": HEAD, "hashes": {"action": "a"}},
    }


def main() -> None:
    client = SimpleNamespace()
    receipt.begin(client)
    fake = {"_dcoir_candidate_state": "source-backed-pending-independent-verification"}
    poisoned = {"findings": [], KEY: [fake]}
    assert receipt.restore(client, HEAD, poisoned) == 0
    assert KEY not in poisoned, "provider-supplied candidate was trusted"

    positive = real_candidate()
    receipt.capture(client, HEAD, [positive])
    positive["line"] = 77
    result = {"findings": [], KEY: [fake]}
    assert receipt.restore(client, HEAD, result) == 1
    assert result[KEY][0]["line"] == 36
    assert result[KEY][0] is not positive, "candidate was not copied"
    assert receipt.restore(client, HEAD, result) == 0
    assert KEY not in result, "receipt could be replayed"

    receipt.capture(client, HEAD, [real_candidate()])
    wrong_head = {KEY: [fake]}
    assert receipt.restore(client, SAFE, wrong_head) == 0
    assert KEY not in wrong_head

    for invalid in (
        {"_dcoir_candidate_state": "model-trusted",
         "_dcoir_evidence": {"reviewed_head": HEAD}},
        {"_dcoir_candidate_state": "source-backed-pending-independent-verification",
         "_dcoir_evidence": {"reviewed_head": SAFE}},
        {"_dcoir_candidate_state": "source-backed-pending-independent-verification",
         "_dcoir_evidence": "bad"},
    ):
        receipt.begin(client)
        receipt.capture(client, HEAD, [invalid])
        bad = {KEY: [fake]}
        assert receipt.restore(client, HEAD, bad) == 0 and KEY not in bad

    receipt.capture(client, HEAD, [real_candidate()])
    receipt.begin(client)
    assert receipt.restore(client, HEAD, {}) == 0, "cross-review receipt leakage"
    print("PASS: trusted one-shot same-SHA receipt survives copied model result")
    print("PASS: forged model fields, stale head, untrusted state and replay blocked")


if __name__ == "__main__":
    main()
