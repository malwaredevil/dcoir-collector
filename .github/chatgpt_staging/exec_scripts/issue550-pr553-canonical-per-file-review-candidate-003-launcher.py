from __future__ import annotations

import base64
import gzip
from pathlib import Path

payload = Path(
    ".github/chatgpt_staging/exec_payloads/"
    "issue550-pr553-canonical-per-file-review-candidate-001.py.gz.b64"
)
source = gzip.decompress(base64.b64decode(payload.read_text(encoding="utf-8"))).decode("utf-8")
source = source.replace(
    "issue550-pr553-canonical-per-file-review-candidate-001",
    "issue550-pr553-canonical-per-file-review-candidate-003",
).replace(
    "ISSUE550_PR553_CANONICAL_PER_FILE_REVIEW_CANDIDATE_001_PASS",
    "ISSUE550_PR553_CANONICAL_PER_FILE_REVIEW_CANDIDATE_003_PASS",
)
old = '''    run("git", "diff", "--check", cwd=worktree)\n    patch = run("git", "diff", "--binary", cwd=worktree).stdout\n'''
new = '''    run("git", "add", "-N", ".github/dcoir_review/scripts/dcoir_review/per_file_review.py", cwd=worktree)\n    run("git", "diff", "--check", cwd=worktree)\n    patch = run("git", "diff", "--binary", cwd=worktree).stdout\n'''
if old not in source:
    raise RuntimeError("candidate exporter anchor not found")
source = source.replace(old, new, 1)
exec(compile(source, "issue550-per-file-candidate-003.py", "exec"), {"__name__": "__main__"})
