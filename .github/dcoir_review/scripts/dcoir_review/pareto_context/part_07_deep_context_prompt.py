def build_python_path_alias_context(gh: Any, pr: dict[str, Any], files: list[dict[str, Any]]) -> dict[str, set[str]]:
    head_sha = str(pr.get("head", {}).get("sha", "") or "")
    if not head_sha:
        return {}
    path_alias_context: dict[str, set[str]] = {}
    for item in files:
        path = str(item.get("filename", "")).strip()
        status = str(item.get("status", "")).strip()
        if not path or status in {"removed", "deleted"} or Path(path).suffix.lower() != ".py":
            continue
        try:
            aliases = python_path_constructor_aliases(fetch_pr_file_text(gh, path, head_sha))
        except Exception:
            continue
        if aliases:
            path_alias_context[path] = aliases
    return path_alias_context


def build_python_os_alias_context(gh: Any, pr: dict[str, Any], files: list[dict[str, Any]]) -> dict[str, set[str]]:
    head_sha = str(pr.get("head", {}).get("sha", "") or "")
    if not head_sha:
        return {}
    os_alias_context: dict[str, set[str]] = {}
    for item in files:
        path = str(item.get("filename", "")).strip()
        status = str(item.get("status", "")).strip()
        if not path or status in {"removed", "deleted"} or Path(path).suffix.lower() != ".py":
            continue
        try:
            aliases = python_os_module_aliases(fetch_pr_file_text(gh, path, head_sha))
        except Exception:
            continue
        if aliases:
            os_alias_context[path] = aliases
    return os_alias_context


def build_deep_context_block(gh: Any, pr: dict[str, Any], files: list[dict[str, Any]], config: Any, review_mode: str) -> tuple[str, str]:
    if review_mode == "diff":
        return "", "diff-focused review; no full changed-file context requested"
    head_sha = str(pr.get("head", {}).get("sha", "") or "")
    if not head_sha:
        return "", "deep context requested but PR head SHA was unavailable"

    max_files = max(0, int(getattr(config, "deep_review_max_files", 8)))
    max_file_chars = max(0, int(getattr(config, "deep_review_max_file_chars", 12000)))
    max_total_chars = max(0, int(getattr(config, "deep_review_max_total_chars", 24000)))
    lines = [
        "Deep changed-file context:",
        f"Mode: {review_mode}.",
        "Use this full changed-file context to reason about whole-file behavior and downstream effects, while anchoring actionable findings to changed lines when practical.",
    ]
    included: list[str] = []
    omitted: list[str] = []
    remaining = max_total_chars

    for item in files:
        if len(included) >= max_files:
            break
        path = str(item.get("filename", "")).strip()
        status = str(item.get("status", "")).strip()
        if not path:
            continue
        if status in {"removed", "deleted"}:
            omitted.append(f"{path} (deleted)")
            continue
        try:
            text = base.sanitize_text(fetch_pr_file_text(gh, path, head_sha), config)
        except UnicodeDecodeError:
            omitted.append(f"{path} (not utf-8 text)")
            continue
        except Exception as exc:
            omitted.append(f"{path} ({str(exc)[:120]})")
            continue
        truncated = len(text) > max_file_chars
        snippet = text[:max_file_chars]
        if truncated:
            snippet = f"{snippet}\n\n[full-file context truncated for this file]"
        block = f"### {path}\nStatus: {status}; head ref: {head_sha[:12]}\n~~~{language_hint(path)}\n{snippet}\n~~~"
        if len(block) > remaining:
            if not included and remaining > DEEP_CONTEXT_MIN_PARTIAL_CHARS + len(DEEP_CONTEXT_BUDGET_EXHAUSTED_SUFFIX):
                partial = block[: remaining - len(DEEP_CONTEXT_BUDGET_EXHAUSTED_SUFFIX)].rstrip()
                fence_suffix = "\n~~~" if partial.count("~~~") % 2 == 1 else ""
                block = f"{partial}{fence_suffix}\n\n[deep context budget exhausted]"
            else:
                omitted.append(f"{path} (deep context budget)")
                continue
        lines.append(block)
        included.append(f"{path}{' (truncated)' if truncated else ''}")
        remaining -= len(block)
        if remaining <= DEEP_CONTEXT_MIN_PARTIAL_CHARS:
            # Keep a floor for useful context; below this, the next block would
            # usually be a tiny fragment rather than actionable file context.
            break

    if not included:
        return "", f"{review_mode}; no changed-file context included; omitted: {', '.join(omitted) or 'none'}"
    summary = f"{review_mode}; included {len(included)} file context block(s): {', '.join(included[:6])}"
    if len(included) > 6:
        summary += f", and {len(included) - 6} more"
    if omitted:
        summary += f"; omitted {len(omitted)}: {', '.join(omitted[:4])}"
    return "\n\n".join(lines), summary


def truncate_with_balanced_fences(text: str, max_chars: int, marker: str) -> str:
    if len(text) <= max_chars:
        return text
    if max_chars <= len(marker):
        return marker[:max_chars]
    fence_close = "\n~~~"
    partial_limit = max(0, max_chars - len(marker))
    partial = text[:partial_limit].rstrip()
    if partial.count("~~~") % 2 == 1:
        partial_limit = max(0, max_chars - len(marker) - len(fence_close))
        partial = text[:partial_limit].rstrip()
        if partial.count("~~~") % 2 == 1:
            partial = f"{partial}{fence_close}"
    return f"{partial}{marker}"


