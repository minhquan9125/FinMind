"""Offline, explainable event candidates; never changes news or markers."""
import argparse
import json
import math
import re
import unicodedata
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path

from news_crosscheck import article_similarity
from news_storage import SCRAPERS, daily_path

STOP = set('và của các những một là với cho từ tại trong trên được đã sẽ có này đó khi về theo đến hơn cũng vào ra để do tới đang sau cùng'.split())
ALIASES = {
    'FPT': ('fpt',), 'HPG': ('hpg', 'hòa phát', 'trần đình long'),
    'VCB': ('vcb', 'vietcombank'), 'TPB': ('tpb', 'tpbank', 'tiên phong'),
    'HAG': ('hag', 'hoàng anh gia lai', 'bầu đức', 'đoàn nguyên đức'),
    'PNJ': ('pnj',), 'NVL': ('nvl', 'novaland'), 'SHS': ('shs',),
    'F88': ('f88',), 'HOSE': ('hose', 'ho se'), 'HNX': ('hnx',),
    'VINFAST': ('vinfast',), 'NGA': ('nga',), 'FED': ('fed',),
}
EVENTS = {
    'share_issue': ('phát hành cổ phiếu', 'cổ phiếu thưởng', 'tăng vốn cổ phần'),
    'voting_shares': ('quyền biểu quyết',),
    'bond_issue': ('phát hành trái phiếu', 'chào bán trái phiếu', 'huy động',),
    'dividend': ('cổ tức',),
    'appointment': ('bổ nhiệm', 'đổi chủ', 'tổng giám đốc',),
    'shareholders': ('cổ đông',),
    'earnings': ('lợi nhuận', 'kết quả kinh doanh', 'kqkd',),
    'head_office': ('địa chỉ trụ sở', 'địa điểm trụ sở',),
    'agreement': ('hợp đồng', 'ký bán', 'ký kết', 'hợp tác', 'bắt tay',),
    'listing': ('niêm yết', 'chuyển sang hose',),
    'trading': ('bán ròng', 'mua ròng',),
    'sanction': ('xử phạt', 'bị phạt',),
}


def normalize(value):
    return ' '.join(re.findall(r'[^\W_]+', unicodedata.normalize('NFC', value or '').casefold()))


def words(value):
    return Counter(w for w in normalize(value).split() if w not in STOP and len(w) > 1)


def labels(text, rules):
    padded = ' ' + normalize(text) + ' '
    return {label for label, phrases in rules.items()
            if any(' ' + normalize(phrase) + ' ' in padded for phrase in phrases)}


def published(value):
    if not value:
        return None
    try:
        stamp = datetime.fromisoformat(value.replace('Z', '+00:00'))
        # CafeF article HTML dates have no offset; interpret them in Vietnam.
        if stamp.tzinfo is None:
            stamp = stamp.replace(tzinfo=timezone(timedelta(hours=7)))
        return stamp.astimezone(timezone.utc)
    except (ValueError, TypeError):
        return None


def specific_numbers(text):
    """Supporting anchors only, never proof that the associated facts agree."""
    values = re.findall(r'(?<!\w)\d+(?:[.,]\d+)*(?!\w)', text or '')
    return {v for v in values if ('.' in v or ',' in v or len(v) >= 3)
            and not (v.isdigit() and 1900 <= int(v) <= 2100)}


def cosine(a, b, idf):
    left = {w: (1 + math.log(n)) * idf.get(w, 1) for w, n in a.items()}
    right = {w: (1 + math.log(n)) * idf.get(w, 1) for w, n in b.items()}
    denominator = math.sqrt(sum(v*v for v in left.values()) * sum(v*v for v in right.values()))
    return sum(v * right.get(w, 0) for w, v in left.items()) / denominator if denominator else 0.0


def load_scope(root, scope):
    buckets = {'cafef': {}, 'fireant': {}}
    for source in buckets:
        folder = daily_path(root, source, scope, '01-01-2000').parent
        for path in sorted(folder.glob('*.json'), key=lambda p: datetime.strptime(p.stem, '%d-%m-%Y')):
            if not path.resolve().is_relative_to(SCRAPERS):
                raise ValueError('News file escapes scrapers')
            datetime.strptime(path.stem, '%d-%m-%Y')
            payload = json.loads(path.read_text(encoding='utf-8'))
            if not isinstance(payload, dict) or not isinstance(payload.get('articles'), list):
                raise ValueError(f'{path}: expected articles list')
            for article in payload['articles']:
                if (not isinstance(article, dict) or article.get('source') != source
                        or not isinstance(article.get('url'), str) or not article['url']):
                    raise ValueError(f'{path}: invalid article')
                # Same URL across crawl days is one article, not several discoveries.
                bucket = buckets[source].setdefault(article['url'], {'files': [], 'uncheck_files': []})
                bucket['files'].append(path.relative_to(root).as_posix())
                if article.get('marker') == 'uncheck':
                    bucket['uncheck_files'].append(path.relative_to(root).as_posix())
                bucket['article'] = article
    entries = [entry for bucket in buckets.values() for entry in bucket.values()]
    df = Counter()
    for entry in entries:
        a = entry['article']
        entry['title_words'] = words(a.get('title'))
        entry['body_words'] = words(a.get('content'))
        df.update(set(entry['title_words']) | set(entry['body_words']))
        # Do not use tab tags as proof: several posts can mention many tickers.
        entry['entities'] = labels(a.get('title', '') + ' ' + a.get('description', ''), ALIASES)
        entry['entities'].update(re.findall(r'\b[A-Z][A-Z0-9]{2,4}\b', a.get('title', '')))
        entry['events'] = labels(a.get('title', '') + ' ' + (a.get('content') or '')[:600], EVENTS)
        entry['numbers'] = specific_numbers(a.get('title', '') + ' ' + (a.get('content') or ''))
        entry['published'] = published(a.get('published_at'))
    idf = {w: math.log((1 + len(entries)) / (1 + n)) + 1 for w, n in df.items()}
    return buckets, idf


def compare(left, right, idf, window_days=3, threshold=0.52):
    a, b = left['article'], right['article']
    title_score = cosine(left['title_words'], right['title_words'], idf)
    body_score = cosine(left['body_words'], right['body_words'], idf)
    overlap = article_similarity(a, b)
    entities = sorted(left['entities'] & right['entities'])
    events = sorted(left['events'] & right['events'])
    numbers = sorted(left['numbers'] & right['numbers'])
    dates = left['published'], right['published']
    delta = abs((dates[0] - dates[1]).total_seconds()) / 86400 if all(dates) else None
    same_title = bool(normalize(a.get('title'))) and normalize(a.get('title')) == normalize(b.get('title'))
    # Resolution/document identifiers distinguish similar boilerplate disclosures.
    document_ids = [set(re.findall(r'(?:số|so)\s+(\d+(?:/\d+)?)', x.get('title', '').casefold())) for x in (a, b)]
    conflicting_document = all(document_ids) and not document_ids[0].intersection(document_ids[1])
    headline_score = 0.55 * title_score + 0.35 * body_score + 0.10 * bool(events)
    anchored_body = bool(entities and events and len(numbers) >= 2 and body_score >= 0.4)
    score = max(headline_score, 0.75 * body_score + 0.15 + 0.10) if anchored_body else headline_score
    if (delta is not None and delta > window_days) or conflicting_document or overlap > 0.8:
        return None
    if same_title:
        status = 'same_title_low_body_overlap'
    elif (entities and events and delta is not None and score >= threshold
          and (title_score >= 0.25 or anchored_body) and body_score >= 0.20):
        status = 'possible_rewritten_event'
    else:
        return None
    def reference(entry):
        row = entry['article']
        return {key: row.get(key) for key in ('source', 'url', 'title', 'published_at')} | {
            'files': entry['files'], 'uncheck_files': entry['uncheck_files'],
            'excerpt': (row.get('content') or '')[:600]}
    return {'status': status, 'event_score': round(score, 6),
            'evidence': {'title_tfidf_cosine': round(title_score, 6),
                         'body_tfidf_cosine': round(body_score, 6),
                         'existing_text_overlap': overlap, 'shared_entities': entities,
                         'shared_event_types': events, 'publication_gap_days': delta,
                         'shared_numeric_anchors': numbers,
                         'matching_route': 'same_title' if same_title else 'body_with_numeric_anchors' if anchored_body else 'headline_and_body',
                         'missing_publication_date': delta is None,
                         'shared_title_keywords': sorted(set(left['title_words']) & set(right['title_words']))},
            'left': reference(left), 'right': reference(right)}


def analyze(root=SCRAPERS, scopes=None, window_days=3, threshold=0.52):
    root = Path(root).resolve()
    if not root.is_relative_to(SCRAPERS):
        raise ValueError('Root must be inside scrapers')
    if scopes is None:
        symbol_root = root / 'tin_tuc_theo_ma'
        if not symbol_root.resolve().is_relative_to(SCRAPERS):
            raise ValueError('Symbol directory escapes scrapers')
        scopes = ['market'] + (sorted(p.name for p in symbol_root.iterdir() if p.is_dir())
                               if symbol_root.exists() else [])
    pairs, summaries = [], []
    all_uncheck, all_matched, rewritten_articles = set(), set(), set()
    for scope in sorted(set(scopes)):
        buckets, idf = load_scope(root, scope)
        entries = [e for bucket in buckets.values() for e in bucket.values()]
        unchecked = {e['article']['url'] for e in entries if e['uncheck_files']}
        all_uncheck.update(unchecked)
        found = []
        for left in buckets['cafef'].values():
            for right in buckets['fireant'].values():
                if not (left['uncheck_files'] or right['uncheck_files']):
                    continue
                match = compare(left, right, idf, window_days, threshold)
                if match:
                    match['scope'] = scope
                    found.append(match)
        matched = {p[side]['url'] for p in found for side in ('left', 'right')} & unchecked
        rewritten = [p for p in found if p['status'] == 'possible_rewritten_event']
        rewritten_articles.update({p[s]['url'] for p in rewritten for s in ('left', 'right')} & unchecked)
        all_matched.update(matched)
        summaries.append({'scope': scope, 'uncheck_records': sum(len(e['uncheck_files']) for e in entries),
                          'unique_uncheck_articles': len(unchecked), 'candidate_pairs': len(found),
                          'rewritten_candidate_pairs': len(rewritten),
                          'same_title_candidate_pairs': len(found) - len(rewritten),
                          'uncheck_articles_with_candidates': len(matched),
                          'uncheck_articles_without_candidates': len(unchecked - matched)})
        pairs.extend(found)
    pairs.sort(key=lambda p: (-p['event_score'], p['scope'], p['left']['url'], p['right']['url']))
    unique_pairs = {(p['left']['url'], p['right']['url']) for p in pairs}
    rewritten_pairs = {(p['left']['url'], p['right']['url']) for p in pairs
                       if p['status'] == 'possible_rewritten_event'}
    return {'schema_version': '1.0', 'generated_at': datetime.now(timezone.utc).isoformat(),
            'method': 'local_tfidf_entities_event_rules_v1',
            'limitations': ['Candidates require manual review; scores are not probabilities or fact verification.',
                            'No confirmed event count: candidate pairs may describe related but distinct events.',
                            'Rules can miss paraphrases, unknown entities and events; publication dates are not event dates.',
                            'Same-title disclosures are separated from differently worded candidates.'],
            'settings': {'window_days': window_days, 'threshold': threshold,
                         'headline_weights': {'title': 0.55, 'body': 0.35, 'shared_event': 0.10},
                         'body_anchor_route': {'min_body_cosine': 0.4, 'min_shared_numbers': 2,
                                               'score': '0.75 * body_cosine + 0.25 (shared entity and event)'},
                         'naive_publication_timezone': 'UTC+7'},
            'summary': {'uncheck_records': sum(s['uncheck_records'] for s in summaries),
                        'unique_uncheck_articles': len(all_uncheck),
                        'unique_candidate_pairs': len(unique_pairs),
                        'unique_rewritten_candidate_pairs': len(rewritten_pairs),
                        'unique_same_title_candidate_pairs': len(unique_pairs - rewritten_pairs),
                        'unique_uncheck_articles_with_candidates': len(all_matched),
                        'unique_uncheck_articles_with_rewritten_candidates': len(rewritten_articles),
                        'unique_uncheck_articles_without_candidates': len(all_uncheck - all_matched)},
            'scopes': summaries, 'candidates': pairs}


def markdown(report):
    summary = report['summary']
    lines = ['# Phân tích bài uncheck', '',
             f"- Tổng lượt record uncheck: {summary['uncheck_records']}",
             f"- Bài uncheck duy nhất theo URL: {summary['unique_uncheck_articles']}",
             f"- Cặp ứng viên duy nhất: {summary['unique_candidate_pairs']}",
             f"- Cặp khác cách viết: {summary['unique_rewritten_candidate_pairs']}",
             f"- Cặp cùng tiêu đề, khác phần nội dung: {summary['unique_same_title_candidate_pairs']}",
             f"- Bài uncheck có ứng viên khác cách viết: {summary['unique_uncheck_articles_with_rewritten_candidates']}",
             '', 'Đây là ứng viên cần đọc lại, không phải số sự kiện đã xác nhận. Không thay đổi marker.',
             'TF-IDF và quy tắc thực thể/sự kiện có thể bỏ sót hoặc ghép nhầm. Điểm không phải xác suất.', '',
             '| Phạm vi | Record uncheck | Bài duy nhất | Cặp khác cách viết | Cặp cùng tiêu đề |',
             '|---|---:|---:|---:|---:|']
    for s in report['scopes']:
        lines.append(f"| {s['scope']} | {s['uncheck_records']} | {s['unique_uncheck_articles']} | {s['rewritten_candidate_pairs']} | {s['same_title_candidate_pairs']} |")
    for i, pair in enumerate(report['candidates'], 1):
        kind = 'Khác cách viết — cần xem lại' if pair['status'] == 'possible_rewritten_event' else 'Cùng tiêu đề, nội dung không vượt ngưỡng'
        e = pair['evidence']
        lines.extend(['', f"## {i}. {pair['scope']} — {kind}", '',
                      f"Điểm xếp hạng: {pair['event_score']}; giống văn bản: {e['existing_text_overlap']:.3f}.",
                      f"Thực thể chung: {', '.join(e['shared_entities']) or 'không nhận diện'}; loại sự kiện: {', '.join(e['shared_event_types']) or 'không nhận diện'}.",
                      f"Số liệu chung (chỉ làm manh mối): {', '.join(e['shared_numeric_anchors']) or 'không có'}.",
                      f"Khoảng cách xuất bản (ngày): {e['publication_gap_days']}."])
        for side in ('left', 'right'):
            a = pair[side]
            lines.extend(['', f"**{a['source']}**: {a['title']}", '', a['url'], '', a['excerpt'].replace('\n', ' ')])
    return '\n'.join(lines) + '\n'


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=SCRAPERS)
    parser.add_argument('--scopes', nargs='+')
    parser.add_argument('--window-days', type=float, default=3)
    parser.add_argument('--threshold', type=float, default=0.52)
    parser.add_argument('--output', type=Path, default=SCRAPERS / 'uncheck_analysis')
    args = parser.parse_args(argv)
    if not math.isfinite(args.window_days) or args.window_days < 0 or not 0 <= args.threshold <= 1:
        parser.error('window-days must be finite and nonnegative; threshold must be 0..1')
    output = args.output.resolve()
    if not output.is_relative_to(SCRAPERS):
        parser.error('Output must be inside scrapers')
    targets = [output / 'report.json', output / 'report.md']
    if any(not p.resolve().is_relative_to(SCRAPERS) for p in targets):
        parser.error('Report path escapes scrapers')
    report = analyze(args.root, args.scopes, args.window_days, args.threshold)
    output.mkdir(parents=True, exist_ok=True)
    targets[0].write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    targets[1].write_text(markdown(report), encoding='utf-8')
    print(json.dumps(report['summary'], ensure_ascii=False, indent=2))
    print(f'Reports: {output}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
