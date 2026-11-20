"""Make the legacy CLI modules importable when pytest runs from any directory.

These tests import `hoi` and `retrieval_flow` as top-level modules, which only
resolve when the working directory is `src/retrieval_orchestration` (the way
`python -m unittest discover -s tests` is documented in the README).
"""
import sys
from pathlib import Path

ROOT = str(Path(__file__).resolve().parents[1])
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
