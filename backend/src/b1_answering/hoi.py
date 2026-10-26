"""Legacy CLI entrypoint shim."""""
import sys
from pathlib import Path

_backend = Path(__file__).resolve().parents[2]
if str(_backend) not in sys.path:
    sys.path.insert(0, str(_backend))

from src.b1_answering.cli.main import (
    DEMO_PACK,
    DEMO_PASSAGE,
    FixtureProvider,
    run_cli,
    main,
    display,
)

if __name__ == "__main__":
    raise SystemExit(main())
