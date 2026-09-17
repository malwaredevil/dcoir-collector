"""Stable finding-comment policy helpers for canonical renderers."""

from __future__ import annotations

from typing import Any

from dcoir_review import finding_verifier


SYNTHESIS_VERIFIED_MARKER = "_dcoir_fix_synthesis_verified_v20"

_TEMPLATE_BY_KIND: dict[str, tuple[str, str, str]] = {
    "yaml_token_to_pr_url": (
        "Workflow sends repository token to PR-controlled URL",
        "This workflow sends a repository token to a URL taken from pull request metadata.",
        "Use a trusted allowlisted endpoint or remove the outbound request from the privileged workflow.",
    ),
    "yaml_metadata_shell": (
        "Workflow executes pull request metadata in a shell",
        "This line passes pull request metadata into shell execution.",
        "Do not execute PR metadata; use explicit allowlisted values outside privileged shell steps.",
    ),
    "yaml_shell_pipe": (
        "Workflow pipes a network-fetched script into a shell",
        "This line executes network-fetched content directly in the shell.",
        "Download, pin, and verify the content before execution.",
    ),
    "yaml_untrusted_checkout": (
        "Privileged workflow checks out untrusted PR code",
        "This privileged workflow checks out pull request controlled code.",
        "Use a trusted base ref or split privileged metadata handling from untrusted code checkout.",
    ),
    "yaml_pull_request_target": (
        "Privileged pull_request_target workflow context",
        "pull_request_target runs with base-repository privileges.",
        "Keep untrusted PR code and shell execution out of this workflow.",
    ),
    "yaml_broad_write": (
        "GitHub Actions workflow grants broad write permissions",
        "This workflow grants write-scoped permissions.",
        "Reduce permissions to the least privilege required by each job.",
    ),
    "ps_dynamic_exec": (
        "PowerShell executes caller-controlled code",
        "This line executes input as PowerShell code.",
        "Replace dynamic execution with an allowlisted command path.",
    ),
    "ps_plaintext_secure_string": (
        "PowerShell converts plaintext into a SecureString",
        "This line treats plaintext input as secret material.",
        "Load secrets from the platform secret store instead of caller plaintext.",
    ),
    "ps_acl": (
        "PowerShell grants broad filesystem ACL access",
        "This line grants broad filesystem permissions.",
        "Grant only the least-privileged identity and access rights needed.",
    ),
    "ps_process_launch": (
        "PowerShell launches a caller-controlled process",
        "This line launches a process from caller-controlled values.",
        "Resolve executables from an allowlist and pass structured arguments.",
    ),
    "ps_env_token": (
        "PowerShell forwards an environment token to a request-controlled callback",
        "This line reads an environment token and forwards it to a request-controlled callback.",
        "Allowlist destinations and keep authorization headers scoped to trusted endpoints.",
    ),
    "ps_run_key_persistence": (
        "PowerShell writes a Windows Run-key persistence location",
        "This line writes to a Run-key persistence location.",
        "Remove the Run-key write or gate it behind a governed audited operation.",
    ),
    "python_pickle_load": (
        "Python deserializes untrusted pickle data",
        "pickle can execute code during deserialization.",
        "Use a safe data format or only unpickle trusted authenticated data.",
    ),
    "python_yaml_load": (
        "Python loads YAML with an unsafe loader",
        "yaml.load with an unsafe loader can construct arbitrary objects.",
        "Use yaml.safe_load for untrusted YAML.",
    ),
    "python_shell_exec": (
        "Python executes caller-controlled shell text",
        "This line executes shell text from caller-controlled input.",
        "Use an allowlisted executable and argument list with shell=False.",
    ),
    "python_env_token": (
        "Python forwards an environment token to a request-controlled callback",
        "This line reads an environment token and forwards it to a request-controlled callback.",
        "Allowlist callback hosts and keep authorization headers scoped to trusted endpoints.",
    ),
    "python_archive_extract": (
        "Python extracts an archive without path containment checks",
        "Archive extraction can write outside the intended directory.",
        "Validate each member path resolves under the destination before extraction.",
    ),
    "python_path_write": (
        "Python writes to a request-controlled filesystem path",
        "This write may use a request-controlled path.",
        "Resolve and verify the destination is inside the governed output directory.",
    ),
    "python_truthy_literal_branch": (
        "Python branch condition contains an always-truthy literal",
        "A non-empty string literal after `or` is always truthy, so this branch bypasses the intended comparison.",
        "Compare the same variable explicitly against the second allowed value instead of using the bare string literal.",
    ),
    "k8s_host_pid": (
        "Kubernetes workload shares the host PID namespace",
        "hostPID exposes the host process namespace.",
        "Remove hostPID unless there is a governed operational requirement.",
    ),
    "k8s_host_network": (
        "Kubernetes workload shares the host network namespace",
        "hostNetwork exposes host networking to the workload.",
        "Remove hostNetwork unless the workload has a documented need.",
    ),
    "k8s_privileged_container": (
        "Kubernetes container runs privileged",
        "privileged: true gives broad host-level capabilities.",
        "Drop privileged mode and grant only required capabilities.",
    ),
    "k8s_privilege_escalation": (
        "Kubernetes container allows privilege escalation",
        "allowPrivilegeEscalation permits additional privileges.",
        "Set allowPrivilegeEscalation: false and drop unnecessary capabilities.",
    ),
    "k8s_host_path": (
        "Kubernetes workload mounts a hostPath volume",
        "hostPath mounts host filesystem paths into the workload.",
        "Use a scoped persistent volume or remove the host filesystem mount.",
    ),
    "ts_inner_html": (
        "TypeScript writes untrusted data into HTML",
        "Writing untrusted data to innerHTML can create DOM injection.",
        "Use textContent or a vetted sanitizer.",
    ),
    "ts_dynamic_execution": (
        "TypeScript executes dynamic string code",
        "Dynamic string execution can run attacker-controlled JavaScript.",
        "Use function callbacks and allowlisted behavior instead of executable strings.",
    ),
}


def template_for_kind(kind: str) -> tuple[str, str, str]:
    return _TEMPLATE_BY_KIND.get(
        str(kind or "").strip(),
        (
            "Security-sensitive changed line",
            "This changed line matched a high-risk review sentinel.",
            "Replace the risky pattern with a governed safe implementation.",
        ),
    )


def deterministic_sentinel_kind(finding: Any) -> str:
    if not isinstance(finding, dict):
        return ""
    verifier = finding.get(finding_verifier.VERIFIER_MARKER)
    if not isinstance(verifier, dict):
        return ""
    if verifier.get("mode") != "deterministic-core-sentinel" or verifier.get("supported") is not True:
        return ""
    verifier_kind = str(verifier.get("kind", "") or "").strip()
    explicit_kind = str(finding.get("_risk_sentinel_kind", "") or "").strip()
    raw_key = finding.get("_risk_sentinel_key")
    keyed_kind = ""
    if isinstance(raw_key, (list, tuple)) and len(raw_key) == 3:
        keyed_kind = str(raw_key[2] or "").strip()
    return verifier_kind or explicit_kind or keyed_kind


def safe_single_line_suggestion(base: Any, finding: dict[str, Any]) -> str:
    if not bool(finding.get(SYNTHESIS_VERIFIED_MARKER)):
        return ""
    suggestion = str(finding.get("suggested_replacement", "") or "").rstrip()
    if not suggestion or any(marker in suggestion for marker in ("\n", "\r", "```", "~~~")):
        return ""
    if len(suggestion) > 1000:
        return ""
    checker = getattr(base, "is_safe_suggestion", None)
    if callable(checker) and not checker(suggestion):
        return ""
    return suggestion


def render_base_comment(finding: dict[str, Any]) -> str:
    path = str(finding.get("path", "") or "")
    try:
        line = int(finding.get("line", 0) or 0)
    except (TypeError, ValueError):
        line = 0
    kind = str(finding.get("_risk_sentinel_kind", "") or "").strip()
    if not kind:
        raw_key = finding.get("_risk_sentinel_key")
        if isinstance(raw_key, (list, tuple)) and len(raw_key) == 3:
            kind = str(raw_key[2] or "").strip()
    title_default, body_default, notes_default = template_for_kind(kind)
    title = str(finding.get("title", "") or title_default).strip()
    body = str(finding.get("body", "") or body_default).strip()
    guidance = finding.get("fix_guidance") if isinstance(finding.get("fix_guidance"), dict) else {}
    notes = str(guidance.get("notes", "") or notes_default).strip()
    validation = str(finding.get("validation", "") or guidance.get("validation", "") or "").strip()
    lines = [f"**{title}**", "", body]
    covered = finding.get("covered_risk_sentinel_keys")
    if isinstance(covered, list) and len(covered) > 1:
        rendered: list[str] = []
        for raw in covered:
            if isinstance(raw, (list, tuple)) and len(raw) == 3:
                rendered.append(f"`{raw[0]}:{raw[1]}` `{raw[2]}`")
        if rendered:
            lines.extend(["", "**Covered signals:**", *[f"- {item}" for item in rendered]])
    if notes:
        lines.extend(["", "**Suggested fix:**", "", notes])
    if validation:
        lines.extend(["", "**Validation:**", "", "```bash", validation, "```"])
    if path and line > 0 and not covered:
        lines.extend(["", f"_Anchor: `{path}:{line}`_"])
    return "\n".join(lines).strip()

