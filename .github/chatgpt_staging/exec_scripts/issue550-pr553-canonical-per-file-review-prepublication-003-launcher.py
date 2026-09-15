from __future__ import annotations

import base64
import gzip
from pathlib import Path

payload = Path(
    ".github/chatgpt_staging/exec_payloads/"
    "issue550-pr553-canonical-per-file-review-prepublication-003.py.gz.b64"
)
source = gzip.decompress(base64.b64decode(payload.read_text(encoding="utf-8"))).decode("utf-8")
exec(compile(source, "issue550-pr553-canonical-per-file-review-prepublication-003.py", "exec"), {"__name__": "__main__"})
