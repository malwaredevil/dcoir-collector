from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path

repo = Path(os.environ.get("DCOIR_REPO_ROOT") or os.environ.get("GITHUB_WORKSPACE") or ".").resolve()
source_path = repo / ".github/chatgpt_staging/exec_scripts/issue550-pr553-canonical-review-config-validation-001.py"
downloads = Path(os.environ.get("DCOIR_DOWNLOADS_DIR") or os.environ.get("RUNNER_TEMP") or tempfile.gettempdir()).resolve()
inner = downloads / "issue550-pr553-canonical-review-config-validation-004-inner.py"

source = source_path.read_text(encoding="utf-8")
replacements = {
    'EXPECTED_HEAD = "1210e9689200c7a97a8b48c0d6a1dc792675700d"':
        'EXPECTED_HEAD = "f10aa75bbdf54110329409371d7aa86404b6ba65"',
    'EXPECTED_TREE = "72b50e19e9da8eaaf566a79726a6615442c9c94c"':
        'EXPECTED_TREE = "91021d85eec18569fe52492c13959cd8b28a0331"',
    'REQUEST_ID = "issue550-pr553-canonical-review-config-validation-001"':
        'REQUEST_ID = "issue550-pr553-canonical-review-config-validation-004"',
    'TERMINAL = "ISSUE550_PR553_CANONICAL_REVIEW_CONFIG_VALIDATION_001_PASS"':
        'TERMINAL = "ISSUE550_PR553_CANONICAL_REVIEW_CONFIG_VALIDATION_004_PASS"',
    'if len(commands) != 56:\n        raise RuntimeError(f"expected 56 governed Python commands, observed {len(commands)}")':
        'if len(commands) != 59:\n        raise RuntimeError(f"expected 59 governed validation commands, observed {len(commands)}")',
}
for old, new in replacements.items():
    if source.count(old) != 1:
        raise SystemExit(f"exact-head replacement anchor count for {old!r}: {source.count(old)}")
    source = source.replace(old, new, 1)

loop_old = '''        if argv[0] in {"python", "python3"}:\n            argv[0] = sys.executable\n        print(f"=== Registry {index:02d}/59 {command} ===")\n        run(*argv, cwd=worktree)\n'''
loop_new = '''        if argv[0] in {"python", "python3"}:\n            argv[0] = sys.executable\n        elif argv[0] == "bash":\n            git_for_registry = shutil.which("git")\n            if not git_for_registry:\n                raise RuntimeError("git executable not found for governed bash command")\n            git_root_for_registry = Path(git_for_registry).resolve().parent.parent\n            git_bash_for_registry = git_root_for_registry / "bin" / "bash.exe"\n            if not git_bash_for_registry.is_file():\n                raise RuntimeError(f"Git-for-Windows bash not found: {git_bash_for_registry}")\n            argv[0] = str(git_bash_for_registry)\n        print(f"=== Registry {index:02d}/59 {command} ===")\n        run(*argv, cwd=worktree)\n'''
if source.count(loop_old) != 1:
    raise SystemExit(f"registry loop replacement anchor count={source.count(loop_old)}")
source = source.replace(loop_old, loop_new, 1)

inner.write_text(source, encoding="utf-8", newline="\n")
compile(inner.read_text(encoding="utf-8"), str(inner), "exec")
cp = subprocess.run([sys.executable, str(inner)], cwd=repo, text=True)
if cp.returncode:
    raise SystemExit(cp.returncode)
print("CANONICAL_REVIEW_CONFIG_VALIDATION_004_WRAPPER_PASS")
