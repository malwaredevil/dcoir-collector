#!/usr/bin/env python3
"""Fail closed if the checked-in PowerShell inventory omits or misstates a source."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from powershell_surface_inventory_common import DEFAULT_JSON_OUTPUT, repo_relative_cli_path
from powershell_surface_inventory_outputs import build_inventory


def verify_inventory(repo_root: Path, inventory_path: Path = DEFAULT_JSON_OUTPUT) -> int:
    root = repo_root.resolve()
    try:
        tracked = repo_relative_cli_path(root, inventory_path, 'checked-in PowerShell inventory')
        expected: Any = json.loads(tracked.read_text(encoding='utf-8'))
        current = build_inventory(root)
        if not isinstance(expected, dict) or expected.get('mode') != 'full':
            raise ValueError('checked-in inventory must be a full JSON object')
        if not expected.get('validation', {}).get('success') or not current['validation']['success']:
            raise ValueError('checked-in or freshly discovered inventory validation failed: '
                             + str(current['validation'].get('errors', [])[:5]))
        if current != expected:
            old_paths = {x['path']: x for x in expected.get('surfaces', [])}
            new_paths = {x['path']: x for x in current['surfaces']}
            omitted = sorted(new_paths.keys() - old_paths.keys())
            stale = sorted(old_paths.keys() - new_paths.keys())
            changed = sorted(p for p in old_paths.keys() & new_paths.keys() if old_paths[p] != new_paths[p])
            raise ValueError('PowerShell inventory is stale; regenerate and commit it before analysis. '
                             f'unlisted paths={omitted[:5]}, stale paths={stale[:5]}, '
                             f'changed facts/classifications={changed[:5]}; '
                             'all inventory metadata must match freshly discovered sources')
        print(f'PASS: PowerShell inventory matches fresh source discovery: '
              f'{len(current["surfaces"])} surfaces, '
              f'{current["summary"]["by_inclusion_decision"].get("include", 0)} included')
        return 0
    except (OSError, ValueError, KeyError, TypeError, RuntimeError) as exc:
        print(f'FAIL: PowerShell inventory freshness: {exc}', file=sys.stderr)
        return 1


def main() -> int:
    parser = argparse.ArgumentParser(description='Verify checked-in PowerShell inventory against current checkout')
    parser.add_argument('--repo-root', default='.')
    parser.add_argument('--inventory', default=DEFAULT_JSON_OUTPUT.as_posix())
    args = parser.parse_args()
    return verify_inventory(Path(args.repo_root), Path(args.inventory))


if __name__ == '__main__':
    raise SystemExit(main())
