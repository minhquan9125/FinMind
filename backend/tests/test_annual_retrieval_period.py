"""Dense and hybrid retrieval must use the same annual period and reject old caches."""
import asyncio
import uuid

import pytest

from src.documents.repository import vector_search_filtered
from src.vector_retrieval import backend as hybrid
from backend.tests.test_filtered_vector_search import FakeConnection, FakePool


def test_dense_and_hybrid_select_and_filter_by_shared_period():
    from src.documents.retrieval_period import PERIOD_SQL, EXACT_PERIOD_SQL, FILTER_PERIOD_SQL
    for exact in (False, True):
        connection = FakeConnection()
        asyncio.run(vector_search_filtered(FakePool(connection), str(uuid.uuid4()), [0.1], 3,
                                          period='2024', exact_period=exact))
        assert PERIOD_SQL + ' AS period' in connection.sql
        assert (EXACT_PERIOD_SQL + ' = $3' if exact else FILTER_PERIOD_SQL + " ILIKE '%' || $3 || '%'") in connection.sql
    assert PERIOD_SQL + ' AS period' in hybrid.FIELDS


def test_cache_with_page_labels_is_invalidated_even_when_index_is_unchanged():
    payload = dict(version=2, tokenizer=hybrid.TOKENIZER_VERSION,
                   index_id='ecfbf20f-b3e0-5077-bd3e-03f0efb95e6d', model=hybrid.MODEL,
                   built_at=1000, fingerprint='a'*32, rows=[])
    with pytest.raises(hybrid.RetrievalError, match='CACHE_VERSION_MISMATCH'):
        hybrid._validate_cache(payload, payload['index_id'], hybrid.MODEL, 1000, 3600)
