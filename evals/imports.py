"""Other tracks' modules, used only when they are merged."""
from __future__ import annotations

import importlib
from typing import Any


def optional(module: str, name: str) -> Any | None:
    """module.name, or None when that module or one of its packages is missing. Every other import error is raised."""
    try:
        found = importlib.import_module(module)
    except ModuleNotFoundError as e:
        parts = module.split(".")
        if e.name in {".".join(parts[:i]) for i in range(1, len(parts) + 1)}:
            return None
        raise
    return getattr(found, name)
