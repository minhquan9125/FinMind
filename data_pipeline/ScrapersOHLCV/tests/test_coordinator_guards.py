from datetime import datetime
import pytest
from ohlcv.core.state import CandleBook
from test_core import candle, NOW


def test_final_candle_cannot_become_pending_even_authoritatively():
    book = CandleBook([candle(status='closed', reconciled_at=NOW)])
    assert not book.apply(candle(status='pending_reconciliation'), authoritative=True).accepted
    assert book.current['FPT'].status == 'closed'


def test_source_identifier_accepts_versioned_provenance_but_rejects_control_chars():
    assert candle(source='dnse_v2').source == 'dnse_v2'
    with pytest.raises(ValueError):
        candle(source='dnse\n')
