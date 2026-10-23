"""Article content shares feed admission and cannot fetch arbitrary hosts."""
import pytest

from src.market_data.news import FireAntNews, NewsService
from src.market_data.live import BusyError

URL = 'https://fireant.vn/bai-viet/tin-fpt/123'


def test_article_uses_shared_quota_spacing_and_cache():
    seconds = [0]
    class Source:
        calls = []
        def __call__(self, symbol): self.calls.append('feed'); return []
        def article(self, url): self.calls.append(url); return {'url': url, 'content': 'Nội dung'}
    class Repository:
        def runtime_write(self, *args): pass
        def get_news(self, *args): return {'articles': []}
    source = Source()
    news = NewsService(source, Repository(), clock=lambda: seconds[0])
    news.refresh('FPT')
    with pytest.raises(BusyError): news.article(URL)
    seconds[0] = 2
    assert news.article(URL)['content'] == 'Nội dung'
    assert news.article(URL)['content'] == 'Nội dung'
    assert source.calls == ['feed', URL]
    for i in range(8):
        seconds[0] += 2
        news.article(URL+str(i))
    seconds[0] += 2
    with pytest.raises(BusyError): news.article(URL+'another')
    assert len(source.calls) == 10


@pytest.mark.parametrize('url', ['https://evil.test/bai-viet/tin/123', 'http://fireant.vn/bai-viet/tin/123',
    'https://user:pass@fireant.vn/bai-viet/tin/123', 'https://fireant.vn/bai-viet/tin/not-numeric',
    'https://fireant.vn:8080/bai-viet/tin/123'])
def test_article_url_rejected_before_network(monkeypatch, url):
    source = FireAntNews()
    monkeypatch.setattr(source, '_get', lambda *args, **kw: pytest.fail('must not access network'))
    try:
        with pytest.raises(ValueError): source.article(url)
    finally: source.close()


def test_article_fetch_binds_id_and_strips_html(monkeypatch):
    import json
    source = FireAntNews()
    source.anonymous = 'public-test-value'
    def get(url, **kwargs):
        assert url == 'https://restv2.fireant.vn/posts/123'
        return json.dumps({'type': 1, 'postID': 123, 'title': 'FPT',
                           'content': '<p>FPT mở trung tâm nghiên cứu.</p>', 'date': '2026-10-23T09:00:00Z'})
    monkeypatch.setattr(source, '_get', get)
    try:
        result = source.article(URL)
        assert result['content'] == 'FPT mở trung tâm nghiên cứu.'
        assert result['url'] == URL
    finally: source.close()
