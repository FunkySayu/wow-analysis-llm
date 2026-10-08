"""Puts tools/raidbots/ on sys.path so `import talent_tree_sync` works without packaging tools/
as an installable module -- consistent with tools/warcraftlogs' existing style (plain scripts,
imported by adding the directory to sys.path) rather than inventing a new convention."""

from __future__ import annotations

import sys
from pathlib import Path

TOOLS_DIR = Path(__file__).resolve().parents[1]
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))
