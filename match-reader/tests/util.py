"""Shared helpers for the match-reader tests: paths and cached builds."""
from __future__ import annotations

import os
import sys

# match-reader/
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# the repo root, so the sibling match-lab package is importable
_REPO = os.path.dirname(ROOT)
_MATCH_LAB = os.path.join(_REPO, "match-lab")
if _MATCH_LAB not in sys.path:
    sys.path.insert(0, _MATCH_LAB)

from matchlab import generate_match  # noqa: E402
from matchreader import reader  # noqa: E402

DATA_DIR = os.path.join(_REPO, "data")

_CACHE = {}


def seed_match(seed: int):
    """The generated match for a seed (cached; never mutated by the reader)."""
    if seed not in _CACHE:
        _CACHE[seed] = generate_match(seed)
    return _CACHE[seed]


def seed_demo(seed: int):
    """(demo output, accepted candidates) for a seed, cached."""
    if ("demo", seed) not in _CACHE:
        out, accepted, _held = reader._build(seed_match(seed))
        _CACHE[("demo", seed)] = (out, accepted)
    return _CACHE[("demo", seed)]
