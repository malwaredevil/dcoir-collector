from __future__ import annotations

import ast
import base64
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HEAD = "781a480bb306ff7e0bf1fd55302636a0176ad5c5"
TREE = "ecfe9870cff993695d58c9ee8f35525a0ccd9902"
BRANCH = "refactor/issue-550-dcoir-runtime-consolidation"
repo = Path(os.environ.get("DCOIR_REPO_ROOT") or os.environ.get("GITHUB_WORKSPACE") or ".").resolve()
downloads = Path(os.environ.get("DCOIR_DOWNLOADS_DIR") or os.environ.get("RUNNER_TEMP") or tempfile.gettempdir()).resolve()
preview = repo / ".github/chatgpt_staging/exec_scripts/issue550-pr553-canonical-config-consolidation-preview-complete-patch-006.py"
base_patch = downloads / "issue550-pr553-canonical-config-consolidation-preview-001.patch"
worktree = downloads / "issue550-pr553-canonical-config-readable-preview-009-worktree"
out_patch = downloads / "issue550-pr553-canonical-config-readable-preview-009.patch"
summary = downloads / "issue550-pr553-canonical-config-readable-preview-009-summary.txt"

for key in (
    "OPENROUTER_API_KEY", "GITHUB_TOKEN", "GH_TOKEN", "DCOIR_GITHUB_FG_TOKEN",
    "DCOIR_GITHUB_CL_TOKEN", "DCOIR_GEMINI_API", "DCOIR_OPENAI_API_KEY",
    "DCOIR_OPENAI_PROJECT_ID", "OPENAI_API_KEY",
):
    os.environ.pop(key, None)
os.environ["PYTHONDONTWRITEBYTECODE"] = "1"


def run(*args: str, cwd: Path | None = None, check: bool = True) -> subprocess.CompletedProcess[str]:
    completed = subprocess.run(args, cwd=cwd, text=True, capture_output=True)
    print(completed.stdout, end="")
    print(completed.stderr, end="", file=sys.stderr)
    if check and completed.returncode:
        raise RuntimeError(f"command failed {completed.returncode}: {args}")
    return completed


readable_config = base64.b64decode(
    "IiIiQ2Fub25pY2FsIHBvc3QtYmFzZSBjb25maWd1cmF0aW9uIGZvciBEQ09JUiBSZXZpZXcuCgpUaGUgYmFzZSBQYXJldG8gbG9hZGVyIHBhcnNlcyBjb25maWd1cmF0aW9uIG9uY2UuIFRoaXMgbW9kdWxlIG93bnMgdGhlCnJlc3BvbnNpYmlsaXR5LXNwZWNpZmljIHNldHRpbmdzIHRoYXQgaGlzdG9yaWNhbCBydW50aW1lIG92ZXJsYXlzIHVzZWQgdG8gYWRkIGJ5CndyYXBwaW5nIGBgbG9hZF9wYXJldG9fY29udGV4dF9jb25maWdgYC4gS2VlcGluZyB0aG9zZSBzZXR0aW5ncyBoZXJlIG1ha2VzCmNvbmZpZ3VyYXRpb24gY29tcG9zaXRpb24gZXhwbGljaXQgd2l0aG91dCBwcmVzZXJ2aW5nIHRoZSBydW50aW1lIHdyYXBwZXIgY2hhaW4uCiIiIgoKZnJvbSBfX2Z1dHVyZV9fIGltcG9ydCBhbm5vdGF0aW9ucwoKZnJvbSB0eXBpbmcgaW1wb3J0IEFueQoKREVGQVVMVF9DT05GSVJNQVRJT05fTU9ERUxTID0gKCJvcGVuYWkvZ3B0LTUuNi1zb2wtcHJvIiwpCkRFRkFVTF9SRUFTT05JTkdfRUZGT1JUID0gInhoaWdoIgpERUZBVUxUX1ZFUklGSUVSX1JFUEFJUl9MSU1JVCA9IDgKREVGQVVMVF9BREpVRElDQVRJT05fTU9ERUxTID0gKAogICAgImFudGhyb3BpYy9jbGF1ZGUtb3B1cy01IiwKICAgICJvcGVuYWkvZ3B0LTUuNi1zb2wtcHJvIiwKKQpERUZBVUxUX0FESlVESUNBVElPTl9NQVhfRklORElOR1MgPSA4CkRFRkFVTFRfQ0FORElEQVRFX0RJR0VTVF9DSEFSUyA9IDI0MDAwCkRFRkFVTFRfQ0FORElEQVRFX0VTQ0FMQVRJT05fQ09ORklERU5DRV9NQVJHSU4gPSAwLjEwCkRFRkFVTFRfQ0FORElEQVRFX0VTQ0FMQVRJT05fTUFYX1BBVEhTID0gNApERUZBVUxUX0NBTkRJREFURV9FU0NBTEFUSU9OX0ZJTEVfQ0hBUlMgPSAxMjAwMApERUZBVUxUX0NBTkRJREFURV9FU0NBTEFUSU9OX1RPVEFMX0NPTlRFWFRfQ0hBUlMgPSA0ODAwMApERUZBVUxUX1JFUEFJUl9DUklUSUNfQkFUQ0hfTUFYX0ZJTkRJTkdTID0gOAoKQURBUFRJVkVfU0VNQU5USUNfREVGQVVMVFMgPSB7CiAgICAiYWRhcHRpdmVfc2VtYW50aWNfbWluX3Byb21wdF9jaGFycyI6IDQ4MDAwLAogICAgImFkYXB0aXZlX3NlbWFudGljX3NtYWxsX2RlbHRhX3Byb21wdF9jaGFycyI6IDYwMDAwLAogICAgImFkYXB0aXZlX3NlbWFudGljX3NtYWxsX2RlbHRhX21heF9maWxlcyI6IDQsCiAgICAiYWRhcHRpdmVfc2VtYW50aWNfc21hbGxfZGVsdGFfbWF4X2RpZmZfY2hhcnMiOiAyMDAwMCwKICAgICJhZGFwdGl2ZV9zZW1hbnRpY19zbWFsbF9kZWx0YV9tYXhfY29udGV4dF9jaGFycyI6IDMwMDAwLAp9CgoKZGVmIF9hc19zdHJpbmdfbGlzdCh2YWx1ZTogQW55LCBmYWxsYmFjazogdHVwbGVbc3RyLCAuLi5dKSAtPiBsaXN0W3N0cl06CiAgICBpZiBpc2luc3RhbmNlKHZhbHVlLCBsaXN0KToKICAgICAgICBjbGVhbmVkID0gW3N0cihpdGVtKS5zdHJpcCgpIGZvciBpdGVtIGluIHZhbHVlIGlmIHN0cihpdGVtKS5zdHJpcCgpXQogICAgICAgIGlmIGNsZWFuZWQ6CiAgICAgICAgICAgIHJldHVybiBjbGVhbmVkCiAgICBpZiBpc2luc3RhbmNlKHZhbHVlLCBzdHIpIGFuZCB2YWx1ZS5zdHJpcCgpOgogICAgICAgIHJldHVybiBbdmFsdWUuc3RyaXAoKV0KICAgIHJldHVybiBsaXN0KGZhbGxiYWNrKQoKCmRlZiBfb3B0aW9uYWxfc3RyaW5nX2xpc3QodmFsdWU6IEFueSkgLT4gbGlzdFtzdHJdOgogICAgaWYgaXNpbnN0YW5jZSh2YWx1ZSwgbGlzdCk6CiAgICAgICAgcmV0dXJuIFtzdHIoaXRlbSkuc3RyaXAoKSBmb3IgaXRlbSBpbiB2YWx1ZSBpZiBzdHIoaXRlbSkuc3RyaXAoKV0KICAgIGlmIGlzaW5zdGFuY2UodmFsdWUsIHN0cikgYW5kIHZhbHVlLnN0cmlwKCk6CiAgICAgICAgcmV0dXJuIFt2YWx1ZS5zdHJpcCgpXQogICAgcmV0dXJuIFtdCgoKZGVmIF9wb3NpdGl2ZV9pbnQodmFsdWU6IEFueSwgZmFsbGJhY2s6IGludCkgLT4gaW50OgogICAgdHJ5OgogICAgICAgIHBhcnNlZCA9IGludCh2YWx1ZSkKICAgIGV4Y2VwdCAoVHlwZUVycm9yLCBWYWx1ZUVycm9yKToKICAgICAgICBwYXJzZWQgPSBmYWxsYmFjawogICAgcmV0dXJuIG1heCgxLCBwYXJzZWQpCgoKZGVmIF9vcHRpb25hbF9wb3NpdGl2ZV9pbnQodmFsdWU6IEFueSwga2V5OiBzdHIpIC0+IGludCB8IE5vbmU6CiAgICBpZiB2YWx1ZSBpbiAoTm9uZSwgIiIpOgogICAgICAgIHJldHVybiBOb25lCiAgICB0cnk6CiAgICAgICAgcGFyc2VkID0gaW50KHZhbHVlKQogICAgZXhjZXB0IChUeXBlRXJyb3IsIFZhbHVlRXJyb3IpIGFzIGV4YzoKICAgICAgICByYWlzZSBWYWx1ZUVycm9yKAogICAgICAgICAgICBmIkNvbmZpZyBrZXkge2tleSFyfSBtdXN0IGJlIGEgcG9zaXRpdmUgaW50ZWdlciBvciBlbXB0eSwgZ290IHt2YWx1ZSFyfSIKICAgICAgICApIGZyb20gZXhjCiAgICBpZiBwYXJzZWQgPD0gMDoKICAgICAgICByYWlzZSBWYWx1ZUVycm9yKAogICAgICAgICAgICBmIkNvbmZpZyBrZXkge2tleSFyfSBtdXN0IGJlIGEgcG9zaXRpdmUgaW50ZWdlciBvciBlbXB0eSwgZ290IHt2YWx1ZSFyfSIKICAgICAgICApCiAgICByZXR1cm4gcGFyc2VkCgoKZGVmIF91bml0X2Zsb2F0KHZhbHVlOiBBbnksIGZhbGxiYWNrOiBmbG9hdCkgLT4gZmxvYXQ6CiAgICB0cnk6CiAgICAgICAgcGFyc2VkID0gZmxvYXQodmFsdWUpCiAgICBleGNlcHQgKFR5cGVFcnJvciwgVmFsdWVFcnJvcik6CiAgICAgICAgcmV0dXJuIGZhbGxiYWNrCiAgICByZXR1cm4gcGFyc2VkIGlmIDAuMCA8PSBwYXJzZWQgPD0gMS4wIGVsc2UgZmFsbGJhY2sKCgpkZWYgX2FwcGx5X2FkdmVyc2FyaWFsX2NvbmZpcm1hdGlvbihjb25maWc6IEFueSwgZGF0YTogZGljdFtzdHIsIEFueV0sIGhhcmRlbmVkOiBBbnkpIC0+IE5vbmU6CiAgICBjb25maWcuYWR2ZXJzYXJpYWxfY29uZmlybWF0aW9uX3JldmlldyA9IGhhcmRlbmVkLmJvb2xfdmFsdWUoCiAgICAgICAgZGF0YSwgImFkdmVyc2FyaWFsX2NvbmZpcm1hdGlvbl9yZXZpZXciLCBUcnVlCiAgICApCiAgICBjb25maWcuYWR2ZXJzYXJpYWxfY29uZmlybWF0aW9uX21vZGVsX3N0YWNrID0gX2FzX3N0cmluZ19saXN0KAogICAgICAgIGRhdGEuZ2V0KCJhZHZlcnNhcmlhbF9jb25maXJtYXRpb25fbW9kZWxfc3RhY2siKSwKICAgICAgICBERUZBVUxUX0NPTkZJUk1BVElPTl9NT0RFTFMsCiAgICApCiAgICBjb25maWcucmV2aWV3X3JlYXNvbmluZ19lZmZvcnQgPSBzdHIoCiAgICAgICAgZGF0YS5nZXQoInJldmlld19yZWFzb25pbmdfZWZmb3J0IiwgREVGQVVMVF9SRUFTT05JTkdfRUZGT1JUKQogICAgICAgIG9yIERFRkFVTFRfUkVBU09OSU5HX0VGRk9SVAogICAgKS5zdHJpcCgpCgogICAgdHJ5OgogICAgICAgIGNvbmZpZ3VyZWQgPSBpbnQoCiAgICAgICAgICAgIGdldGF0dHIoY29uZmlnLCAiZml4X3N5bnRoZXNpc19tYXhfZmluZGluZ3MiLCBERUZBVUxUX1ZFUklGSUVSX1JFUEFJUl9MSU1JVCkKICAgICAgICApCiAgICBleGNlcHQgKFR5cGVFcnJvciwgVmFsdWVFcnJvcik6CiAgICAgICAgY29uZmlndXJlZCA9IERFRkFVTFRfVkVSSUZJRVJfUkVQQUlSX0xJTUlUCiAgICB0cnk6CiAgICAgICAgaW5saW5lX2xpbWl0ID0gaW50KGdldGF0dHIoY29uZmlnLCAibWF4X2lubGluZV9jb21tZW50cyIsIGNvbmZpZ3VyZWQpKQogICAgZXhjZXB0IChUeXBlRXJyb3IsIFZhbHVlRXJyb3IpOgogICAgICAgIGlubGluZV9saW1pdCA9IGNvbmZpZ3VyZWQKICAgIHZlcmlmaWVyX3JlcGFpcl9saW1pdCA9IG1heCgxLCBtaW4oY29uZmlndXJlZCwgaW5saW5lX2xpbWl0KSkKCiAgICBmcm9tIGRjb2lyX3JldmlldyBpbXBvcnQgZmluZGluZ192ZXJpZmllciwgcmVwYWlyX3BpcGVsaW5lCgogICAgZmluZGluZ192ZXJpZmllci5WRVJJRklFUl9NQVhfTU9ERUxfRklORElOR1MgPSB2ZXJpZmllcl9yZXBhaXJfbGltaXQKICAgIHJlcGFpcl9waXBlbGluZS5NQVhfUkVQQUlSX0NBTkRJREFURVMgPSB2ZXJpZmllcl9yZXBhaXJfbGltaXQKICAgIGNvbmZpZy5kY29pcl92MzJfdmVyaWZpZXJfcmVwYWlyX2xpbWl0ID0gdmVyaWZpZXJfcmVwYWlyX2xpbWl0CgoKZGVmIF9hcHBseV9zZW1hbnRpY19hZGp1ZGljYXRpb24oY29uZmlnOiBBbnksIGRhdGE6IGRpY3Rbc3RyLCBBbnldLCBoYXJkZW5lZDogQW55KSAtPiBOb25lOgogICAgY29uZmlnLnNlbWFudGljX2FkanVkaWNhdGlvbl9yZXZpZXcgPSBoYXJkZW5lZC5ib29sX3ZhbHVlKAogICAgICAgIGRhdGEsICJzZW1hbnRpY19hZGp1ZGljYXRpb25fcmV2aWV3IiwgVHJ1ZQogICAgKQogICAgY29uZmlnLnNlbWFudGljX2FkanVkaWNhdGlvbl9tb2RlbF9zdGFjayA9IF9hc19zdHJpbmdfbGlzdCgKICAgICAgICBkYXRhLmdldCgic2VtYW50aWNfYWRqdWRpY2F0aW9uX21vZGVsX3N0YWNrIiksCiAgICAgICAgREVGQVVMVF9BREpVRElDQVRJT05fTU9ERUxTLAogICAgKQogICAgY29uZmlndXJlZF9tYXggPSBfcG9zaXRpdmVfaW50KAogICAgICAgIGRhdGEuZ2V0KCJzZW1hbnRpY19hZGp1ZGljYXRpb25fbWF4X2ZpbmRpbmdzIiwgREVGQVVMVF9BREpVRElDQVRJT05fTUFYX0ZJTkRJTkdTKSwKICAgICAgICBERUZBVUxUX0FESlVESUNBVElPTl9NQVhfRklORElOR1MsCiAgICApCiAgICBpbmxpbmVfbWF4ID0gX3Bvc2l0aXZlX2ludCgKICAgICAgICBnZXRhdHRyKGNvbmZpZywgIm1heF9pbmxpbmVfY29tbWVudHMiLCBjb25maWd1cmVkX21heCksCiAgICAgICAgY29uZmlndXJlZF9tYXgsCiAgICApCiAgICBjb25maWcuc2VtYW50aWNfYWRqdWRpY2F0aW9uX21heF9maW5kaW5ncyA9IG1pbihjb25maWd1cmVkX21heCwgaW5saW5lX21heCkKICAgIGNvbmZpZy5zZW1hbnRpY19hZGp1ZGljYXRpb25fY2FuZGlkYXRlX2RpZ2VzdF9jaGFycyA9IF9wb3NpdGl2ZV9pbnQoCiAgICAgICAgZGF0YS5nZXQoCiAgICAgICAgICAgICJzZW1hbnRpY19hZGp1ZGljYXRpb25fY2FuZGlkYXRlX2RpZ2VzdF9jaGFycyIsCiAgICAgICAgICAgIERFRkFVTFRfQ0FORElEQVRFX0RJR0VTVF9DSEFSUywKICAgICAgICApLAogICAgICAgIERFRkFVTFRfQ0FORElEQVRFX0RJR0VTVF9DSEFSUywKICAgICkKCgpkZWYgX2FwcGx5X2NhbmRpZGF0ZV9lc2NhbGF0aW9uKGNvbmZpZzogQW55LCBkYXRhOiBkaWN0W3N0ciwgQW55XSwgaGFyZGVuZWQ6IEFueSkgLT4gTm9uZToKICAgIGNvbmZpZy5jYW5kaWRhdGVfc2NvcGVkX2VzY2FsYXRpb25fcmV2aWV3ID0gaGFyZGVuZWQuYm9vbF92YWx1ZSgKICAgICAgICBkYXRhLCAiY2FuZGlkYXRlX3Njb3BlZF9lc2NhbGF0aW9uX3JldmlldyIsIFRydWUKICAgICkKICAgIGNvbmZpZy5jYW5kaWRhdGVfZXNjYWxhdGlvbl9jb25maWRlbmNlX21hcmdpbiA9IF91bml0X2Zsb2F0KAogICAgICAgIGRhdGEuZ2V0KAogICAgICAgICAgICAiY2FuZGlkYXRlX2VzY2FsYXRpb25fY29uZmlkZW5jZV9tYXJnaW4iLAogICAgICAgICAgICBERUZBVUxUX0NBTkRJREFURV9FU0NBTEFUSU9OX0NPTkZJREVOQ0VfTUFSR0lOLAogICAgICAgICksCiAgICAgICAgREVGQVVMVF9DQU5ESURBVEVfRVNDQUxBVElPTl9DT05GSURFTkNFX01BUkdJTiwKICAgICkKICAgIGNvbmZpZy5jYW5kaWRhdGVfZXNjYWxhdGlvbl9tYXhfcGF0aHMgPSBfcG9zaXRpdmVfaW50KAogICAgICAgIGRhdGEuZ2V0KAogICAgICAgICAgICAiY2FuZGlkYXRlX2VzY2FsYXRpb25fbWF4X3BhdGhzIiwKICAgICAgICAgICAgREVGQVVMVF9DQU5ESURBVEVfRVNDQUxBVElPTl9NQVhfUEFUSFMsCiAgICAgICAgKSwKICAgICAgICBERUZBVUxUX0NBTkRJREFURV9FU0NBTEFUSU9OX01BWF9QQVRIUywKICAgICkKICAgIGNvbmZpZy5jYW5kaWRhdGVfZXNjYWxhdGlvbl9maWxlX2NoYXJzID0gX3Bvc2l0aXZlX2ludCgKICAgICAgICBkYXRhLmdldCgKICAgICAgICAgICAgImNhbmRpZGF0ZV9lc2NhbGF0aW9uX2ZpbGVfY2hhcnMiLAogICAgICAgICAgICBERUZBVUxUX0NBTkRJREFURV9FU0NBTEFUSU9OX0ZJTEVfQ0hBUlMsCiAgICAgICAgKSwKICAgICAgICBERUZBVUxUX0NBTkRJREFURV9FU0NBTEFUSU9OX0ZJTEVfQ0hBUlMsCiAgICApCiAgICBjb25maWcuY2FuZGlkYXRlX2VzY2FsYXRpb25fdG90YWxfY29udGV4dF9jaGFycyA9IF9wb3NpdGl2ZV9pbnQoCiAgICAgICAgZGF0YS5nZXQoCiAgICAgICAgICAgICJjYW5kaWRhdGVfZXNjYWxhdGlvbl90b3RhbF9jb250ZXh0X2NoYXJzIiwKICAgICAgICAgICAgREVGQVVMVF9DQU5ESURBVEVfRVNDQUxBVElPTl9UT1RBTF9DT05URVhUX0NIQVJTLAogICAgICAgICksCiAgICAgICAgREVGQVVMVF9DQU5ESURBVEVfRVNDQUxBVElPTl9UT1RBTF9DT05URVhUX0NIQVJTLAogICAgKQoKCmRlZiBfYXBwbHlfcHVibGljYXRpb25fYW5kX2NvbnRleHQoY29uZmlnOiBBbnksIGRhdGE6IGRpY3Rbc3RyLCBBbnldLCBoYXJkZW5lZDogQW55KSAtPiBOb25lOgogICAgY29uZmlnLnZlcmlmaWVyX2F1dGhvcml0YXRpdmVfcHVibGljYXRpb25fcmV2aWV3ID0gaGFyZGVuZWQuYm9vbF92YWx1ZSgKICAgICAgICBkYXRhLCAidmVyaWZpZXJfYXV0aG9yaXRhdGl2ZV9wdWJsaWNhdGlvbl9yZXZpZXciLCBUcnVlCiAgICApCiAgICBjb25maWcuY2Fub25pY2FsX3NlbWFudGljX2NvbnRleHRfcmV2aWV3ID0gaGFyZGVuZWQuYm9vbF92YWx1ZSgKICAgICAgICBkYXRhLCAiY2Fub25pY2FsX3NlbWFudGljX2NvbnRleHRfcmV2aWV3IiwgVHJ1ZQogICAgKQogICAgY29uZmlnLmFkYXB0aXZlX3NlbWFudGljX2J1ZGdldHNfcmV2aWV3ID0gaGFyZGVuZWQuYm9vbF92YWx1ZSgKICAgICAgICBkYXRhLCAiYWRhcHRpdmVfc2VtYW50aWNfYnVkZ2V0c19yZXZpZXciLCBUcnVlCiAgICApCiAgICBmb3Iga2V5LCBmYWxsYmFjayBpbiBBREFQVElWRV9TRU1BTlRJQ19ERUZBVUxUUy5pdGVtcygpOgogICAgICAgIHNldGF0dHIoY29uZmlnLCBrZXksIF9wb3NpdGl2ZV9pbnQoZGF0YS5nZXQoa2V5LCBmYWxsYmFjayksIGZhbGxiYWNrKSkKICAgIGNvbmZpZy52ZXJpZmllZF9maW5kaW5nX2dhdGVfc3RhdGVfcmV2aWV3ID0gaGFyZGVuZWQuYm9vbF92YWx1ZSgKICAgICAgICBkYXRhLCAidmVyaWZpZWRfZmluZGluZ19nYXRlX3N0YXRlX3JldmlldyIsIFRydWUKICAgICkKICAgIGNvbmZpZy5zZW1hbnRpY19jYW5kaWRhdGVfaWRlbnRpdHlfcmV2aWV3ID0gaGFyZGVuZWQuYm9vbF92YWx1ZSgKICAgICAgICBkYXRhLCAic2VtYW50aWNfY2FuZGlkYXRlX2lkZW50aXR5X3JldmlldyIsIFRydWUKICAgICkKCgpkZWYgX2FwcGx5X3Blcl9maWxlX3JvdXRpbmcoY29uZmlnOiBBbnksIGRhdGE6IGRpY3Rbc3RyLCBBbnldKSAtPiBOb25lOgogICAgY29uZmlnLnBlcl9maWxlX3Jldmlld19tb2RlbF9zdGFjayA9IF9vcHRpb25hbF9zdHJpbmdfbGlzdCgKICAgICAgICBkYXRhLmdldCgicGVyX2ZpbGVfcmV2aWV3X21vZGVsX3N0YWNrIikKICAgICkKICAgIGVmZm9ydCA9IHN0cihkYXRhLmdldCgicGVyX2ZpbGVfcmV2aWV3X3JlYXNvbmluZ19lZmZvcnQiLCAiIikgb3IgIiIpLnN0cmlwKCkKICAgIGNvbmZpZy5wZXJfZmlsZV9yZXZpZXdfcmVhc29uaW5nX2VmZm9ydCA9IGVmZm9ydCBvciBOb25lCiAgICBjb25maWcucGVyX2ZpbGVfcmV2aWV3X21heF90b2tlbnMgPSBfb3B0aW9uYWxfcG9zaXRpdmVfaW50KAogICAgICAgIGRhdGEuZ2V0KCJwZXJfZmlsZV9yZXZpZXdfbWF4X3Rva2VucyIpLAogICAgICAgICJwZXJfZmlsZV9yZXZpZXdfbWF4X3Rva2VucyIsCiAgICApCiAgICBjb25maWcucGVyX2ZpbGVfcmV2aWV3X3Byb3ZpZGVyX3NvcnQgPSBzdHIoCiAgICAgICAgZGF0YS5nZXQoInBlcl9maWxlX3Jldmlld19wcm92aWRlcl9zb3J0IiwgIiIpIG9yICIiCiAgICApLnN0cmlwKCkKCgpkZWYgX2luaXRpYWxpemVfcnVuX3RlbGVtZXRyeV9mYWlsX3NvZnQoY29uZmlnOiBBbnkpIC0+IE5vbmU6CiAgICB0cnk6CiAgICAgICAgaW1wb3J0IGRjb2lyX3Jldmlld19yZXF1aXJlZF9ydW50aW1lX3BhdGNoX3Y1NCBhcyB0ZWxlbWV0cnkKCiAgICAgICAgdGVsZW1ldHJ5Ll9lbnN1cmVfc2luayhjb25maWcpCiAgICBleGNlcHQgRXhjZXB0aW9uOgogICAgICAgIHRyeToKICAgICAgICAgICAgdGVsZW1ldHJ5Ll9ub3RlX3RlbGVtZXRyeV9lcnJvcihjb25maWcpCiAgICAgICAgZXhjZXB0IEV4Y2VwdGlvbjoKICAgICAgICAgICAgcGFzcwoKCmRlZiBfYXBwbHlfcmVwYWlyX2NyaXRpY19iYXRjaGluZyhjb25maWc6IEFueSwgZGF0YTogZGljdFtzdHIsIEFueV0sIGhhcmRlbmVkOiBBbnkpIC0+IE5vbmU6CiAgICBjb25maWcucmVwYWlyX2NyaXRpY19iYXRjaGluZ19lbmFibGVkID0gaGFyZGVuZWQuYm9vbF92YWx1ZSgKICAgICAgICBkYXRhLCAicmVwYWlyX2NyaXRpY19iYXRjaGluZ19lbmFibGVkIiwgVHJ1ZQogICAgKQogICAgcmF3X2xpbWl0ID0gZGF0YS5nZXQoCiAgICAgICAgInJlcGFpcl9jcml0aWNfYmF0Y2hfbWF4X2ZpbmRpbmdzIiwKICAgICAgICBERUZBVUxUX1JFUEFJUl9DUklUSUNfQkFUQ0hfTUFYX0ZJTkRJTkdTLAogICAgKQogICAgdHJ5OgogICAgICAgIGNvbmZpZy5yZXBhaXJfY3JpdGljX2JhdGNoX21heF9maW5kaW5ncyA9IGludChyYXdfbGltaXQpCiAgICBleGNlcHQgKFR5cGVFcnJvciwgVmFsdWVFcnJvcikgYXMgZXhjOgogICAgICAgIHJhaXNlIFZhbHVlRXJyb3IoCiAgICAgICAgICAgICJDb25maWcga2V5ICdyZXBhaXJfY3JpdGljX2JhdGNoX21heF9maW5kaW5ncycgbXVzdCBiZSBhbiBpbnRlZ2VyIgogICAgICAgICkgZnJvbSBleGMKCgpkZWYgYXBwbHlfcmV2aWV3X2NvbmZpZyhjb25maWc6IEFueSwgZGF0YTogZGljdFtzdHIsIEFueV0sIGhhcmRlbmVkOiBBbnkpIC0+IEFueToKICAgICIiIkFwcGx5IGFsbCBwb3N0LWJhc2UgRENPSVIgY29uZmlndXJhdGlvbiBleGFjdGx5IG9uY2UuIiIiCgogICAgX2FwcGx5X2FkdmVyc2FyaWFsX2NvbmZpcm1hdGlvbihjb25maWcsIGRhdGEsIGhhcmRlbmVkKQogICAgX2FwcGx5X3NlbWFudGljX2FkanVkaWNhdGlvbihjb25maWcsIGRhdGEsIGhhcmRlbmVkKQogICAgX2FwcGx5X2NhbmRpZGF0ZV9lc2NhbGF0aW9uKGNvbmZpZywgZGF0YSwgaGFyZGVuZWQpCiAgICBfYXBwbHlfcHVibGljYXRpb25fYW5kX2NvbnRleHQoY29uZmlnLCBkYXRhLCBoYXJkZW5lZCkKICAgIF9hcHBseV9wZXJfZmlsZV9yb3V0aW5nKGNvbmZpZywgZGF0YSkKICAgIF9pbml0aWFsaXplX3J1bl90ZWxlbWV0cnlfZmFpbF9zb2Z0KGNvbmZpZykKICAgIF9hcHBseV9yZXBhaXJfY3JpdGljX2JhdGNoaW5nKGNvbmZpZywgZGF0YSwgaGFyZGVuZWQpCiAgICByZXR1cm4gY29uZmlnCg=="
).decode("utf-8")

preview_result = run(sys.executable, str(preview), cwd=repo, check=False)
if preview_result.returncode:
    raise SystemExit(preview_result.returncode)
if not base_patch.is_file():
    raise RuntimeError("complete canonical-config preview patch missing")

run("git", "-C", str(repo), "fetch", "--no-tags", "origin", f"+refs/heads/{BRANCH}:refs/remotes/origin/{BRANCH}")
if run("git", "-C", str(repo), "rev-parse", f"refs/remotes/origin/{BRANCH}").stdout.strip() != HEAD:
    raise RuntimeError("PR head drift")
if run("git", "-C", str(repo), "rev-parse", f"{HEAD}^{{tree}}").stdout.strip() != TREE:
    raise RuntimeError("PR tree drift")
if worktree.exists():
    run("git", "-C", str(repo), "worktree", "remove", "--force", str(worktree), check=False)
run("git", "-C", str(repo), "worktree", "add", "--detach", str(worktree), HEAD)
try:
    run("git", "apply", "--check", str(base_patch), cwd=worktree)
    run("git", "apply", str(base_patch), cwd=worktree)
    review_config = worktree / ".github/dcoir_review/scripts/dcoir_review/review_config.py"
    review_config.write_text(readable_config, encoding="utf-8", newline="\n")
    run("git", "add", "-N", ".github/dcoir_review/scripts/dcoir_review/review_config.py", cwd=worktree)

    source = review_config.read_text(encoding="utf-8")
    tree = ast.parse(source)
    required_helpers = {
        "_as_string_list", "_optional_string_list", "_positive_int",
        "_optional_positive_int", "_unit_float", "_apply_adversarial_confirmation",
        "_apply_semantic_adjudication", "_apply_candidate_escalation",
        "_apply_publication_and_context", "_apply_per_file_routing",
        "_initialize_run_telemetry_fail_soft", "_apply_repair_critic_batching",
        "apply_review_config",
    }
    names = {node.name for node in tree.body if isinstance(node, ast.FunctionDef)}
    if not required_helpers.issubset(names):
        raise RuntimeError(f"readable canonical config helper set incomplete: {sorted(required_helpers - names)}")
    if len(source.encode("utf-8")) > 12000:
        raise RuntimeError("readable canonical review_config.py exceeds 12 KB bounded owner target")
    if ";" in source:
        raise RuntimeError("readable canonical review_config.py still contains semicolon-packed statements")

    changed = run("git", "diff", "--name-only", "HEAD", cwd=worktree).stdout.splitlines()
    changed_py = [path for path in changed if path.endswith(".py") and (worktree / path).is_file()]
    if ".github/dcoir_review/scripts/dcoir_review/review_config.py" not in changed:
        raise RuntimeError("readable review_config.py missing from transformed change set")
    run(sys.executable, "-m", "py_compile", *changed_py, cwd=worktree)
    run("git", "diff", "--check", cwd=worktree)

    focused = [
        "dcoir_review_required_runtime_patch_v32_selftest.py",
        "dcoir_review_required_runtime_patch_v35_selftest.py",
        "dcoir_review_required_runtime_patch_v44_scope_selftest.py",
        "dcoir_review_required_runtime_patch_v44_selftest.py",
        "dcoir_review_publication_disposition_selftest.py",
        "dcoir_review_required_runtime_patch_v46_selftest.py",
        "dcoir_review_verified_finding_gate_selftest.py",
        "dcoir_review_semantic_candidate_identity_selftest.py",
        "dcoir_review_per_file_routing_selftest.py",
        "dcoir_review_required_runtime_patch_v54_selftest.py",
        "dcoir_review_required_runtime_patch_v56_selftest.py",
        "dcoir_review_runtime_module_loader_selftest.py",
        "dcoir_review_architecture_b_benchmark_selftest.py",
        "dcoir_review_semantic_recall_corpus_selftest.py",
        "dcoir_review_precision_regression_selftest.py",
    ]
    for test in focused:
        run(sys.executable, str(Path(".github/dcoir_review/scripts") / test), cwd=worktree)

    semantic = run(sys.executable, ".github/dcoir_review/scripts/dcoir_review_semantic_recall_corpus_selftest.py", cwd=worktree).stdout
    if "12 cases, 10 finding classes, 2 clean classes" not in semantic:
        raise RuntimeError("semantic recall summary changed")
    precision = json.loads(run(sys.executable, ".github/dcoir_review/scripts/dcoir_review_precision_regression_selftest.py", cwd=worktree).stdout)
    if float(precision["false_positive_suppression_rate"]) != 1.0:
        raise RuntimeError("false-positive suppression changed")
    if float(precision["true_positive_retention_rate"]) != 1.0:
        raise RuntimeError("true-positive retention changed")
    if precision.get("regressions"):
        raise RuntimeError(f"precision regressions: {precision['regressions']}")

    owner_probe = (
        "import sys;from pathlib import Path;"
        "p=Path('.github/dcoir_review/scripts').resolve();sys.path.insert(0,str(p));"
        "from dcoir_review.entrypoint import DcoirReviewEntrypoint as E;"
        "e=E();m=e.import_module(e.review_module_name);e.apply_runtime_patches(m);"
        "assert m.load_pareto_context_config.__module__==e.review_module_name;"
        "print(m.load_pareto_context_config.__module__)"
    )
    run(sys.executable, "-c", owner_probe, cwd=worktree)

    out_patch.write_bytes(subprocess.check_output(["git", "diff", "--binary", "HEAD"], cwd=worktree))
    patch_text = out_patch.read_text(encoding="utf-8")
    if "dcoir_review/review_config.py" not in patch_text or "new file mode 100644" not in patch_text:
        raise RuntimeError("readable preview patch omitted canonical review_config.py")
    summary.write_text(
        "\n".join([
            "result=PASS",
            f"exact_head={HEAD}",
            f"exact_tree={TREE}",
            "canonical_config_loader=openrouter_pr_review_pareto_context.load_pareto_context_config",
            "canonical_config_helper=dcoir_review.review_config.apply_review_config",
            "removed_runtime_config_wrappers=10",
            f"review_config_bytes={len(source.encode('utf-8'))}",
            f"review_config_functions={len(names)}",
            "focused_tests=15",
            "semantic_recall=12/10/2",
            "precision_false_positive_suppression=1.0",
            "precision_true_positive_retention=1.0",
            "no_inference=true",
            "no_provider_calls=true",
        ]) + "\n",
        encoding="utf-8",
    )
    print(summary.read_text(encoding="utf-8"), end="")
finally:
    run("git", "-C", str(repo), "worktree", "remove", "--force", str(worktree), check=False)

print("ISSUE550_PR553_CANONICAL_CONFIG_READABLE_PREVIEW_009_PASS")
