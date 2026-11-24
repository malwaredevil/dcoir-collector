from __future__ import annotations
import os
import tempfile
from pathlib import Path

p = Path('.github/chatgpt_staging/exec_scripts/issue550-pr553-canonical-config-consolidation-preview-v54-test-fix-005.py')
source = p.read_text(encoding='utf-8')
anchor = '\ntest_anchor = "changed=run(\'git\',\'diff\',\'--name-only\',cwd=wt).stdout.splitlines()"\n'
if anchor not in source:
    raise SystemExit('v54-test-fix-005 test anchor missing')
source = source.replace(
    anchor,
    '\nfixture_transform += "run(\'git\',\'add\',\'-N\',\'.github/dcoir_review/scripts/dcoir_review/review_config.py\',cwd=wt)\\n"\n' + anchor,
    1,
)
exec(compile(source, str(p), 'exec'), {'__name__': '__main__'})
out = Path(os.environ.get('DCOIR_DOWNLOADS_DIR') or os.environ.get('RUNNER_TEMP') or tempfile.gettempdir())
patch = out / 'issue550-pr553-canonical-config-consolidation-preview-001.patch'
text = patch.read_text(encoding='utf-8')
needle = 'diff --git a/.github/dcoir_review/scripts/dcoir_review/review_config.py b/.github/dcoir_review/scripts/dcoir_review/review_config.py'
if needle not in text:
    raise SystemExit('generated patch omitted new canonical review_config.py')
if 'new file mode 100644' not in text[text.index(needle):text.index(needle)+400]:
    raise SystemExit('review_config.py is not represented as a new file in generated patch')
print('COMPLETE_PATCH_EXPORT_GUARD_PASS')
