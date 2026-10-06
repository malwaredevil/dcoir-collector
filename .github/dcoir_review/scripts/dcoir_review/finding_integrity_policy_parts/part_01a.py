

def _replacement_repeats_kind(kind: str, value: str) -> bool:
    normalized = v13._normalize(value)
    if not normalized:
        return False
    if kind == v4.YAML_BROAD_WRITE:
        return "write-all" in normalized or bool(re.search(r"\b[a-z_-]+\s*:\s*write\b", normalized))
    if kind == v4.YAML_UNTRUSTED_CHECKOUT:
        return "pull_request.head" in normalized or "github.head_ref" in normalized or "merge_commit_sha" in normalized
    if kind == v10.YAML_TOKEN_TO_PR_URL:
        return "github_token" in normalized and "github.event.pull_request.body" in normalized
    if kind == v4.YAML_METADATA_SHELL:
        return "github.event.pull_request" in normalized and any(token in normalized for token in ("bash", "sh -c", "shell:", "run:"))
    if kind == v4.YAML_SHELL_PIPE:
        return ("curl" in normalized or "wget" in normalized) and ("| sh" in normalized or "| bash" in normalized)
    if kind == v4.YAML_PULL_REQUEST_TARGET:
        return "pull_request_target" in normalized
    if kind == v9.PS_DYNAMIC_EXEC:
        return "invoke-expression" in normalized or bool(re.search(r"\biex\b", normalized))
    if kind == v4.PS_ACL:
        return "set-acl" in normalized or "filesystemaccessrule" in normalized or "fullcontrol" in normalized
    if kind == v4.PS_PROCESS_LAUNCH:
        return "start-process" in normalized
    if kind == v5.PS_ENV_TOKEN:
        return ("invoke-webrequest" in normalized or "invoke-restmethod" in normalized) and (
            "authorization" in normalized or "bearer" in normalized or "$env:dcoir_token" in normalized
        )
    if kind == v13.PS_PLAINTEXT_SECURE_STRING:
        return "convertto-securestring" in normalized and "-asplaintext" in normalized
    if kind == v13.PS_RUN_KEY_PERSISTENCE:
        return "currentversion\\run" in normalized
    if kind == v9.PYTHON_PICKLE_LOAD:
        return "pickle.load" in normalized or "pickle.loads" in normalized
    if kind == v5.PYTHON_YAML_LOAD:
        return "yaml.load" in normalized and ("loader=yaml.loader" in normalized or "unsafe" in normalized or "loader=" in normalized)
    if kind == v5.PYTHON_SHELL_EXEC:
        return "shell=true" in normalized or "os.system(" in normalized or "os.popen(" in normalized
    if kind == v5.PYTHON_ENV_TOKEN:
        return ("requests." in normalized or "urlopen" in normalized) and (
            "authorization" in normalized or "bearer" in normalized or "dcoir_token" in normalized
        )
    if kind == v11.PYTHON_ARCHIVE_EXTRACT:
        return "extractall" in normalized
    if kind == v11.PYTHON_PATH_WRITE:
        return (".open(" in normalized or "open(" in normalized or "write_text(" in normalized or "write_bytes(" in normalized) and (
            "user_path" in normalized or "request" in normalized or "callback" in normalized
        )
    if kind == v13.K8S_HOST_PID:
        return "hostpid: true" in normalized
    if kind == v13.K8S_HOST_NETWORK:
        return "hostnetwork: true" in normalized
    if kind == v13.K8S_PRIVILEGED_CONTAINER:
        return "privileged: true" in normalized
    if kind == v13.K8S_PRIVILEGE_ESCALATION:
        return "allowprivilegeescalation: true" in normalized
    if kind == v13.K8S_HOST_PATH:
        return "hostpath:" in normalized
    if kind == v13.TS_INNER_HTML:
        return ".innerhtml" in normalized or ".outerhtml" in normalized or "insertadjacenthtml" in normalized
    if kind == v13.TS_DYNAMIC_EXECUTION:
        return "settimeout(" in normalized or "setinterval(" in normalized or "new function(" in normalized
    return False


def _safe_suggested_replacement(kind: str, value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    normalized = v13._normalize(text)
    if _looks_like_prose(text):
        return ""
    if _replacement_repeats_kind(kind, text):
        return ""
    if kind == v4.YAML_BROAD_WRITE and ("write-all" in normalized or re.search(r"\b[a-z_-]+\s*:\s*write\b", normalized)):
        return ""
    if kind == v4.YAML_UNTRUSTED_CHECKOUT and (
        "pull_request.head" in normalized or "github.head_ref" in normalized or "merge_commit_sha" in normalized
    ):
        return ""
    if kind in {v10.YAML_TOKEN_TO_PR_URL, v4.YAML_METADATA_SHELL} and "github.event.pull_request" in normalized:
        return ""
    return text if len(text.splitlines()) <= 20 else ""


def _safe_guidance_code_field(kind: str, field: str, value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    if kind not in v13.TRACKED_HIGH_RISK_KINDS:
        return text
    field_name = str(field or "").lower()
    if field_name in {"replace", "replace_code", "add", "add_code", "suggested_replacement"}:
        return _safe_suggested_replacement(kind, text)
    # Remove snippets for tracked sentinel kinds are often the dangerous source
    # line. Keeping them fenced has repeatedly confused reviewers, so prefer the
    # deterministic prose template unless the snippet is clearly harmless.
    return _safe_suggested_replacement(kind, text)


def _sanitize_fix_guidance(kind: str, guidance: dict[str, Any], validation: str) -> dict[str, Any]:
    cleaned: dict[str, Any] = {}
    for key, value in guidance.items():
        if key in {"remove", "replace", "add", "remove_code", "replace_code", "add_code", "suggested_replacement"}:
            safe_value = _safe_guidance_code_field(kind, key, value)
            if safe_value:
                cleaned[key] = safe_value
            continue
        cleaned[key] = value
    if kind not in v13.TRACKED_HIGH_RISK_KINDS:
        cleaned["validation"] = validation
    else:
        cleaned.pop("validation", None)
    return cleaned


def _integrity_finding(finding: dict[str, Any], key: SentinelKey | None = None, *, force_template: bool = False) -> dict[str, Any]:
    item = _ORIGINAL_V13_INTEGRITY_FINDING(finding, key, force_template=force_template)
    path, line, kind = key or v13._postable_key(item)
    if not kind:
        return item
    validation = _safe_validation(kind, path, line, item.get("validation", ""))
    item["validation"] = validation
    if kind in v13.TRACKED_HIGH_RISK_KINDS:
        item["suggested_replacement"] = _safe_suggested_replacement(kind, item.get("suggested_replacement", ""))
    guidance = item.get("fix_guidance")
    if not isinstance(guidance, dict):
        guidance = {}
    guidance = dict(v13._scrub_model_footer(guidance))
    guidance["validation"] = validation
    item["fix_guidance"] = _sanitize_fix_guidance(kind, guidance, validation)
    item["_risk_sentinel_key"] = [path, line, kind]
    item["_risk_sentinel_kind"] = kind
    item["_dcoir_v14_trusted_key"] = True
    return item


def _validation_matches_kind(kind: str, rendered: str) -> bool:
    normalized = v13._normalize(rendered)
    if kind == v10.YAML_TOKEN_TO_PR_URL:
        return "github_token" in normalized and "github.event.pull_request.body" in normalized and "| bash" not in normalized and "| sh" not in normalized
    if kind == v4.YAML_SHELL_PIPE:
        return "| bash" in normalized or "| sh" in normalized
    if kind == v4.YAML_METADATA_SHELL:
        return "github.event.pull_request.labels" in normalized or "github.event.pull_request.body" in normalized
    if kind == v4.YAML_UNTRUSTED_CHECKOUT:
        return "pull_request.head" in normalized or "github.head_ref" in normalized
    if kind == v4.YAML_BROAD_WRITE:
        return ": write" in normalized or "write-all" in normalized
    if kind == v4.YAML_PULL_REQUEST_TARGET:
        return "pull_request_target" in normalized
    if kind.startswith("ps_"):
        return "$errors" in rendered and "PSParser" in rendered
    if kind.startswith("python_"):
        return "py_compile" in normalized
    return True


def _render_integrity_errors(findings: list[dict[str, Any]], expected: dict[tuple[str, int], set[str]]) -> list[str]:
    errors = list(_ORIGINAL_V13_RENDER_ERRORS(findings, expected))
    for finding in findings:
        path, line, kind = v13._postable_key(finding)
        validation = str(finding.get("validation", "") or "")
        if kind in v13.TRACKED_HIGH_RISK_KINDS and not _validation_matches_kind(kind, validation):
            errors.append(f"{path}:{line} validation_mismatch kind={kind}")
        suggestion = str(finding.get("suggested_replacement", "") or "")
        if suggestion and suggestion != _safe_suggested_replacement(kind, suggestion):
            errors.append(f"{path}:{line} unsafe_suggested_replacement kind={kind}")
    return sorted(set(errors))


def _rendered_comment_has_integrity_problem(rendered: str, finding: dict[str, Any]) -> bool:
    if _ORIGINAL_V13_RENDERED_PROBLEM(rendered, finding):
        return True
    _path, _line, kind = v13._postable_key(finding)
    marker = "**Validation:**"
    validation_text = rendered.split(marker, 1)[1] if marker in rendered else rendered
    if kind in v13.TRACKED_HIGH_RISK_KINDS and not _validation_matches_kind(kind, validation_text):
        return True
    for suggestion in re.findall(r"```suggestion\s*\n(.*?)```", rendered, flags=re.IGNORECASE | re.DOTALL):
        if _replacement_repeats_kind(kind, suggestion):
            return True
    if rendered.lower().count("validation") > 1:
        return True
    validation = _validation_for_key(kind, _path, _line)
    return bool(validation and rendered.count(validation) > 1)


def _family_counts(keys: list[str]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for key in keys:
        kind = key.rsplit(" ", 1)[-1] if " " in key else ""
        family = _family(kind)
        counts[family] = counts.get(family, 0) + 1
    return counts
