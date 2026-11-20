from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import Mock

from backend.src.market_data.session import SessionGate
from backend.src.market_data.live import LiveCoordinator

VN = timezone(timedelta(hours=7))
ROOT = Path(__file__).resolve().parents[2]


def test_status_distinguishes_configured_closed_break_and_unknown_calendar(tmp_path):
    moment = [datetime(2026, 11, 6, 15, 23, tzinfo=VN)]
    gate = SessionGate(ROOT, now=lambda: moment[0])
    assert gate.status() == 'CLOSED'
    moment[0] = datetime(2026, 11, 6, 11, 45, tzinfo=VN)
    assert gate.status() == 'BREAK'
    moment[0] = datetime(2026, 11, 6, 10, tzinfo=VN)
    assert gate.status() == 'OPEN'
    moment[0] = datetime(2027, 11, 6, 15, 23, tzinfo=VN)
    assert gate.status() == 'UNKNOWN_CALENDAR'
    assert SessionGate(tmp_path).status() == 'UNKNOWN_CALENDAR'
    assert gate.status('BAD') == 'UNKNOWN_CALENDAR'


def test_saved_chart_explains_closed_session_and_missing_calendar_without_fetching(tmp_path):
    now = lambda: datetime(2026, 11, 6, 15, 23, tzinfo=VN)
    repository = Mock()
    repository.get_ohlcv.return_value = {'symbol': 'CEO', 'bars': [{'date': '2026-11-06', 'close': '12.3'}]}
    fetch = Mock()
    for root, expected in [(ROOT, 'CLOSED'), (tmp_path, 'UNKNOWN_CALENDAR')]:
        service = LiveCoordinator(fetch, SessionGate(root, now=now), repository, now=now)
        result = service.read('CEO', 250)
        assert result['live']['session_status'] == expected
        assert result['live']['active'] is False
        assert result['bars'][0]['close'] == '12.3'
        assert 'Làm mới biểu đồ' in result['live']['reason']
        assert 'hoặc lịch' not in result['live']['reason']
    fetch.assert_not_called()
