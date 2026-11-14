"""Offline-only experiment measurements. Not imported by production routing."""
import re

TICKERS = ('VCB', 'TCB', 'MBB', 'FPT', 'BID', 'CTG', 'CMG', 'ELC', 'HPG', 'SSI',
           'REE', 'DGC', 'PNJ')
TICKER_PATTERN = re.compile(r'\b(?:' + '|'.join(TICKERS) + r')\b', re.IGNORECASE)
ROUTES = dict(NUMERIC='VECTOR', REPORT_CONTENT='VECTOR', NEWS='VECTOR', TREND='VECTOR',
              PERSON_ROLE='GRAPH', ENTITY_RELATION='GRAPH', MIXED='BOTH')


def mask_tickers(text):
    return TICKER_PATTERN.sub('doanh nghiệp', text)


def policy_observation(label, score, gap):
    return ROUTES[label] if score >= .65 and gap >= .08 else 'NEED_FALLBACK'


def transitions(before, after):
    if [(r['id'], r['gold']) for r in before] != [(r['id'], r['gold']) for r in after]:
        raise ValueError('CASE_ALIGNMENT')
    return dict(fixed=[a['id'] for a, b in zip(before, after) if a['gold'] and a['top1'] != a['gold'] == b['top1']],
                regressed=[a['id'] for a, b in zip(before, after) if a['gold'] and a['top1'] == a['gold'] != b['top1']])
