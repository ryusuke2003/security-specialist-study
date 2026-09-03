#!/usr/bin/env python3
"""Compatibility entrypoint for the modular security-specialist trainer."""
from __future__ import annotations

import sys
from pathlib import Path

_SCRIPT_DIRECTORY = Path(__file__).resolve().parent
if str(_SCRIPT_DIRECTORY) not in sys.path:
    sys.path.insert(0, str(_SCRIPT_DIRECTORY))

import trainer as _trainer

__all__ = _trainer.__all__
for _name in __all__:
    globals()[_name] = getattr(_trainer, _name)
del _name

if __name__ == "__main__":
    raise SystemExit(main())
