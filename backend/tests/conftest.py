"""Test isolation for process-wide state."""
import pytest

from src.documents.shared_serving import shared_pointer


@pytest.fixture(autouse=True)
def _isolated_shared_serving_pointer():
    """The shared serving-corpus pointer is a process-wide cache; no test may inherit another's value."""
    shared_pointer().clear()
    yield
    shared_pointer().clear()
