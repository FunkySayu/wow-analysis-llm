"""Puts tools/warcraftlogs on sys.path so `from lib import ...` resolves the same way it
does under `run.py`, which inserts its own directory before importing checks.

These tests live here rather than under tools/raidbots/tests/ on purpose: tools/pyproject.toml
holds `tests/*.py` to ruff + `mypy --strict`, and tools/warcraftlogs predates that convention
(see the NOTE in that file). Run them explicitly:

    wsl.exe -d Ubuntu -e python3 -m pytest tools/warcraftlogs/tests -q
"""

from __future__ import annotations

import sys
from pathlib import Path

WCL_DIR = Path(__file__).resolve().parents[1]
if str(WCL_DIR) not in sys.path:
    sys.path.insert(0, str(WCL_DIR))
