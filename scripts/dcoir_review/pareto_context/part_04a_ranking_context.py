def safe_artifact_name(path: str, fallback: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_.-]+", "-", path).strip("-")
    return (cleaned or fallback)[:120]


def added_diff_lines_for_path(diff: str, path: str) -> list[hardened.ChangedLine]:
    return [line for line in hardened.iter_added_diff_lines(diff) if line.path == path]


def is_probably_github_actions_workflow(path: str, text: str) -> bool:
    lower_path = path.lower()
    if lower_path.startswith(".github/workflows/"):
        return True
    if Path(lower_path).suffix not in {".yml", ".yaml"}:
        return False
    if "workflow" in Path(lower_path).name or "github" in lower_path or "actions" in lower_path:
        return True
    return bool(re.search(r"(?m)^\s*on\s*:\s*$", text) and re.search(r"(?m)^\s*jobs\s*:\s*$", text))


def file_specialization(path: str, text: str) -> str:
    suffix = Path(path).suffix.lower()
    if suffix in {".ps1", ".psm1", ".psd1"}:
        return (
            "PowerShell specialization: inspect Invoke-Expression, Start-Process, Invoke-WebRequest/Invoke-RestMethod, "
            "Expand-Archive, Set-Content/Add-Content/Out-File/Copy-Item/Move-Item, Remove-Item, Set-Acl, request-controlled "
            "paths, credential forwarding, Windows PowerShell 5.1 compatibility, parser behavior, and PSScriptAnalyzer-style risks."
        )
    if suffix == ".py":
        return (
            "Python specialization: inspect unsafe deserialization, eval/exec/dynamic code evaluation, subprocess/shell execution, tar/zip/archive extraction, "
            "pathlib/os.path containment, raw SQL/query construction, requests/urllib/httpx outbound requests, secret/env persistence, "
            "temporary files, exception handling, and focused py_compile/Bandit/unit validation."
        )
    if suffix in {".yml", ".yaml"}:
        if is_probably_github_actions_workflow(path, text):
            return (
                "GitHub Actions YAML specialization: inspect pull_request_target, broad permissions, checkout of untrusted refs, "
                "untrusted github.event metadata in shell, token or secret forwarding, action pinning, command injection, and workflow "
                "inventory/readback validation."
            )
        return (
            "YAML specialization: inspect security-sensitive configuration, secret material, command fields, path or URL sinks, "
            "privilege settings, schema validity, and whether the file appears to define CI/CD or operational behavior."
        )
    if suffix in {".ts", ".js", ".mjs", ".cjs"}:
        return (
            "TypeScript/JavaScript specialization: inspect child_process execution, dynamic Function/eval, path joins/resolves before "
            "file writes, fetch/webhook token forwarding, raw SQL strings, async error handling, and TypeScript validation."
        )
    if suffix == ".json":
        return "JSON specialization: inspect schema validity, generated-report markers, duplicated or conflicting keys, and secret material."
    if suffix == ".md":
        return "Markdown/governance specialization: inspect misleading operator guidance, missing validation evidence, stale authority, and unsafe instructions."
    return "Generic specialization: inspect correctness, security, validation, and governance risk in the changed file."


def per_file_priority(item: dict[str, Any], file_text: str) -> tuple[int, int, str]:
    path = str(item.get("filename", "") or "")
    suffix = Path(path.lower()).suffix
    if suffix in {".ps1", ".psm1", ".psd1", ".py"}:
        family = 0
    elif suffix in {".yml", ".yaml"} and is_probably_github_actions_workflow(path, file_text):
        family = 0
    elif suffix in {".yml", ".yaml"}:
        family = 1
    elif suffix in {".ts", ".js", ".mjs", ".cjs"}:
        family = 2
    else:
        family = 3
    changes = int(item.get("changes") or 0)
    return family, -changes, path


def normalized_finding_text(value: Any, max_chars: int = 240) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip().lower())[:max_chars]


def finding_review_family(finding: dict[str, Any]) -> str:
    path = str(finding.get("path", "") or "").strip()
    lower_path = path.lower()
    suffix = Path(lower_path).suffix
    title = str(finding.get("title", "") or "")
    body = str(finding.get("body", "") or "")
    haystack = f"{title}\n{body}".lower()
    if suffix in {".ps1", ".psm1", ".psd1"}:
        return "powershell"
    if suffix == ".py":
        return "python"
    if suffix in {".yml", ".yaml"}:
        if (
            lower_path.startswith(".github/workflows/")
            or "github action" in haystack
            or "workflow" in Path(lower_path).name
            or "/actions/" in lower_path
        ):
            return "github-actions-yaml"
        if (
            "kubernetes" in lower_path
            or lower_path.startswith("k8s/")
            or "/k8s/" in lower_path
            or "kubernetes" in haystack
            or "kubectl" in haystack
        ):
            return "kubernetes-yaml"
        return "yaml"
    if suffix in {".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs"}:
        return "typescript"
    return "other"


def finding_dedupe_key(finding: dict[str, Any]) -> tuple[str, str, str, str]:
    return (
        str(finding.get("path", "") or "").strip(),
        str(finding.get("line", "") or "").strip(),
        normalized_finding_text(finding.get("title", "")),
        normalized_finding_text(finding.get("body", "")),
    )


def dedupe_findings_for_ranking(findings: list[dict[str, Any]]) -> list[dict[str, Any]]:
    deduped: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str, str]] = set()
    for finding in findings:
        key = finding_dedupe_key(finding)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(finding)
    return deduped


