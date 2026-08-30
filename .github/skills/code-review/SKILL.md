---
name: code-review
description: Review dcoir-collector pull requests for confirmed high-impact defects using the repository's existing governance, compatibility, security, and evidence-integrity rules. Use for GitHub Copilot pull-request code review.
---

# DCOIR collector code review

Use this skill only for pull-request review. It narrows review behavior; it does not replace or override the repository root `AGENTS.md`.

1. Read and apply the `AGENTS.md` **Review guidelines** as the standing authority for review scope and severity. Report only confirmed, actionable defects with a concrete failure mode; do not report style-only, speculative, or nice-to-have issues.
2. Prioritize security vulnerabilities, unsafe subprocess or shell behavior, credential/secret exposure, path traversal or unsafe file handling, broken authorization/approval logic, data loss, and evidence-integrity failures.
3. For GitHub Actions changes, inspect trust boundaries: untrusted PR data entering shell or expressions, unsafe `pull_request_target` use, overbroad token permissions, secret exposure, and validation paths that can be bypassed.
4. For Windows-targeted PowerShell, check Windows PowerShell 5.1 compatibility. Do not treat PowerShell 7 behavior as proof of Windows PowerShell 5.1 compatibility.
5. Treat broken collector behavior, incorrect DCOIR outputs, corrupted or misplaced evidence, broken CI/validation, and bypassed repository governance as review findings when the PR concretely introduces them.
6. Missing tests are findings only when the changed code leaves a confirmed high-impact behavior unvalidated. Validation output is evidence, not automatically a code-review finding.
7. Anchor each finding to the changed line that introduces the defect and explain the observable failure or risk. Prefer the smallest safe repair and include an exact replacement when it is clear.
8. Use the built-in read-only GitHub MCP context when repository facts materially affect the finding—for example, a PR-linked issue's acceptance criteria, relevant workflow/check evidence, or surrounding repository source. Verify such facts rather than guessing.
9. Do not use Playwright MCP unless the correctness of the changed code genuinely depends on browser or rendered-UI behavior.
10. Do not seek unrelated external MCP context or broaden the review into third-party systems merely because an MCP tool exists.
11. Preserve reviewer independence. Do not use DCOIR Review comments or outputs from the same pull request as a source of findings; assess the code and authoritative repository context independently.
12. If the evidence is insufficient to establish a concrete defect, do not publish it as a finding.
