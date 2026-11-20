"""Compatibility entry point; implementation lives in news/."""
import sys
from pathlib import Path

_scrapers_dir = str(Path(__file__).resolve().parent)
if _scrapers_dir not in sys.path:
    sys.path.insert(0, _scrapers_dir)

from news import run_news_pipeline as implementation

if __name__ == '__main__':
    raise SystemExit(implementation.main())
else:
    sys.modules[__name__] = implementation
