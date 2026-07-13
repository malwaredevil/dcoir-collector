$ErrorActionPreference = 'Stop'
$repo = $env:DCOIR_REPO_ROOT
if ([string]::IsNullOrWhiteSpace($repo)) { throw 'DCOIR_REPO_ROOT is not set' }
Set-Location $repo

git config user.name 'chatgpt-exec'
git config user.email 'chatgpt-exec@users.noreply.github.com'
git pull --ff-only origin main

$py = @'
from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

repo = Path.cwd()
source_root = repo / 'project_sources/gemini/bundle_source'
prime_rel = '01_GEMINI_AGENT_BUILD/Prime_Agent_DCOIR_Gemini_Orchestrator.md.txt'
prime_path = source_root / prime_rel
manifest_path = source_root / 'Gemini_Bundle_Source_Manifest.json'
compile_path = repo / 'project_sources/gemini/tools/compile_dcoir_gemini_bundle.py'
validate_path = repo / 'project_sources/gemini/tools/validate_dcoir_gemini_bundle.py'
build_path = repo / 'project_sources/gemini/tools/build_dcoir_gemini_release.py'
doc10 = repo / 'project_sources/gemini/docs/DOC-10_DCOIR_Gemini_Stored_Source_And_Compile_Strategy_v1_0_0.txt'
doc11 = repo / 'project_sources/gemini/docs/DOC-11_DCOIR_Gemini_Creation_Pipeline_v1_0_0.txt'

# 1. Manifest migration: chunks become editable source; monolithic prime becomes generated runtime artifact.
manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
chunk_manifest_rel = manifest.get('prime_agent_chunk_manifest') or manifest.get('topology', {}).get('prime_agent_chunk_manifest')
if not chunk_manifest_rel:
    raise SystemExit('Missing prime agent chunk manifest reference')
chunk_sources = list(manifest.get('topology', {}).get('prime_agent_chunk_sources', []))
if not chunk_sources:
    raise SystemExit('Missing prime agent chunk sources')
manifest['prime_agent_source_mode'] = 'chunked_reassembled'
manifest['prime_agent_runtime_mode'] = 'generated_from_chunks'
manifest['prime_agent_chunk_manifest'] = chunk_manifest_rel
manifest['runtime_generated_files'] = [prime_rel]
source_only_dirs = list(dict.fromkeys(list(manifest.get('source_only_dirs', [])) + ['01_GEMINI_AGENT_BUILD/prime_agent_chunks']))
manifest['source_only_dirs'] = source_only_dirs
source_only_files = list(dict.fromkeys(list(manifest.get('source_only_files', [])) + [chunk_manifest_rel, *chunk_sources]))
manifest['source_only_files'] = source_only_files
manifest['topology']['prime_agent_file'] = prime_rel
manifest['topology']['prime_agent_runtime_mode'] = 'generated_from_chunks'
manifest['topology']['prime_agent_chunk_manifest'] = chunk_manifest_rel
manifest['topology']['prime_agent_chunk_sources'] = chunk_sources
required = list(manifest.get('required_files', []))
required = [rel for rel in required if rel != prime_rel]
for rel in [chunk_manifest_rel, *chunk_sources]:
    if rel not in required:
        required.append(rel)
manifest['required_files'] = required
manifest_path.write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')

# 2. Patch compiler to understand source-only files/dirs and generated runtime files.
compile_text = compile_path.read_text(encoding='utf-8')
compile_text = compile_text.replace(
"def iter_source_files(source_root: Path, generated_dir: str) -> Iterable[Path]:\n    generated_root = source_root / generated_dir\n    for path in sorted(source_root.rglob('*')):\n        if not path.is_file():\n            continue\n        if path.name in EXCLUDE:\n            continue\n        try:\n            path.relative_to(generated_root)\n            continue\n        except ValueError:\n            pass\n        yield path\n",
"def is_under(path: Path, root: Path) -> bool:\n    try:\n        path.relative_to(root)\n        return True\n    except ValueError:\n        return False\n\n\ndef iter_source_files(source_root: Path, generated_dir: str, source_only_files: set[str], source_only_dirs: set[str]) -> Iterable[Path]:\n    generated_root = source_root / generated_dir\n    source_only_dir_paths = [source_root / rel for rel in source_only_dirs]\n    for path in sorted(source_root.rglob('*')):\n        if not path.is_file():\n            continue\n        if path.name in EXCLUDE:\n            continue\n        rel = path.relative_to(source_root).as_posix()\n        if rel in source_only_files:\n            continue\n        if any(is_under(path, root) for root in source_only_dir_paths):\n            continue\n        if is_under(path, generated_root):\n            continue\n        yield path\n"
)
compile_text = compile_text.replace(
"    knowledge_sources = list(manifest.get('knowledge_attachment_sources', []))\n\n    required = manifest.get('required_files', [])\n    missing = []\n",
"    knowledge_sources = list(manifest.get('knowledge_attachment_sources', []))\n    source_only_files = set(manifest.get('source_only_files', []))\n    source_only_dirs = set(manifest.get('source_only_dirs', []))\n    runtime_generated_files = list(manifest.get('runtime_generated_files', []))\n\n    required = manifest.get('required_files', [])\n    missing = []\n"
)
compile_text = compile_text.replace(
"    for rel in knowledge_sources:\n        if not (repo_root / rel).exists():\n            missing.append(rel)\n    if missing:\n        raise SystemExit('Missing required source files: ' + ', '.join(missing))\n",
"    for rel in knowledge_sources:\n        if not (repo_root / rel).exists():\n            missing.append(rel)\n    for rel in runtime_generated_files:\n        if not (source_root / rel).exists():\n            missing.append(rel)\n    if missing:\n        raise SystemExit('Missing required source files: ' + ', '.join(missing))\n"
)
compile_text = compile_text.replace(
"        for path in iter_source_files(source_root, generated_dir):\n",
"        for path in iter_source_files(source_root, generated_dir, source_only_files, source_only_dirs):\n"
)
compile_text = compile_text.replace(
"        'source_strategy': manifest.get('source_strategy'),\n",
"        'source_strategy': manifest.get('source_strategy'),\n        'prime_agent_source_mode': manifest.get('prime_agent_source_mode'),\n        'prime_agent_runtime_mode': manifest.get('prime_agent_runtime_mode'),\n        'runtime_generated_files': runtime_generated_files,\n        'source_only_files': sorted(source_only_files),\n        'source_only_dirs': sorted(source_only_dirs),\n"
)
compile_path.write_text(compile_text, encoding='utf-8')

# 3. Patch validator so chunked mode allows the canonical prime to be generated, not committed.
validate_text = validate_path.read_text(encoding='utf-8')
validate_text = validate_text.replace(
"    topology = manifest.get('topology', {})\n    prime_rel = topology.get('prime_agent_file')\n    sub_rel_list = list(topology.get('sub_agent_files', []))\n",
"    topology = manifest.get('topology', {})\n    prime_rel = topology.get('prime_agent_file')\n    sub_rel_list = list(topology.get('sub_agent_files', []))\n    prime_source_mode = manifest.get('prime_agent_source_mode')\n    prime_runtime_mode = manifest.get('prime_agent_runtime_mode')\n    source_only_files = set(manifest.get('source_only_files', []))\n    source_only_dirs = set(manifest.get('source_only_dirs', []))\n    runtime_generated_files = list(manifest.get('runtime_generated_files', []))\n    checks['prime_agent_source_mode'] = prime_source_mode\n    checks['prime_agent_runtime_mode'] = prime_runtime_mode\n    checks['runtime_generated_files'] = runtime_generated_files\n    checks['source_only_files'] = sorted(source_only_files)\n    checks['source_only_dirs'] = sorted(source_only_dirs)\n"
)
validate_text = validate_text.replace(
"    if prime_rel and discovered_prime != [prime_rel]:\n        errors.append('prime agent file discovered in source tree does not match manifest topology')\n    if sorted(sub_rel_list) != discovered_sub:\n        errors.append('discovered sub-agent files do not exactly match manifest topology')\n    checks['topology_exact_match'] = bool(prime_rel and discovered_prime == [prime_rel] and sorted(sub_rel_list) == discovered_sub)\n\n\n    prime_source_mode = manifest.get('prime_agent_source_mode')\n    checks['prime_agent_source_mode'] = prime_source_mode\n",
"    if prime_source_mode == 'chunked_reassembled' and prime_runtime_mode == 'generated_from_chunks':\n        allowed_prime_discovery = (discovered_prime == [] or discovered_prime == [prime_rel])\n        if not allowed_prime_discovery:\n            errors.append('chunked prime agent mode allows zero or one generated canonical prime file only')\n        if prime_rel not in runtime_generated_files:\n            errors.append('runtime_generated_files must include manifest topology prime_agent_file in chunked mode')\n    else:\n        if prime_rel and discovered_prime != [prime_rel]:\n            errors.append('prime agent file discovered in source tree does not match manifest topology')\n        allowed_prime_discovery = bool(prime_rel and discovered_prime == [prime_rel])\n    if sorted(sub_rel_list) != discovered_sub:\n        errors.append('discovered sub-agent files do not exactly match manifest topology')\n    checks['topology_exact_match'] = bool(prime_rel and allowed_prime_discovery and sorted(sub_rel_list) == discovered_sub)\n\n\n"
)
validate_text = validate_text.replace(
"                canonical = (source_root / prime_rel).read_text(encoding='utf-8') if prime_rel and (source_root / prime_rel).exists() else ''\n                checks['prime_agent_chunk_reassembly_matches_canonical'] = assembled == canonical\n                if assembled != canonical:\n                    errors.append('prime agent chunk reassembly does not match canonical prime agent file')\n",
"                canonical_path = (source_root / prime_rel) if prime_rel else None\n                canonical_exists = bool(canonical_path and canonical_path.exists())\n                checks['prime_agent_generated_canonical_exists'] = canonical_exists\n                if canonical_exists:\n                    canonical = canonical_path.read_text(encoding='utf-8')\n                    checks['prime_agent_chunk_reassembly_matches_canonical'] = assembled == canonical\n                    if assembled != canonical:\n                        errors.append('prime agent chunk reassembly does not match canonical prime agent file')\n                else:\n                    checks['prime_agent_chunk_reassembly_matches_canonical'] = True\n                    checks['prime_agent_chunk_reassembly_sha256_only'] = True\n                if '```' in assembled and assembled.count('```') % 2 != 0:\n                    errors.append('reassembled prime agent has unbalanced markdown code fences')\n                if 'Prime_Agent_Chunks_Manifest' in assembled or 'prime_agent_chunks/' in assembled:\n                    errors.append('reassembled prime agent appears to contain source-only chunk metadata')\n                if assembled.count('Agent name:') != 1 or assembled.count('Agent description:') != 1:\n                    errors.append('reassembled prime agent must contain exactly one Agent name and one Agent description block')\n"
)
validate_path.write_text(validate_text, encoding='utf-8')

# 4. Patch build script to inspect final Gemini ZIP for generated-prime contract and source-only leakage.
build_text = build_path.read_text(encoding='utf-8')
if 'inspect_gemini_zip_contract' not in build_text:
    build_text = build_text.replace('import sys\nfrom pathlib import Path\n', 'import sys\nimport zipfile\nfrom pathlib import Path\n')
    build_text = build_text.replace(
"def write_report(output_dir: Path, report: dict) -> None:\n    report_path = output_dir / 'build_dcoir_gemini_release_report.json'\n    report_path.write_text(json.dumps(report, indent=2), encoding='utf-8')\n    print(json.dumps(report, indent=2))\n\n\ndef main() -> int:\n",
"def write_report(output_dir: Path, report: dict) -> None:\n    report_path = output_dir / 'build_dcoir_gemini_release_report.json'\n    report_path.write_text(json.dumps(report, indent=2), encoding='utf-8')\n    print(json.dumps(report, indent=2))\n\n\ndef inspect_gemini_zip_contract(output_dir: Path, manifest: dict) -> dict:\n    bundle_name = manifest['bundle_name']\n    zips = sorted(output_dir.glob(f'{bundle_name}_*.zip'))\n    if not zips:\n        return {'success': False, 'error': 'no Gemini bundle zip found'}\n    zip_path = zips[-1]\n    prime_rel = manifest.get('topology', {}).get('prime_agent_file')\n    source_only_dirs = tuple(rel.rstrip('/') + '/' for rel in manifest.get('source_only_dirs', []))\n    source_only_files = set(manifest.get('source_only_files', []))\n    with zipfile.ZipFile(zip_path) as zf:\n        names = zf.namelist()\n    payload_rels = []\n    for name in names:\n        parts = name.split('/', 1)\n        payload_rels.append(parts[1] if len(parts) == 2 else name)\n    prime_matches = [rel for rel in payload_rels if rel == prime_rel]\n    leaked_files = [rel for rel in payload_rels if rel in source_only_files or any(rel.startswith(prefix) for prefix in source_only_dirs)]\n    return {\n        'success': len(prime_matches) == 1 and not leaked_files,\n        'zip_path': str(zip_path),\n        'prime_agent_entries': prime_matches,\n        'source_only_leaks': leaked_files,\n    }\n\n\ndef main() -> int:\n"
    )
    build_text = build_text.replace(
"    script_root = Path(__file__).resolve().parent\n    source_root = Path(args.source_root).resolve()\n    output_dir = Path(args.output_dir).resolve()\n",
"    script_root = Path(__file__).resolve().parent\n    source_root = Path(args.source_root).resolve()\n    manifest = json.loads((source_root / 'Gemini_Bundle_Source_Manifest.json').read_text(encoding='utf-8'))\n    output_dir = Path(args.output_dir).resolve()\n"
    )
    build_text = build_text.replace(
"    success = compile_proc.returncode == 0\n    write_report(output_dir, {'success': success, 'stage': 'complete' if success else 'compile', 'steps': steps})\n    return 0 if success else 1\n",
"    if compile_proc.returncode != 0:\n        write_report(output_dir, {'success': False, 'stage': 'compile', 'steps': steps})\n        return 1\n\n    zip_contract = inspect_gemini_zip_contract(output_dir, manifest)\n    steps.append({'name': 'inspect_gemini_zip_contract', 'returncode': 0 if zip_contract.get('success') else 1, 'report': zip_contract})\n    if not zip_contract.get('success'):\n        write_report(output_dir, {'success': False, 'stage': 'inspect_gemini_zip_contract', 'steps': steps})\n        return 1\n\n    write_report(output_dir, {'success': True, 'stage': 'complete', 'steps': steps})\n    return 0\n"
    )
build_path.write_text(build_text, encoding='utf-8')

# 5. Docs: append migration notes if not present.
for path, title in [(doc10, 'Prime-agent chunk source and generated runtime note'), (doc11, 'Prime-agent generated runtime topology note')]:
    text = path.read_text(encoding='utf-8')
    if title not in text:
        text = text.rstrip() + f"\n\n{title}\n- The editable prime-agent source is now the ordered chunk set under `01_GEMINI_AGENT_BUILD/prime_agent_chunks/` plus `Prime_Agent_Chunks_Manifest.json`.\n- `01_GEMINI_AGENT_BUILD/Prime_Agent_DCOIR_Gemini_Orchestrator.md.txt` is a generated runtime artifact assembled from the chunk manifest before validation and compile.\n- The generated runtime prime-agent file must appear in the final Gemini Enterprise bundle as one coherent prompt file. Source-only chunk files and the chunk manifest must not ship in the final Gemini delivery ZIP.\n- Build and validation lanes must reassemble before judging the Gemini agent and must inspect the final ZIP for source-only leakage.\n"
        path.write_text(text + '\n', encoding='utf-8')

# 6. Validate in runner before commit. Remove tracked/generated monolith from source control after validation.
out_dir = repo / 'project_sources/validation/out_gemini_generated_prime_migration_001'
if out_dir.exists():
    shutil.rmtree(out_dir)
out_dir.mkdir(parents=True, exist_ok=True)
# Ensure build starts from chunk source and can generate the monolithic runtime file.
if prime_path.exists():
    prime_path.unlink()
subprocess.run([sys.executable, str(build_path), '--source-root', str(source_root), '--output-dir', str(out_dir)], check=True)
report = json.loads((out_dir / 'build_dcoir_gemini_release_report.json').read_text(encoding='utf-8'))
if not report.get('success'):
    raise SystemExit('Gemini generated-prime migration build report did not pass')
zip_step = next((s for s in report['steps'] if s.get('name') == 'inspect_gemini_zip_contract'), None)
if not zip_step or not zip_step.get('report', {}).get('success'):
    raise SystemExit('Gemini ZIP contract inspection did not pass')
# Remove generated prime from working tree and mark deletion in git.
if prime_path.exists():
    prime_path.unlink()
subprocess.run(['git', 'rm', '--quiet', '--', prime_path.as_posix()], check=False)

# Commit only intended paths and deletion.
paths = [
    manifest_path.as_posix(),
    compile_path.as_posix(),
    validate_path.as_posix(),
    build_path.as_posix(),
    doc10.as_posix(),
    doc11.as_posix(),
    prime_path.as_posix(),
]
subprocess.run(['git', 'add', '--', *paths], check=True)
if subprocess.run(['git', 'diff', '--cached', '--quiet']).returncode == 0:
    print(json.dumps({'success': True, 'changed': False}, indent=2))
else:
    subprocess.run(['git', 'commit', '-m', 'Make Gemini prime agent generated from chunk source'], check=True)
    subprocess.run(['git', 'push', 'origin', 'HEAD:main'], check=True)
    print(json.dumps({'success': True, 'changed': True, 'validated_before_commit': True, 'zip_contract': zip_step['report']}, indent=2))
'@

$script = Join-Path $env:DCOIR_CONFIG_DIR 'gemini_generated_prime_migration_001.py'
$py | Out-File -FilePath $script -Encoding utf8
python $script
