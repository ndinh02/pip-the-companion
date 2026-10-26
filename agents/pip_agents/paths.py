"""Make the sibling packages (match-lab, match-reader) importable."""
from __future__ import annotations

import os
import sys

REPO = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
for folder in ("match-lab", "match-reader"):
    path = os.path.join(REPO, folder)
    if path not in sys.path:
        sys.path.insert(0, path)
