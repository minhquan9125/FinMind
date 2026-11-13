"""Test isolation for process-wide state."""
import os

import pytest

# Tests sign their own tokens: never fall back to a real or published secret.
os.environ.setdefault('JWT_SECRET_KEY', 'test-only-jwt-secret-' + 'x' * 32)

from src.documents.shared_serving import shared_pointer


@pytest.fixture(autouse=True)
def _isolated_shared_serving_pointer():
    """The shared serving-corpus pointer is a process-wide cache; no test may inherit another's value."""
    shared_pointer().clear()
    yield
    shared_pointer().clear()
