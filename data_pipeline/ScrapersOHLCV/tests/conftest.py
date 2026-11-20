import tempfile
from pathlib import Path

import pytest


@pytest.fixture
def local_tmp():
    base = Path(__file__).resolve().parents[1] / ".agent-state" / "test-tmp"
    base.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=base) as name:
        (Path(name) / 'web').mkdir()
        yield Path(name)
