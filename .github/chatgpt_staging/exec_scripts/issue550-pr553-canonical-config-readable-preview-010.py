from __future__ import annotations

import base64
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

repo = Path(os.environ.get("DCOIR_REPO_ROOT") or os.environ.get("GITHUB_WORKSPACE") or ".").resolve()
downloads = Path(os.environ.get("DCOIR_DOWNLOADS_DIR") or os.environ.get("RUNNER_TEMP") or tempfile.gettempdir()).resolve()
source_path = repo / ".github/chatgpt_staging/exec_scripts/issue550-pr553-canonical-config-readable-preview-009.py"
corrected_path = downloads / "issue550-pr553-canonical-config-readable-preview-010-inner.py"

source = source_path.read_text(encoding="utf-8")
pattern = re.compile(
    r'(readable_config\s*=\s*base64\.b64decode\(\s*")([A-Za-z0-9+/=]+)("\s*\)\.decode\([^\n]+\))',
    re.DOTALL,
)
match = pattern.search(source)
if match is None:
    raise SystemExit("readable_config base64 anchor missing")

decoded = base64.b64decode(match.group(2)).decode("utf-8")
old = "DEFAUL_REASONING_EFFORT"
new = "DEFAULT_REASONING_EFFORT"
if decoded.count(old) != 1:
    raise SystemExit(f"expected exactly one readable-config typo, found {decoded.count(old)}")
decoded = decoded.replace(old, new, 1)
encoded = base64.b64encode(decoded.encode("utf-8")).decode("ascii")
corrected = source[: match.start(2)] + encoded + source[match.end(2) :]
corrected = corrected.replace(
    'summary = downloads / "issue550-pr553-canonical-config-readable-preview-009-summary.txt"',
    'summary = downloads / "issue550-pr553-canonical-config-readable-preview-010-summary.txt"',
    1,
)
corrected = corrected.replace(
    'out_patch = downloads / "issue550-pr553-canonical-config-readable-preview-009.patch"',
    'out_patch = downloads / "issue550-pr553-canonical-config-readable-preview-010.patch"',
    1,
)
corrected_path.write_text(corrected, encoding="utf-8", newline="\n")

completed = subprocess.run([sys.executable, str(corrected_path)], cwd=repo, text=True)
if completed.returncode:
    raise SystemExit(completed.returncode)

summary = downloads / "issue550-pr553-canonical-config-readable-preview-010-summary.txt"
if not summary.is_file():
    raise SystemExit("corrected readable preview summary missing")
with summary.open("a", encoding="utf-8") as handle:
    handle.write("readable_config_typo_fixed=true\n")
print(summary.read_text(encoding="utf-8"), end="")
print("ISSUE550_PR553_CANONICAL_CONFIG_READABLE_PREVIEW_010_PASS")
