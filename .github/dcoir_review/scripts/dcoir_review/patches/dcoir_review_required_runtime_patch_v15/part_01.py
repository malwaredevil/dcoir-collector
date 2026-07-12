"""Fifteenth required-coverage layer for DCOIR Review.

v15 is intentionally small: it fixes the #341 compatibility crash where v14
introduced a family-balancing helper but delegated it to a v13 helper that did
not exist on live main. It also keeps Kubernetes findings as optional/bonus
rather than part of the core must-pass family order.
"""

from __future__ import annotations

from typing import Any

import dcoir_review_required_runtime_patch_v13 as v13
import dcoir_review_required_runtime_patch_v14 as v14

VERSION = "v15"
FAMILY_ORDER = ("yaml", "powershell", "python", "other", "typescript")
_ORIGINAL_V13_FAMILY = getattr(v13, "_family", None)


def _fallback_family(kind: Any) -> str:
    value = str(kind or "")
    if value.startswith("yaml_"):
        return "yaml"
    if value.startswith("ps_"):
        return "powershell"
    if value.startswith("python_"):
        return "python"
    if value.startswith("k8s_"):
        return "kubernetes"
    if value.startswith("ts_"):
        return "typescript"
    return "other"


def _family(kind: Any) -> str:
    upstream = _ORIGINAL_V13_FAMILY
    if callable(upstream):
        try:
            result = str(upstream(kind) or "")
        except Exception:
            result = ""
        if result:
            return {"ps": "powershell", "k8s": "kubernetes", "ts": "typescript"}.get(result, result)
    return _fallback_family(kind)


def _patch_family_compat() -> None:
    v13._family = _family
    v14._family = _family
    v14.FAMILY_ORDER = FAMILY_ORDER
    v14.VERSION = VERSION


def apply_pareto_context_module(_module: Any) -> None:
    _patch_family_compat()
