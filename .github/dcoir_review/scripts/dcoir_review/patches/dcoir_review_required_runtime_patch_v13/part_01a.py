def _template_for_kind(kind: str) -> tuple[str, str, str]:
    templates = {
        v10.YAML_TOKEN_TO_PR_URL: ("Workflow sends repository token to PR-controlled URL", "This workflow sends a repository token to a URL taken from pull request metadata.", "Use a trusted allowlisted endpoint or remove the outbound request from the privileged workflow."),
        v4.YAML_METADATA_SHELL: ("Workflow executes pull request metadata in a shell", "This line passes pull request metadata into shell execution.", "Do not execute PR metadata; use explicit allowlisted values outside privileged shell steps."),
        v4.YAML_SHELL_PIPE: ("Workflow pipes a network-fetched script into a shell", "This line executes network-fetched content directly in the shell.", "Download, pin, and verify the content before execution."),
        v4.YAML_UNTRUSTED_CHECKOUT: ("Privileged workflow checks out untrusted PR code", "This privileged workflow checks out pull request controlled code.", "Use a trusted base ref or split privileged metadata handling from untrusted code checkout."),
        v4.YAML_PULL_REQUEST_TARGET: ("Privileged pull_request_target workflow context", "pull_request_target runs with base-repository privileges.", "Keep untrusted PR code and shell execution out of this workflow."),
        v4.YAML_BROAD_WRITE: ("GitHub Actions workflow grants broad write permissions", "This workflow grants write-scoped permissions.", "Reduce permissions to the least privilege required by each job."),
        v9.PS_DYNAMIC_EXEC: ("PowerShell executes caller-controlled code", "This line executes input as PowerShell code.", "Replace dynamic execution with an allowlisted command path."),
        PS_PLAINTEXT_SECURE_STRING: ("PowerShell converts plaintext into a SecureString", "This line treats plaintext input as secret material.", "Load secrets from the platform secret store instead of caller plaintext."),
        v4.PS_ACL: ("PowerShell grants broad filesystem ACL access", "This line grants broad filesystem permissions.", "Grant only the least-privileged identity and access rights needed."),
        v4.PS_PROCESS_LAUNCH: ("PowerShell launches a caller-controlled process", "This line launches a process from caller-controlled values.", "Resolve executables from an allowlist and pass structured arguments."),
        v5.PS_ENV_TOKEN: ("PowerShell forwards an environment token to a request-controlled callback", "This line reads an environment token and forwards it to a request-controlled callback.", "Allowlist destinations and keep authorization headers scoped to trusted endpoints."),
        PS_RUN_KEY_PERSISTENCE: ("PowerShell writes a Windows Run-key persistence location", "This line writes to a Run-key persistence location.", "Remove the Run-key write or gate it behind a governed audited operation."),
        v9.PYTHON_PICKLE_LOAD: ("Python deserializes untrusted pickle data", "pickle can execute code during deserialization.", "Use a safe data format or only unpickle trusted authenticated data."),
        v5.PYTHON_YAML_LOAD: ("Python loads YAML with an unsafe loader", "yaml.load with an unsafe loader can construct arbitrary objects.", "Use yaml.safe_load for untrusted YAML."),
        v5.PYTHON_SHELL_EXEC: ("Python executes caller-controlled shell text", "This line executes shell text from caller-controlled input.", "Use an allowlisted executable and argument list with shell=False."),
        v5.PYTHON_ENV_TOKEN: ("Python forwards an environment token to a request-controlled callback", "This line reads an environment token and forwards it to a request-controlled callback.", "Allowlist callback hosts and keep authorization headers scoped to trusted endpoints."),
        v11.PYTHON_ARCHIVE_EXTRACT: ("Python extracts an archive without path containment checks", "Archive extraction can write outside the intended directory.", "Validate each member path resolves under the destination before extraction."),
        v11.PYTHON_PATH_WRITE: ("Python writes to a request-controlled filesystem path", "This write may use a request-controlled path.", "Resolve and verify the destination is inside the governed output directory."),
        K8S_HOST_PID: ("Kubernetes workload shares the host PID namespace", "hostPID exposes the host process namespace.", "Remove hostPID unless there is a governed operational requirement."),
        K8S_HOST_NETWORK: ("Kubernetes workload shares the host network namespace", "hostNetwork exposes host networking to the workload.", "Remove hostNetwork unless the workload has a documented need."),
        K8S_PRIVILEGED_CONTAINER: ("Kubernetes container runs privileged", "privileged: true gives broad host-level capabilities.", "Drop privileged mode and grant only required capabilities."),
        K8S_PRIVILEGE_ESCALATION: ("Kubernetes container allows privilege escalation", "allowPrivilegeEscalation permits additional privileges.", "Set allowPrivilegeEscalation: false and drop unnecessary capabilities."),
        K8S_HOST_PATH: ("Kubernetes workload mounts a hostPath volume", "hostPath mounts host filesystem paths into the workload.", "Use a scoped persistent volume or remove the host filesystem mount."),
        TS_INNER_HTML: ("TypeScript writes untrusted data into HTML", "Writing untrusted data to innerHTML can create DOM injection.", "Use textContent or a vetted sanitizer."),
        TS_DYNAMIC_EXECUTION: ("TypeScript executes dynamic string code", "Dynamic string execution can run attacker-controlled JavaScript.", "Use function callbacks and allowlisted behavior instead of executable strings."),
    }
    return templates.get(kind, ("Security-sensitive changed line", "This changed line matched a high-risk review sentinel.", "Replace the risky pattern with a governed safe implementation."))


def _language_for_kind(kind: str) -> str:
    if kind.startswith("python_"):
        return "python"
    if kind.startswith("ps_"):
        return "powershell"
    if kind.startswith(("yaml_", "k8s_")):
        return "yaml"
    if kind.startswith("ts_"):
        return "typescript"
    return "text"


def _scrub_model_footer(value: Any) -> Any:
    if isinstance(value, str):
        scrubbed = re.sub(r"\n?\s*_Reviewed with [^._]+(?:\.[^_]*)?\._\s*", "", value)
        return re.sub(r"(?im)^\s*_?Reviewed with .+?_?\s*$", "", scrubbed).strip()
    if isinstance(value, dict):
        return {key: _scrub_model_footer(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_scrub_model_footer(item) for item in value]
    return value


def _safe_validation(kind: str, path: str, line: int, value: Any = "") -> str:
    current = str(value or "")
    if not current.strip() or "<<" in current or current.count("```") % 2 or "assert text.strip()" in current or current.strip().lower().startswith(("validate ", "validation:")):
        return _validation_for_key(kind, path, line)
    return current


def _integrity_finding(finding: dict[str, Any], key: SentinelKey | None = None, *, force_template: bool = False) -> dict[str, Any]:
    path, line, kind = key or _postable_key(finding)
    item = dict(_scrub_model_footer(finding))
    if not kind:
        return item
    title, body, notes = _template_for_kind(kind)
    rendered_kinds = _text_kinds(path, "\n".join(str(item.get(name, "") or "") for name in ("title", "body")))
    contradictory = {candidate for candidate in rendered_kinds if candidate != kind and candidate in TRACKED_HIGH_RISK_KINDS}
    if force_template or contradictory or kind in TRACKED_HIGH_RISK_KINDS:
        item["title"] = title
        item["body"] = body
    validation = _safe_validation(kind, path, line, item.get("validation", ""))
    item["validation"] = validation
    guidance = item.get("fix_guidance") if isinstance(item.get("fix_guidance"), dict) else {}
    guidance = dict(_scrub_model_footer(guidance))
    guidance.setdefault("language", _language_for_kind(kind))
    guidance["notes"] = notes
    guidance["validation"] = validation
    item["fix_guidance"] = guidance
    item["_risk_sentinel_key"] = [path, line, kind]
    item["_risk_sentinel_kind"] = kind
    return item


def _fallback_for_sentinel(hardened: Any, sentinel: Any, config: Any) -> dict[str, Any]:
    key = _sentinel_key(sentinel)
    path, line, kind = key
    if kind in TRACKED_HIGH_RISK_KINDS:
        return _integrity_finding({"severity": "critical" if kind in REQUIRED_KINDS else "high", "confidence": 0.99, "path": path, "line": line, "_anchored_line_text": str(getattr(sentinel, "text", "") or "")}, key, force_template=True)
    fallback = _ORIGINAL_V12_FALLBACK_FOR_SENTINEL(hardened, sentinel, config)
    fallback["_risk_sentinel_key"] = [path, line, kind]
    fallback["_risk_sentinel_kind"] = kind
    return _integrity_finding(fallback, key)
