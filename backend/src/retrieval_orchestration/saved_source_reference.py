"""Readable saved-source metadata; no fetching, inferred URLs or new evidence."""
from datetime import datetime
from urllib.parse import urlsplit


def source_reference_metadata(citation,item):
    locator=item.get('locator') or {}
    snapshot=item.get('snapshot') or {}
    candidates=[locator.get('url'),locator.get('source_url'),snapshot.get('url'),item.get('source_url')]
    url=None
    for value in candidates:
        if not isinstance(value,str):continue
        try:parsed=urlsplit(value)
        except ValueError:continue
        if parsed.scheme in ('http','https') and parsed.hostname and not parsed.username and not parsed.password:
            url=value;break
    if url:citation['source_url']=url
    else:citation.pop('source_url',None)
    details=[]
    published=locator.get('published_at') or snapshot.get('published_at') or (item.get('stored_news')or{}).get('published_at')
    if published:
        try:details.append('Ngày đăng: '+datetime.fromisoformat(str(published).replace('Z','+00:00')).strftime('%d/%m/%Y'))
        except ValueError:pass
    page=locator.get('pdf_page') or locator.get('page_number') or locator.get('page')
    if page is not None:details.append('Trang PDF: '+str(page))
    if url:details.append('Nguồn gốc: '+url)
    else:details.append('Nguồn lưu trong FinMind; chưa có liên kết công khai để mở.')
    return details
