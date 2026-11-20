"""Compatibility launcher; chart implementation lives in app/server.py."""
import sys
from ohlcv.app import server as implementation

if __name__ == '__main__':
    raise SystemExit(implementation.main())
else:
    sys.modules[__name__] = implementation
