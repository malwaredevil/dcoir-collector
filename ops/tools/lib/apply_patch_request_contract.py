from __future__ import annotations

import hashlib
import json
import pathlib
import re
import subprocess
from dataclasses import dataclass
from typing import Any

SCHEMA_V1 = "dcoir.ops.apply_patch_request.v1"

SCHEMA_V2 = "dcoir.ops.apply_patch_request.v2"

SCHEMA = SCHEMA_V1

SAFE_ID_RE = re.compile(r"^[A-Za-z0-9._-]+$")

DEFAULT_COMMIT = "Apply governed ops patch request"

BOT_USER_NAME = "github-actions[bot]"

BOT_USER_EMAIL = "41898282+github-actions[bot]@users.noreply.github.com"

BLOCKED_TARGET_PREFIXES = (
    ".git/",
    "chatgpt_staging/",
    "ops/requests/",
    "ops/reports/",
)

FORBIDDEN_PATCH_MARKERS = (
    "GIT binary patch",
    "Binary files ",
    "rename from ",
    "rename to ",
    "copy from ",
    "copy to ",
    "new file mode ",
    "deleted file mode ",
    "old mode ",
    "new mode ",
    "similarity index ",
    "dissimilarity index ",
)

class RequestError(RuntimeError):
    """Raised when a request violates the apply-patch contract."""

@dataclass(frozen=True)
class TargetSpec:
    path: str
    allowed_roots: tuple[str, ...]
    expected_target_blob_sha: str | None = None
    expected_current_sha256: str | None = None
    expected_new_sha256: str | None = None

@dataclass(frozen=True)
class PatchRequest:
    schema: str
    request_id: str
    mode: str
    operation: str
    target_branch: str
    patch_path: str
    expected_patch_sha256: str
    targets: tuple[TargetSpec, ...]
    commit_message: str = DEFAULT_COMMIT
    allow_default_branch: bool = False
    default_branch_reason: str = ""
    allow_workflow_changes: bool = False
    workflow_change_reason: str = ""

    @property
    def target_paths(self) -> tuple[str, ...]:
        return tuple(target.path for target in self.targets)

    @property
    def target_path(self) -> str | None:
        return self.targets[0].path if len(self.targets) == 1 else None

def run(cmd: list[str], *, cwd: pathlib.Path, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, cwd=cwd, check=check, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()

def sha256_file(path: pathlib.Path) -> str:
    return sha256_bytes(path.read_bytes())

def require_string(value: Any, *, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise RequestError(f"{field} is required")
    return value

def optional_string(value: Any, *, field: str) -> str | None:
    if value is None or value == "":
        return None
    if not isinstance(value, str):
        raise RequestError(f"{field} must be a string")
    return value

def optional_bool(value: Any, *, field: str, default: bool = False) -> bool:
    if value is None:
        return default
    if not isinstance(value, bool):
        raise RequestError(f"{field} must be a boolean")
    return value

def git_blob_sha(repo: pathlib.Path, target_path: str) -> str:
    proc = run(["git", "ls-files", "-s", "--", target_path], cwd=repo)
    parts = proc.stdout.split()
    return parts[1] if len(parts) > 1 else ""

def normalize_repo_path(value: str, *, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise RequestError(f"{field} is required")
    if "\\" in value:
        raise RequestError(f"{field} must use forward slashes: {value}")
    p = pathlib.PurePosixPath(value.strip())
    if p.is_absolute() or ".." in p.parts or str(p) in {"", "."}:
        raise RequestError(f"{field} must be a safe repo-relative path: {value}")
    return p.as_posix()

def validate_request_id(value: str) -> str:
    if not isinstance(value, str) or not SAFE_ID_RE.match(value):
        raise RequestError("request_id must contain only letters, numbers, dot, underscore, and hyphen")
    return value

def validate_branch(repo: pathlib.Path, branch: str, default_branch: str, allow_default: bool, reason: str) -> str:
    if not isinstance(branch, str) or not branch.strip():
        raise RequestError("target_branch is required")
    candidate = branch.strip()
    if candidate.startswith(("refs/", "origin/")):
        raise RequestError("target_branch must be a branch name, not a refspec or remote-tracking name")
    if any(token in candidate for token in ("..", "@{", "\\", ":", "~", "^", "?", "*", "[")):
        raise RequestError(f"target_branch contains unsupported ref syntax: {candidate}")
    if candidate.startswith("/") or candidate.endswith("/") or "//" in candidate:
        raise RequestError(f"target_branch must be a safe branch name: {candidate}")
    check = subprocess.run(
        ["git", "check-ref-format", "--branch", candidate],
        cwd=repo,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if check.returncode != 0:
        raise RequestError(f"target_branch is not a valid git branch name: {candidate}")
    if candidate == default_branch and not allow_default:
        raise RequestError("target_branch is the default branch; set allow_default_branch with a reason to permit this")
    if allow_default and candidate == default_branch and not reason.strip():
        raise RequestError("allow_default_branch=true requires default_branch_reason")
    return candidate

def validate_roots(raw: Any) -> tuple[str, ...]:
    if not isinstance(raw, list) or not raw:
        raise RequestError("allowed_roots must be a non-empty list")
    roots: list[str] = []
    for item in raw:
        if not isinstance(item, str):
            raise RequestError("allowed_roots[] must be a string")
        root = normalize_repo_path(item, field="allowed_roots[]").rstrip("/")
        if not root or root == ".":
            raise RequestError("allowed_roots must not include repo root")
        roots.append(root)
    return tuple(sorted(set(roots)))

def path_under(path: str, roots: tuple[str, ...]) -> bool:
    return any(path == root or path.startswith(root + "/") for root in roots)

def validate_target_path(target: TargetSpec, request: PatchRequest) -> None:
    path = target.path
    if any(path == prefix.rstrip("/") or path.startswith(prefix) for prefix in BLOCKED_TARGET_PREFIXES):
        raise RequestError(f"target_path is blocked for ops patch requests: {path}")
    if not path_under(path, target.allowed_roots):
        raise RequestError(f"target_path is outside allowed_roots: {path}")
    if path.startswith(".github/workflows/") and not request.allow_workflow_changes:
        raise RequestError("workflow targets require allow_workflow_changes=true and workflow_change_reason")

def request_dir_from_path(repo: pathlib.Path, request_path: pathlib.Path, request_id: str) -> pathlib.Path:
    try:
        rel = request_path.resolve().relative_to((repo / "ops/requests/apply_patch").resolve())
    except ValueError as exc:
        raise RequestError("request file must live under ops/requests/apply_patch/<request_id>/request.json") from exc
    if rel.parts != (request_id, "request.json"):
        raise RequestError("request file path must be ops/requests/apply_patch/<request_id>/request.json")
    return request_path.parent

def validate_digest(value: str | None, *, field: str, length: int) -> None:
    if value is not None and not re.fullmatch(rf"[0-9a-f]{{{length}}}", value):
        raise RequestError(f"{field} must be a {length}-character hex digest")

def target_from_v1(data: dict[str, Any]) -> TargetSpec:
    target = TargetSpec(
        path=normalize_repo_path(require_string(data.get("target_path"), field="target_path"), field="target_path"),
        allowed_roots=validate_roots(data.get("allowed_roots")),
        expected_target_blob_sha=optional_string(data.get("expected_target_blob_sha"), field="expected_target_blob_sha"),
        expected_current_sha256=optional_string(data.get("expected_current_sha256"), field="expected_current_sha256"),
        expected_new_sha256=optional_string(data.get("expected_new_sha256"), field="expected_new_sha256"),
    )
    if not (target.expected_target_blob_sha or target.expected_current_sha256):
        raise RequestError("expected_target_blob_sha or expected_current_sha256 is required")
    validate_digest(target.expected_target_blob_sha, field="expected_target_blob_sha", length=40)
    validate_digest(target.expected_current_sha256, field="expected_current_sha256", length=64)
    validate_digest(target.expected_new_sha256, field="expected_new_sha256", length=64)
    return target

def target_from_v2(raw: Any, index: int) -> TargetSpec:
    if not isinstance(raw, dict):
        raise RequestError(f"targets[{index}] must be an object")
    target = TargetSpec(
        path=normalize_repo_path(require_string(raw.get("path"), field=f"targets[{index}].path"), field=f"targets[{index}].path"),
        allowed_roots=validate_roots(raw.get("allowed_roots")),
        expected_target_blob_sha=optional_string(raw.get("expected_target_blob_sha"), field=f"targets[{index}].expected_target_blob_sha"),
        expected_current_sha256=optional_string(raw.get("expected_current_sha256"), field=f"targets[{index}].expected_current_sha256"),
        expected_new_sha256=optional_string(raw.get("expected_new_sha256"), field=f"targets[{index}].expected_new_sha256"),
    )
    if not (target.expected_target_blob_sha or target.expected_current_sha256):
        raise RequestError(f"targets[{index}] requires expected_target_blob_sha or expected_current_sha256")
    validate_digest(target.expected_target_blob_sha, field=f"targets[{index}].expected_target_blob_sha", length=40)
    validate_digest(target.expected_current_sha256, field=f"targets[{index}].expected_current_sha256", length=64)
    validate_digest(target.expected_new_sha256, field=f"targets[{index}].expected_new_sha256", length=64)
    return target

def load_request(repo: pathlib.Path, request_path: pathlib.Path, default_branch: str) -> PatchRequest:
    data = json.loads(request_path.read_text(encoding="utf-8"))
    schema = data.get("schema")
    if schema not in {SCHEMA_V1, SCHEMA_V2}:
        raise RequestError(f"schema must be {SCHEMA_V1} or {SCHEMA_V2}")
    request_id = validate_request_id(require_string(data.get("request_id"), field="request_id"))
    target_branch = validate_branch(
        repo,
        require_string(data.get("target_branch"), field="target_branch"),
        default_branch,
        optional_bool(data.get("allow_default_branch"), field="allow_default_branch"),
        optional_string(data.get("default_branch_reason"), field="default_branch_reason") or "",
    )
    patch_path = normalize_repo_path(require_string(data.get("patch_path"), field="patch_path"), field="patch_path")
    request_dir = request_dir_from_path(repo, request_path, request_id)
    expected_prefix = f"ops/requests/apply_patch/{request_id}/"
    if not patch_path.startswith(expected_prefix) or not patch_path.endswith((".patch", ".diff")):
        raise RequestError("patch_path must be a .patch or .diff file in the same request directory")
    if (repo / patch_path).resolve().parent != request_dir.resolve():
        raise RequestError("patch_path must be in the same request directory as request.json")
    expected_patch_sha256 = require_string(data.get("expected_patch_sha256"), field="expected_patch_sha256").lower()
    if not re.fullmatch(r"[0-9a-f]{64}", expected_patch_sha256):
        raise RequestError("expected_patch_sha256 must be a lowercase SHA-256 hex digest")
    if schema == SCHEMA_V1:
        mode = optional_string(data.get("mode", "dry-run"), field="mode") or "dry-run"
        if mode not in {"dry-run", "apply"}:
            raise RequestError("mode must be dry-run or apply")
        operation = mode
        targets = (target_from_v1(data),)
    else:
        mode = require_string(data.get("mode"), field="mode")
        if mode != "patch-set":
            raise RequestError('v2 mode must be "patch-set"')
        operation = optional_string(data.get("operation", "dry-run"), field="operation") or "dry-run"
        if operation not in {"dry-run", "apply"}:
            raise RequestError("operation must be dry-run or apply")
        raw_targets = data.get("targets")
        if not isinstance(raw_targets, list) or not raw_targets:
            raise RequestError("targets must be a non-empty list")
        targets = tuple(target_from_v2(raw, index) for index, raw in enumerate(raw_targets))
        seen: set[str] = set()
        for target in targets:
            if target.path in seen:
                raise RequestError(f"duplicate target path in targets: {target.path}")
            seen.add(target.path)
    commit_message = (optional_string(data.get("commit_message", DEFAULT_COMMIT), field="commit_message") or DEFAULT_COMMIT).strip() or DEFAULT_COMMIT
    if "\n" in commit_message or "\r" in commit_message:
        raise RequestError("commit_message must be a single line")
    request = PatchRequest(
        schema=schema,
        request_id=request_id,
        mode=mode,
        operation=operation,
        target_branch=target_branch,
        patch_path=patch_path,
        expected_patch_sha256=expected_patch_sha256,
        targets=targets,
        commit_message=commit_message,
        allow_default_branch=optional_bool(data.get("allow_default_branch"), field="allow_default_branch"),
        default_branch_reason=optional_string(data.get("default_branch_reason"), field="default_branch_reason") or "",
        allow_workflow_changes=optional_bool(data.get("allow_workflow_changes"), field="allow_workflow_changes"),
        workflow_change_reason=optional_string(data.get("workflow_change_reason"), field="workflow_change_reason") or "",
    )
    if request.allow_workflow_changes and not request.workflow_change_reason.strip():
        raise RequestError("allow_workflow_changes=true requires workflow_change_reason")
    for target in request.targets:
        validate_target_path(target, request)
    return request
