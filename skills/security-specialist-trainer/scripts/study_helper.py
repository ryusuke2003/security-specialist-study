#!/usr/bin/env python3
"""Compatibility entrypoint for the modular security-specialist trainer."""
from __future__ import annotations

import sys
from pathlib import Path

_SCRIPT_DIRECTORY = Path(__file__).resolve().parent
if str(_SCRIPT_DIRECTORY) not in sys.path:
    sys.path.insert(0, str(_SCRIPT_DIRECTORY))

from trainer.common import *
from trainer.session_parser import *
from trainer.indexes import *
from trainer.progress import *
from trainer.planner import *
from trainer.cli import main, parse_args

if __name__ == "__main__":
    raise SystemExit(main())
