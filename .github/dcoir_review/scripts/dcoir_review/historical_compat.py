"""Narrow compatibility bridge for retired historical DCOIR module names.

Historical wrappers delegate reads and writes to their responsibility-named
canonical module. Production code must import the canonical modules directly;
this bridge exists only for legacy imports and characterization tests that have
not yet been renamed.
"""

from __future__ import annotations

import sys
from types import ModuleType
from typing import Any


class _HistoricalAliasModule(ModuleType):
    def __getattribute__(self, name: str) -> Any:
        if name == "__dict__":
            try:
                target = ModuleType.__getattribute__(self, "_dcoir_compat_target")
            except AttributeError:
                return ModuleType.__getattribute__(self, name)
            return ModuleType.__getattribute__(target, "__dict__")
        return ModuleType.__getattribute__(self, name)

    def __getattr__(self, name: str) -> Any:
        target = ModuleType.__getattribute__(self, "_dcoir_compat_target")
        return getattr(target, name)

    def __setattr__(self, name: str, value: Any) -> None:
        if name.startswith("__") or name.startswith("_dcoir_compat_"):
            ModuleType.__setattr__(self, name, value)
            return
        target = ModuleType.__getattribute__(self, "_dcoir_compat_target")
        setattr(target, name, value)

    def __dir__(self) -> list[str]:
        target = ModuleType.__getattribute__(self, "_dcoir_compat_target")
        return sorted(set(ModuleType.__dir__(self)) | set(dir(target)))


def install_historical_alias(module_name: str, target: ModuleType) -> None:
    module = sys.modules[module_name]
    ModuleType.__setattr__(module, "_dcoir_compat_target", target)
    ModuleType.__setattr__(module, "__class__", _HistoricalAliasModule)
