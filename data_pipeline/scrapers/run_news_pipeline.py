"""Compatibility entry point; implementation lives in news/."""
import sys
from news import run_news_pipeline as implementation

if __name__ == '__main__':
    raise SystemExit(implementation.main())
else:
    sys.modules[__name__] = implementation
