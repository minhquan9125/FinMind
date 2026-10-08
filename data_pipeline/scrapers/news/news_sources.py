"""Public provider endpoints used by the CafeF and FireAnt news tabs."""
import re
import unicodedata
from functools import lru_cache
from urllib.parse import urljoin
from xml.etree import ElementTree

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from scrapling.parser import Selector

CAFEF = 'https://cafef.vn'
FIREANT = 'https://fireant.vn'
FIREANT_API = 'https://restv2.fireant.vn'


def session():
    client = requests.Session()
    client.headers.update({'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/131.0.0.0 Safari/537.36'})
    client.mount('https://', HTTPAdapter(max_retries=Retry(
        total=2, backoff_factor=0.5, status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=('GET',), respect_retry_after_header=False)))
    return client


HTTP = session()


def get(url, **kwargs):
    response = HTTP.get(url, timeout=25, **kwargs)
    response.raise_for_status()
    return response


def plain_text(value):
    if not value:
        return ''
    page = Selector('<div>' + str(value) + '</div>')
    return ' '.join(page.get_all_text().split())


def fold(value):
    value = unicodedata.normalize('NFD', value.lower().replace('đ', 'd'))
    return ''.join(c for c in value if not unicodedata.combining(c))


def relevant(item):
    """Conservative headline/summary filter; broad economics groups are insufficient."""
    if item.get('symbols'):
        return True
    text = fold(item.get('title', '') + ' ' + item.get('description', ''))
    return bool(re.search(
        r'\b(chung khoan|co phieu|co dong|co tuc|trai phieu|vn[ -]?index|vn30|'
        r'hnx|upcom|hose|ipo|niem yet|tu doanh|khoi ngoai|lai suat|ty gia|'
        r'lam phat|gdp|fed|chinh sach tien te|ngan hang nha nuoc|'
        r'ket qua kinh doanh|loi nhuan|doanh thu|bao cao tai chinh|gia dau|'
        r'xuat khau dau|thue quan|chinh sach tai khoa|gia vang)\b', text))


@lru_cache(maxsize=1)
def fireant_headers():
    """Resolve the site's public anonymous credential; never embed a user token."""
    page = Selector(get(FIREANT).text)
    scripts = [n.attrib.get('src', '') for n in page.css('script[src]')]
    for script in scripts:
        if '/chunks/pages/_app-' not in script:
            continue
        text = get(urljoin(FIREANT, script)).text
        match = re.search(r'ANONYMOUS_ACCESS_TOKEN\s*=\s*"([^"]+)"', text)
        if match:
            return {'Authorization': 'Bearer ' + match.group(1), 'Referer': FIREANT + '/'}
    raise RuntimeError('FireAnt public anonymous credential not found in current site bundle')


def fireant_json(path, params=None):
    response = HTTP.get(FIREANT_API + path, params=params, headers=fireant_headers(), timeout=25)
    if response.status_code in (401, 403):
        fireant_headers.cache_clear()
        response = HTTP.get(FIREANT_API + path, params=params, headers=fireant_headers(), timeout=25)
    response.raise_for_status()
    return response.json()


def fireant_item(row):
    title = plain_text(row.get('title'))
    slug = re.sub(r'[^a-z0-9]+', '-', fold(title)).strip('-') or 'tin-tuc'
    symbols = sorted({tag['symbol'].upper() for tag in row.get('taggedSymbols', [])
                      if isinstance(tag, dict) and tag.get('symbol')})
    return {'url': f'{FIREANT}/bai-viet/{slug}/{row["postID"]}',
            'title': title, 'description': plain_text(row.get('description')),
            'published_at': row.get('date'), 'symbols': symbols,
            'provider_id': str(row['postID']), 'category': (row.get('postGroup') or {}).get('name')}


def fireant_candidates(symbol=None, max_pages=5):
    seen = set()
    for page in range(max_pages):
        params = {'type': 1, 'offset': page * 50, 'limit': 50}
        if symbol:
            params['symbol'] = symbol
        rows = fireant_json('/posts', params)
        if not isinstance(rows, list):
            raise ValueError('Unexpected FireAnt posts response (expected a list)')
        fresh = 0
        for row in rows:
            if not isinstance(row, dict) or row.get('type') != 1 or not row.get('postID'):
                continue
            key = row['postID']
            if key in seen:
                continue
            seen.add(key)
            fresh += 1
            item = fireant_item(row)
            # The tab's symbol association is authoritative, including articles
            # whose title does not explicitly spell out the stock ticker.
            if symbol:
                item['symbols'] = sorted(set(item['symbols']) | {symbol})
                item['matched_symbols'] = [symbol]
            if symbol or relevant(item):
                yield item
        if not rows or not fresh:
            break


def cafef_candidates(symbol=None, max_pages=5):
    if symbol:
        seen = set()
        for page in range(1, max_pages + 1):
            data = get(CAFEF + '/du-lieu/Ajax/PageNew/News.ashx', params={
                'Symbol': symbol, 'NewsType': 0, 'PageIndex': page, 'PageSize': 50}).json()
            if data.get('Success') is False or not isinstance(data.get('Data'), list):
                raise ValueError('Unexpected CafeF symbol news response')
            fresh = 0
            for row in data['Data']:
                url = row.get('LinkDetail')
                if not url or url in seen:
                    continue
                seen.add(url)
                fresh += 1
                date = row.get('DeployDate') or ''
                match = re.search(r'Date\((\d+)\)', date)
                if match:
                    from datetime import datetime, timezone
                    date = datetime.fromtimestamp(int(match.group(1)) / 1000, timezone.utc).isoformat()
                yield {'url': urljoin(CAFEF, url), 'title': plain_text(row.get('Title')),
                       'description': plain_text(row.get('SubTitle')), 'published_at': date or None,
                       'symbols': [symbol], 'matched_symbols': [symbol]}
            if not fresh:
                break
        return
    # RSS can be unavailable or malformed independently of the article website.
    seen = set()
    rss_error = None
    try:
        root = ElementTree.fromstring(get(CAFEF + '/thi-truong-chung-khoan.rss').content)
        for row in root.findall('.//item'):
            item = {'url': row.findtext('link') or '', 'title': row.findtext('title') or '',
                    'description': plain_text(row.findtext('description')), 'symbols': []}
            if relevant(item):
                seen.add(item['url'])
                yield item
    except (requests.RequestException, ElementTree.ParseError) as exc:
        rss_error = exc
    # Category listing also fills the quota when the feed contains off-topic links.
    page = Selector(get(CAFEF + '/thi-truong-chung-khoan.chn').text)
    for node in page.css('h3 a[href], h2 a[href]'):
        url = urljoin(CAFEF, node.attrib.get('href', ''))
        item = {'url': url, 'title': ' '.join(node.get_all_text().split()), 'description': '', 'symbols': []}
        if url not in seen and relevant(item):
            seen.add(url)
            yield item
    if not seen and rss_error:
        raise RuntimeError(f'CafeF RSS failed and category listing had no usable links: {rss_error}')
