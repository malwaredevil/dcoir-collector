# Issue 618: cross-file contract cues must reach routine *per-file* detector
# prompts without extra provider requests or trusting other-file source text.
contract_diff = """diff --git a/.github/actions/run-audit/action.yml b/.github/actions/run-audit/action.yml
index 1234567..7654321 100644
--- a/.github/actions/run-audit/action.yml
+++ b/.github/actions/run-audit/action.yml
@@ -1,1 +1,2 @@
 name: Audit
+run: python tools/scan.py --inventory state/surface_inventory.json
diff --git a/ops/Invoke-Inspect.ps1 b/ops/Invoke-Inspect.ps1
new file mode 100644
index 0000000..1111111
--- /dev/null
+++ b/ops/Invoke-Inspect.ps1
@@ -0,0 +1,1 @@
+Write-Output 'probe'
diff --git a/docs/overview.md b/docs/overview.md
index 3333333..4444444 100644
--- a/docs/overview.md
+++ b/docs/overview.md
@@ -1,1 +1,2 @@
 # Overview
+Editorial update
"""
integration_path = ".github/actions/run-audit/action.yml"
contract_context = mod.build_cross_file_contract_context(integration_path, contract_diff)
assert "Cross-file contract review cues" in contract_context
assert '"ops/Invoke-Inspect.ps1"' in contract_context
assert "source inventory" in contract_context
assert "fail closed" in contract_context
assert contract_context.index("ops/Invoke-Inspect.ps1") < contract_context.index("docs/overview.md")
assert len(contract_context) <= 2200
assert mod.build_cross_file_contract_context("docs/overview.md", contract_diff) == ""
assert mod.build_cross_file_contract_context(integration_path, contract_diff, 240) == ""

contract_prompt = mod.build_per_file_review_prompt(
    {"number": 618, "title": "Check CI target coverage"},
    {
        "filename": integration_path,
        "status": "modified",
        "patch": "run: python tools/scan.py --inventory state/surface_inventory.json",
    },
    "name: Audit\nrun: python tools/scan.py --inventory state/surface_inventory.json\n",
    contract_diff,
    config,
    [],
    "first-pass-deep",
)
assert "Cross-file contract review cues" in contract_prompt
assert '"ops/Invoke-Inspect.ps1"' in contract_prompt
assert "Do not report an issue solely from this list" in contract_prompt
assert "Full head-file context" in contract_prompt

many_changed = (
    "diff --git a/.github/actions/run-audit/action.yml b/.github/actions/run-audit/action.yml\n"
    + "".join(
        f"diff --git a/ops/tool-{n:03d}.ps1 b/ops/tool-{n:03d}.ps1\n"
        "new file mode 100644\n"
        for n in range(200)
    )
)
bounded_context = mod.build_cross_file_contract_context(integration_path, many_changed)
assert 450 <= len(bounded_context) <= 2200
assert "more changed path(s) omitted by context budget" in bounded_context
assert '"ops/tool-000.ps1"' in bounded_context

malformed_path_diff = (
    "diff --git a/.github/actions/run-audit/action.yml b/.github/actions/run-audit/action.yml\n"
    "diff --git a/ops/unsafe\tname.ps1 b/ops/unsafe\tname.ps1\n"
)
assert mod.build_cross_file_contract_context(integration_path, malformed_path_diff) == ""


# The large-source budget must not displace a critical inventory mutation.
inventory_heavy_diff = many_changed + (
    "diff --git a/state/surface_inventory.json b/state/surface_inventory.json\n"
    "index 1111111..2222222 100644\n"
    "--- a/state/surface_inventory.json\n"
    "+++ b/state/surface_inventory.json\n"
    "@@ -1,1 +1,1 @@\n"
    '-{"surfaces": 10}\n'
    '+{"surfaces": 11}\n'
)
inventory_heavy_context = mod.build_cross_file_contract_context(
    integration_path, inventory_heavy_diff
)
assert '"state/surface_inventory.json"' in inventory_heavy_context
assert len(inventory_heavy_context) <= 2200
assert "more changed path(s) omitted by context budget" in inventory_heavy_context

# Escape and skip unusual file names rather than interpolating diff-controlled
# source as an instruction or breaking prompt boundaries.
quoted_name_diff = (
    "diff --git a/.github/actions/run-audit/action.yml b/.github/actions/run-audit/action.yml\n"
    'diff --git a/ops/evil"prompt.ps1 b/ops/evil"prompt.ps1\n'
)
quoted_name_ctx = mod.build_cross_file_contract_context(integration_path, quoted_name_diff)
assert 'evil\\\"prompt.ps1' in quoted_name_ctx

print("Pareto context DCOIR Review selftest passed")
