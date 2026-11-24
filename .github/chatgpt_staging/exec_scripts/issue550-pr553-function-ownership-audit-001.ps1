$ErrorActionPreference = 'Stop'

$repo = [Environment]::GetEnvironmentVariable('DCOIR_REPO_ROOT','Machine')
if ([string]::IsNullOrWhiteSpace($repo)) { $repo = $env:GITHUB_WORKSPACE }
if ([string]::IsNullOrWhiteSpace($repo)) { $repo = (Get-Location).Path }
$downloads = [Environment]::GetEnvironmentVariable('DCOIR_DOWNLOADS_DIR','Machine')
if ([string]::IsNullOrWhiteSpace($downloads)) { $downloads = $env:RUNNER_TEMP }
if ([string]::IsNullOrWhiteSpace($downloads)) { $downloads = [IO.Path]::GetTempPath() }

$expectedHead = '781a480bb306ff7e0bf1fd55302636a0176ad5c5'
$expectedTree = 'ecfe9870cff993695d58c9ee8f35525a0ccd9902'
$branch = 'refactor/issue-550-dcoir-runtime-consolidation'
$requestId = 'issue550-pr553-function-ownership-audit-001'
$worktree = Join-Path $downloads ($requestId + '-worktree')
$pythonPath = Join-Path $downloads ($requestId + '.py')
$jsonPath = Join-Path $downloads ($requestId + '.json')
$summaryPath = Join-Path $downloads ($requestId + '-summary.txt')

@('OPENROUTER_API_KEY','GITHUB_TOKEN','GH_TOKEN','DCOIR_GITHUB_FG_TOKEN','DCOIR_GITHUB_CL_TOKEN','DCOIR_GEMINI_API','DCOIR_OPENAI_API_KEY','DCOIR_OPENAI_PROJECT_ID','OPENAI_API_KEY') | ForEach-Object {
    [Environment]::SetEnvironmentVariable($_, $null, 'Process')
    Remove-Item ("Env:" + $_) -ErrorAction SilentlyContinue
}
$env:PYTHONDONTWRITEBYTECODE = '1'

& git -C $repo fetch --no-tags origin "+refs/heads/$branch`:refs/remotes/origin/$branch"
if ($LASTEXITCODE -ne 0) { throw 'Fetch failed' }
$actualHead = (& git -C $repo rev-parse "refs/remotes/origin/$branch").Trim()
if ($actualHead -ne $expectedHead) { throw "PR head drift: expected $expectedHead observed $actualHead" }
$actualTree = (& git -C $repo rev-parse "$expectedHead`^{tree}").Trim()
if ($actualTree -ne $expectedTree) { throw "PR tree drift: expected $expectedTree observed $actualTree" }
if (Test-Path -LiteralPath $worktree) { & git -C $repo worktree remove --force $worktree 2>$null }
& git -C $repo worktree add --detach $worktree $expectedHead
if ($LASTEXITCODE -ne 0) { throw 'Unable to create isolated worktree' }

$python = @'
from __future__ import annotations
import ast
import inspect
import json
import re
import sys
from collections import defaultdict
from pathlib import Path
from types import ModuleType
from typing import Any

root = Path.cwd()
scripts = root / '.github' / 'dcoir_review' / 'scripts'
if str(scripts) not in sys.path:
    sys.path.insert(0, str(scripts))

from dcoir_review.entrypoint import DcoirReviewEntrypoint
from dcoir_review_architecture_inventory import build_inventory

PATCH_RE = re.compile(r'^dcoir_review_required_runtime_patch_v\d+(?:$|_)')
STORAGE_LITERAL_RE = re.compile(r'_dcoir_(?:review_)?(?:v\d+_)?[A-Za-z0-9_]*(?:original|stored|storage)[A-Za-z0-9_]*')


def callable_owner(value: Any) -> dict[str, str] | None:
    if not callable(value):
        return None
    module_name = str(getattr(value, '__module__', '') or '')
    qualname = str(getattr(value, '__qualname__', getattr(value, '__name__', '')) or '')
    try:
        source = inspect.getsourcefile(value) or ''
    except (OSError, TypeError):
        source = ''
    if source:
        try:
            source = Path(source).resolve().relative_to(scripts).as_posix()
        except (OSError, ValueError):
            source = str(source)
    return {'module': module_name, 'qualname': qualname, 'source': source}


def snap(namespace: Any) -> dict[str, dict[str, str]]:
    result = {}
    if namespace is None:
        return result
    for name in sorted(dir(namespace)):
        if name.startswith('__'):
            continue
        try:
            owner = callable_owner(getattr(namespace, name))
        except Exception:
            continue
        if owner is not None:
            result[name] = owner
    return result


def snap_all(review: Any) -> dict[str, dict[str, dict[str, str]]]:
    return {
        'review': snap(review),
        'hardened': snap(getattr(review, 'hardened', None)),
        'base': snap(getattr(review, 'base', None)),
    }


def changed(before, after):
    rows = []
    for surface in ('review','hardened','base'):
        names = sorted(set(before[surface]) | set(after[surface]))
        for name in names:
            if before[surface].get(name) != after[surface].get(name):
                rows.append({
                    'surface': surface,
                    'name': name,
                    'before': before[surface].get(name),
                    'after': after[surface].get(name),
                })
    return rows


def production_sequence(entry):
    groups = (
        'patch_module_names','terminal_patch_module_names','post_terminal_patch_module_names',
        'candidate_integrity_patch_module_names','stage_local_patch_module_names',
        'execution_policy_patch_module_names','telemetry_patch_module_names','post_telemetry_patch_module_names',
    )
    return [name for group in groups for name in getattr(entry, group)]


def source_path(relative: str) -> Path:
    return scripts / relative


def duplicate_definitions(inventory):
    defs = defaultdict(list)
    storage_constants = []
    for module_name, record in inventory['modules'].items():
        for source in record.get('sources', []):
            path = source_path(source['path'])
            if not path.is_file():
                continue
            text = path.read_text(encoding='utf-8')
            tree = ast.parse(text, filename=str(path))
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    defs[node.name].append({'module': module_name, 'path': source['path'], 'line': node.lineno})
            for node in tree.body:
                if not isinstance(node, (ast.Assign, ast.AnnAssign)):
                    continue
                targets = node.targets if isinstance(node, ast.Assign) else [node.target]
                value = node.value
                if not isinstance(value, ast.Constant) or not isinstance(value.value, str):
                    continue
                if not STORAGE_LITERAL_RE.search(value.value):
                    continue
                for target in targets:
                    if isinstance(target, ast.Name):
                        refs = sum(1 for candidate in ast.walk(tree) if isinstance(candidate, ast.Name) and candidate.id == target.id)
                        storage_constants.append({
                            'module': module_name,
                            'path': source['path'],
                            'constant': target.id,
                            'attribute': value.value,
                            'ast_name_references': refs,
                            'candidate_orphan': refs <= 1,
                        })
    duplicates = {
        name: rows for name, rows in sorted(defs.items())
        if len({row['path'] for row in rows}) > 1 and name not in {'main','apply_pareto_context_module'}
    }
    return duplicates, storage_constants


entry = DcoirReviewEntrypoint()
review = entry.import_module(entry.review_module_name)
sequence = production_sequence(entry)
initial = snap_all(review)
stages = []
chains = defaultdict(list)
for module_name in sequence:
    before = snap_all(review)
    entry._apply_patch_modules(review, (module_name,))
    after = snap_all(review)
    delta = changed(before, after)
    for item in delta:
        chains[(item['surface'], item['name'])].append({
            'stage': module_name,
            'before': item['before'],
            'after': item['after'],
        })
    stages.append({'module': module_name, 'changed_callable_count': len(delta), 'changes': delta})

final = snap_all(review)
change_chains = []
superseded = []
stable_stage_summary = []
for (surface, name), events in sorted(chains.items()):
    final_owner = final[surface].get(name)
    chain = {'surface': surface, 'name': name, 'change_count': len(events), 'events': events, 'final_owner': final_owner}
    if len(events) > 1:
        change_chains.append(chain)
    for event in events:
        if event['after'] is not None and event['after'] != final_owner:
            superseded.append({
                'surface': surface,
                'name': name,
                'installed_by_stage': event['stage'],
                'installed_owner': event['after'],
                'final_owner': final_owner,
            })

for stage in stages:
    if not stage['module'].startswith('dcoir_review.'):
        continue
    final_survivors = 0
    superseded_count = 0
    for item in stage['changes']:
        if item['after'] == final[item['surface']].get(item['name']):
            final_survivors += 1
        elif item['after'] is not None:
            superseded_count += 1
    stable_stage_summary.append({
        'module': stage['module'],
        'changed_callable_count': stage['changed_callable_count'],
        'final_survivor_count': final_survivors,
        'later_superseded_count': superseded_count,
    })

final_numbered = []
final_stable = []
for surface in ('review','hardened','base'):
    for name, owner in sorted(final[surface].items()):
        row = {'surface': surface, 'name': name, 'owner': owner}
        if PATCH_RE.match(owner.get('module','')):
            final_numbered.append(row)
        elif owner.get('module','').startswith('dcoir_review.'):
            final_stable.append(row)

stored_callable_attrs = []
for surface, namespace in (
    ('review', review), ('hardened', getattr(review,'hardened',None)), ('base', getattr(review,'base',None))
):
    if namespace is None:
        continue
    for name, value in sorted(vars(namespace).items()):
        if not name.startswith('_dcoir_') or not callable(value):
            continue
        stored_callable_attrs.append({'surface': surface, 'attribute': name, 'owner': callable_owner(value)})

inventory = build_inventory()
duplicates, storage_constants = duplicate_definitions(inventory)
numbered_sources = sorted({
    source['path']
    for module, record in inventory['modules'].items()
    if record.get('numbered_version') is not None
    for source in record.get('sources', [])
})

result = {
    'schema_version': 'dcoir_review_function_ownership_audit_v1',
    'exact_head': '781a480bb306ff7e0bf1fd55302636a0176ad5c5',
    'exact_tree': 'ecfe9870cff993695d58c9ee8f35525a0ccd9902',
    'production_sequence': sequence,
    'production_component_count': len(sequence),
    'stage_changes': stages,
    'multi_stage_change_chains': change_chains,
    'superseded_callable_installations': superseded,
    'stable_stage_summary': stable_stage_summary,
    'final_numbered_owned_callables': final_numbered,
    'final_stable_owned_callables': final_stable,
    'stored_original_callable_attributes': stored_callable_attrs,
    'duplicate_function_definitions': duplicates,
    'storage_constants': storage_constants,
    'candidate_orphan_storage_constants': [row for row in storage_constants if row['candidate_orphan']],
    'remaining_numbered_source_paths': numbered_sources,
    'inventory_missing_modules': inventory['missing_modules'],
    'inventory_max_numbered_version': inventory['max_numbered_version'],
}
Path(r'__JSON_PATH__').write_text(json.dumps(result, indent=2, sort_keys=True), encoding='utf-8')

summary = [
    'result=PASS',
    'exact_head=' + result['exact_head'],
    'exact_tree=' + result['exact_tree'],
    f"production_components={result['production_component_count']}",
    f"multi_stage_callable_chains={len(change_chains)}",
    f"superseded_callable_installations={len(superseded)}",
    f"final_numbered_owned_callables={len(final_numbered)}",
    f"final_stable_owned_callables={len(final_stable)}",
    f"stored_original_callable_attributes={len(stored_callable_attrs)}",
    f"duplicate_function_names={len(duplicates)}",
    f"candidate_orphan_storage_constants={len(result['candidate_orphan_storage_constants'])}",
    f"remaining_numbered_source_paths={len(numbered_sources)}",
    'stable_stage_summary=' + json.dumps(stable_stage_summary, separators=(',',':')),
    'final_numbered_owner_modules=' + ','.join(sorted({row['owner']['module'] for row in final_numbered})),
    'no_inference=true',
    'no_provider_calls=true',
]
Path(r'__SUMMARY_PATH__').write_text('\n'.join(summary) + '\n', encoding='utf-8')
print('\n'.join(summary))
'@
$python = $python.Replace('__JSON_PATH__', $jsonPath.Replace('\','\\')).Replace('__SUMMARY_PATH__', $summaryPath.Replace('\','\\'))
[IO.File]::WriteAllText($pythonPath, $python, [Text.UTF8Encoding]::new($false))

try {
    Push-Location $worktree
    & python $pythonPath
    if ($LASTEXITCODE -ne 0) { throw 'Function ownership audit failed' }
    $dirty = @(& git status --porcelain)
    if ($dirty.Count -ne 0) { throw "Isolated worktree dirty after audit: $($dirty -join ', ')" }
}
finally {
    Pop-Location
    & git -C $repo worktree remove --force $worktree 2>$null
}

Write-Host 'ISSUE550_PR553_FUNCTION_OWNERSHIP_AUDIT_001_PASS'
