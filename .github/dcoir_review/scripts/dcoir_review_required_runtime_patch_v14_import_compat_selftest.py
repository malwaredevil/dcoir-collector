#!/usr/bin/env python3
"""Import-compatibility self-test for DCOIR Review v14/v15.

This covers the #340 and #341 workflow crash shapes: live v13 did not expose
some helper names that later runtime overlays referenced unconditionally.
"""

from __future__ import annotations

import importlib
from types import SimpleNamespace

import dcoir_review_required_runtime_patch_v13 as v13


def main() -> None:
    for name in ("_render_integrity_errors", "_rendered_comment_has_integrity_problem", "_family"):
        if hasattr(v13, name):
            delattr(v13, name)

    if not hasattr(v13, "_rendered_comment_has_problem"):
        v13._rendered_comment_has_problem = lambda _rendered, _finding: False

    v14 = importlib.import_module("dcoir_review_required_runtime_patch_v14")
    v15 = importlib.import_module("dcoir_review_required_runtime_patch_v15")

    v15.apply_pareto_context_module(SimpleNamespace(base=None, hardened=None))

    assert v14._render_integrity_errors([], {}) == []
    assert v14._family("yaml_pull_request_target") == "yaml"
    assert v14._family("ps_process_launch") == "powershell"
    assert v14._family("python_pickle_load") == "python"
    assert v14._family("k8s_host_network") == "kubernetes"
    assert v14._family("ts_inner_html") == "typescript"
    assert v14._family("unknown") == "other"
    assert "kubernetes" not in v14.FAMILY_ORDER

    metadata = v14._augment_metadata([], [], [], SimpleNamespace(max_inline_comments=12), {"selected_keys": []})
    assert metadata["version"] == "v15"

    module = SimpleNamespace(base=None, hardened=None)
    v14.apply_pareto_context_module(module)
    v15.apply_pareto_context_module(module)
    assert v13._rendered_comment_has_problem is v14._rendered_comment_has_integrity_problem
    assert v13._rendered_comment_has_integrity_problem is v14._rendered_comment_has_integrity_problem

    print("dcoir_review_required_runtime_patch_v14_import_compat_selftest passed")


if __name__ == "__main__":
    main()
