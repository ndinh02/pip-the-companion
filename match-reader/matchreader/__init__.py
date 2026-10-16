"""matchreader: turn one match-lab match into the file the web app plays.

Run from match-reader/ (see build.py and pick_seed.py). Standard library only.
"""
from __future__ import annotations

from .reader import READER_VERSION, build_output, dumps, load_templates

__all__ = ["READER_VERSION", "build_output", "dumps", "load_templates"]
