from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

from lib.openai_dcoir_replay_package import (
    OPENAI_MODEL_ID,
    OPENAI_RUNTIME_NAME,
    load_governed_openai_target_package,
)

CONFIG_PATH = Path('project_sources/agent_runtime/generated/packages/openai_usb_reporting/GPT_Configuration.json')
MANIFEST_PATH = Path('project_sources/agent_runtime/generated/packages/openai_usb_reporting/manifest.json')


def load_governed_openai_usb_package(repo_root: Path) -> Dict[str, Any]:
    return load_governed_openai_target_package(
        repo_root,
        target_id='openai_usb_reporting',
        config_relative_path=CONFIG_PATH,
        manifest_relative_path=MANIFEST_PATH,
        display_name='AFRICOM USB Reporting',
    )


__all__ = [
    'OPENAI_MODEL_ID',
    'OPENAI_RUNTIME_NAME',
    'load_governed_openai_usb_package',
]
