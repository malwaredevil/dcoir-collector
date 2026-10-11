#!/usr/bin/env python3
"""Adversarial and opposite-polarity selftests for independently verified promotion."""
from __future__ import annotations

import copy
import hashlib
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import dcoir_review_historical_recall_cases as history
import openrouter_pr_review_pareto_context as review
from dcoir_review.source_inventory_candidate import detect_inventory_coverage_candidate
from dcoir_review.source_inventory_promotion import (
    verify_source_inventory_for_promotion as verify,
    verify_bounded_inventory_candidates as bounded,
    integrate_verified_inventory_findings as integrate,
)


def sources(case):
    return {**case["caller_sources"], **case["dependency_sources"],
            case["focus_path"]:case["focus_source"]}


def original_candidate(case):
    return detect_inventory_coverage_candidate(
        focus_path=case["focus_path"],
        head_source=case["focus_source"],
        patch=case["changed_diff"].split("\ndiff --git ",1)[0],
        reviewed_head=case["reviewed_head"],
        dependencies=case["dependency_sources"],
        caller_sources=case["caller_sources"],
        action_guard_status="not-evidenced-in-action",
    )


def main():
    positive, safe = history.cases()
    candidate=original_candidate(positive)
    assert candidate and candidate["severity"]=="high"
    original_src=sources(positive)
    head=positive["reviewed_head"]
    path=positive["focus_path"]
    index=review.hardened.build_added_line_index(positive["changed_diff"])
    assert (path,36) in index
    observed=[]
    def fetch(name,ref):
        assert ref==head, "not the immutable reviewed commit"
        observed.append(name)
        return original_src[name]

    proof=verify(candidate,head,index,fetch)
    assert proof and proof["path"]==path and proof["line"]==36
    assert proof["severity"]=="high" and proof["confidence"]>=0.9
    assert len(observed)==10 and len(set(observed))==10, observed
    assert proof["_dcoir_verified_source_inventory"] is True
    assert "newly tracked" in proof["body"].lower()
    assert "not" not in proof["title"].lower().split()
    assert verify(candidate,head,{},fetch) is None

    config=review.load_pareto_context_config(str(HERE.parent/"openrouter-pr-review-pareto.yml"))
    # The newly verified candidate traverses the existing normalizer, but
    # *after* ordinary fix synthesis, so no provider call is possible here.
    result={"summary":"No actionable issues were found.","findings":[],
            "_dcoir_source_inventory_candidates":[copy.deepcopy(candidate)]}
    found,diag=integrate(result,[],config,index,head,fetch,review.hardened)
    assert diag["advisories"]==1 and diag["promoted"]==1 and diag["pending"]==0,diag
    assert len(found)==1 and found[0]["path"]==path and found[0]["line"]==36
    assert found[0]["severity"]=="high"
    assert "No actionable" not in result["summary"]
    assert "_dcoir_source_inventory_candidates" not in result

    # Fresh source mismatch MUST reject even though original metadata remains
    # a convincing-looking, source-backed candidate.
    cases=[]
    def fork(**overrides):
        result=copy.deepcopy(candidate)
        result.update(overrides)
        return result
    cases.extend([
        fork(line=35),fork(path="../../secrets"),fork(_dcoir_candidate_state="safely-cleared"),
        fork(_dcoir_evidence={"reviewed_head":head,"paths":[],"hashes":{}}),
        fork(_dcoir_evidence={**candidate["_dcoir_evidence"],"reviewed_head":"0"*40}),
    ])
    for key in ("paths","hashes"):
        altered=copy.deepcopy(candidate)
        if key=="paths":
            altered["_dcoir_evidence"][key].append(path)
        else:
            altered["_dcoir_evidence"][key][path]="0"*16
        cases.append(altered)
    assert all(verify(c,head,index,fetch) is None for c in cases)
    assert verify(candidate,head.upper(),index,fetch) is None

    bad_source=dict(original_src)
    bad_source[path]=bad_source[path].replace("PSScriptAnalyzer pinned version",
                                              "PSScriptAnalyzer unpinned version")
    assert verify(candidate,head,index,lambda n,r:bad_source[n]) is None
    assert verify(candidate,head,index,lambda n,r:"x"*120001) is None
    assert verify(candidate,head,index,lambda n,r: (_ for _ in ()).throw(IOError())) is None

    # A forged "safe" snapshot with all hashes recomputed cannot bypass the
    # fresh check for the real inventory-freshness verifier in the action.
    real_safe=sources(safe)
    safe_claim=copy.deepcopy(candidate)
    safe_claim["_dcoir_evidence"]["reviewed_head"]=safe["reviewed_head"]
    safe_claim["_dcoir_evidence"]["hashes"]={
        n: hashlib.sha256(real_safe[n].encode()).hexdigest()[:16]
        for n in safe_claim["_dcoir_evidence"]["paths"]
    }
    safe_action=real_safe[path].splitlines()
    safe_line=next(i for i,line in enumerate(safe_action,1)
                   if "python project_sources/collector/tools/run_powershell_analyzer.py " in line)
    safe_claim["line"]=safe_line
    assert verify(safe_claim,safe["reviewed_head"],{(path,safe_line):1},
                  lambda n,r:real_safe[n]) is None

    # Independent caller checks: a protection added before action execution
    # or an independently active inventory guard must make the finding vanish.
    caller=dict(original_src)
    key=".github/workflows/reusable-validate-on-pr.yml"
    caller[key]=caller[key].replace(
        "        uses: ./.github/actions/run-psscriptanalyzer",
        "      - name: Verify source inventory\n"
        "        run: python verify_powershell_surface_inventory_ci.py\n"
        "      - name: Run analyzer\n"
        "        uses: ./.github/actions/run-psscriptanalyzer",
    )
    claim=copy.deepcopy(candidate)
    claim["_dcoir_evidence"]["hashes"][key]=hashlib.sha256(caller[key].encode()).hexdigest()[:16]
    assert verify(claim,head,index,lambda n,r:caller[n]) is None

    cli=dict(original_src)
    cp="project_sources/collector/tools/powershell_analyzer_cli.py"
    cli[cp]+='\nGIT_DISCOVERY = "git ls-files -z"\n'
    claim=copy.deepcopy(candidate)
    claim["_dcoir_evidence"]["hashes"][cp]=hashlib.sha256(cli[cp].encode()).hexdigest()[:16]
    assert verify(claim,head,index,lambda n,r:cli[n]) is None

    # Unrecognized alias imports and disabled CI routes must abstain, even
    # if an adversary also updates all claimed content hashes.
    alias=dict(original_src)
    checker=".github/github_actions/tools/check_required_surfaces.py"
    alias[checker]+="\nimport subprocess as safe_looking_alias\n"
    claim=copy.deepcopy(candidate)
    claim["_dcoir_evidence"]["hashes"][checker]=hashlib.sha256(alias[checker].encode()).hexdigest()[:16]
    assert verify(claim,head,index,lambda n,r:alias[n]) is None
    disabled=dict(original_src)
    entry=".github/workflows/validate-on-pr.yml"
    disabled[entry]+="\nif: false\n"
    claim=copy.deepcopy(candidate)
    claim["_dcoir_evidence"]["hashes"][entry]=hashlib.sha256(disabled[entry].encode()).hexdigest()[:16]
    assert verify(claim,head,index,lambda n,r:disabled[n]) is None

    # Codex P1: inline PowerShell freshness guard before analyzer must
    # conservatively block promotion even when all source hashes are forged
    # to match the safe modified action and the changed anchor is plausible.
    inline = dict(original_src)
    prefix = "        python project_sources/collector/tools/run_powershell_analyzer.py "
    block = (
        "        $tracked = @(git ls-files -- '*.ps1' '*.psm1')\n"
        "        $listed = @((Get-Content -LiteralPath 'project_sources/collector/powershell_surface_inventory.json' -Raw | ConvertFrom-Json).surfaces | ForEach-Object { $_.path })\n"
        "        $delta = @(Compare-Object -ReferenceObject $tracked -DifferenceObject $listed)\n"
        "        if ($delta.Count -gt 0) { throw 'Inventory freshness failed' }\n"
    )
    assert prefix in inline[path]
    inline[path] = inline[path].replace(prefix, block + prefix, 1)
    claimed = copy.deepcopy(candidate)
    claimed["line"] = next(
        i for i, content in enumerate(inline[path].splitlines(), 1)
        if content.startswith(prefix)
    )
    claimed["_dcoir_evidence"]["hashes"][path] = hashlib.sha256(
        inline[path].encode()).hexdigest()[:16]
    assert verify(
        claimed, head, {(path, claimed["line"]): 1},
        lambda name, _ref: inline[name]
    ) is None, "Unsafe HIGH finding despite inline fail-closed freshness guard"
    # Different inline implementations must also abstain. The verifier is
    # not a general-purpose PowerShell parser, so unfamiliar checks block
    # promotion rather than receiving an invented clean bill of health.
    for command in (
        "        $tracked = git -C . ls-files -- '*.ps1'\n",
        "        $missing = Compare-Object $listed $tracked\n",
        "        $listed = Get-Content -Raw project_sources/collector/powershell_surface_inventory.json\n",
        "        $tracked = Get-ChildItem -Recurse *.ps1\n",
        "        python project_sources/collector/tools/check_environment.py --gate\n",
    ):
        alternate = dict(original_src)
        alternate[path] = alternate[path].replace(prefix, command + prefix, 1)
        hypothesis = copy.deepcopy(candidate)
        hypothesis["line"] = next(
            i for i, row in enumerate(alternate[path].splitlines(), 1)
            if row.startswith(prefix)
        )
        hypothesis["_dcoir_evidence"]["hashes"][path] = hashlib.sha256(
            alternate[path].encode()).hexdigest()[:16]
        assert verify(
            hypothesis, head, {(path, hypothesis["line"]): 1},
            lambda name, _ref: alternate[name]
        ) is None, "Possible pre-analyzer guard allowed unsafe HIGH promotion"

    # Candidate title/body are untrusted metadata; the verifier synthesizes
    # its own bounded wording, so injected GitHub mentions cannot survive.
    tampered=fork(title="EVIL @bot",body="EVIL\n@bot",confidence=1.0)
    source_proof=verify(tampered,head,index,fetch)
    assert source_proof and "EVIL" not in str(source_proof)

    # The promotion never consumes all review slots by fiat; no overwrites.
    maxed=copy.copy(config)
    maxed.max_inline_comments=0
    result={"summary":"clean","findings":[],"_dcoir_source_inventory_candidates":[candidate]}
    output,diag=integrate(result,[],maxed,index,head,fetch,review.hardened)
    assert output==[] and diag["promoted"]==0 and diag["pending"]==1,diag
    assert "UNRESOLVED" in result["summary"]
    result={"summary":"clean","findings":[],"_dcoir_source_inventory_candidates":[candidate]}
    low={"path":path,"line":36,"severity":"low","title":"style","body":"cosmetic"}
    output,diag=integrate(result,[low],config,index,head,fetch,review.hardened)
    assert output==[low] and diag["pending"]==1

    result={"summary":"clean","findings":[],"_dcoir_source_inventory_candidates":[candidate]}
    verified_already={"path":path,"line":36,"severity":"high",
                      "title":"Source inventory incomplete",
                      "body":"newly tracked PowerShell source may be omitted"}
    output,diag=integrate(result,[verified_already],config,index,head,fetch,review.hardened)
    assert output==[verified_already] and diag["already_found"]==1 and diag["pending"]==0

    result={"summary":"clean","findings":[],"_dcoir_source_inventory_candidates":[candidate]*3}
    output,diag=integrate(result,[],config,index,head,fetch,review.hardened)
    assert output==[] and diag["pending"]==3
    assert bounded([candidate]*3,head,index,fetch)==([],3)

    result={"summary":"clean","findings":[],"_dcoir_source_inventory_candidates":[candidate]}
    output,diag=integrate(result,[],config,index,head,
             lambda n,r: (_ for _ in ()).throw(IOError("offline")),review.hardened)
    assert output==[] and diag["pending"]==1
    no_candidate={"summary":"no changes","findings":[]}
    output,diag=integrate(no_candidate,[],config,index,head,fetch,review.hardened)
    assert output==[] and diag["advisories"]==0 and no_candidate["summary"]=="no changes"

    print("PASS: original PR617 true P1 verified HIGH on changed line 36")
    print("PASS: actual repaired action safe despite forged candidate and replayed hashes")
    print("PASS: 10 exact-HEAD reads, no provider/model calls; normalizer and publication cap")
    print("PASS: absent/mismatched/untrusted evidence, guarded caller, caller hash, altered CLI")
    print("PASS: no model-attribution confusion, no fake metadata in verified finding")
    print("PASS: never force-publish when unsafe; pending status remains visible")


if __name__=="__main__":
    main()
