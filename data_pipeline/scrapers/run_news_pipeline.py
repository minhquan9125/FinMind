"""One entry point: collect news, cross-check, analyze uncheck and report."""
import argparse
import json
import re
import sys
import unicodedata
from datetime import datetime, timezone
from pathlib import Path

import analyze_uncheck_events as events
import stock_news_collector as collector
from news_storage import SCRAPERS, daily_path


def parse_symbols(value):
    symbols = list(dict.fromkeys(re.split(r'[\s,;]+', value.strip().upper())))
    if not symbols or any(not re.fullmatch(r'[A-Z][A-Z0-9]{1,9}', s) for s in symbols):
        raise ValueError('Nhập mã hợp lệ, ví dụ FPT hoặc FPT HPG VCB.')
    return symbols


def inventory(root, extra_scopes=()):
    """Count saved records (not unique articles across folders/days)."""
    rows, errors = [], []
    symbols = root / 'tin_tuc_theo_ma'
    if not symbols.resolve().is_relative_to(SCRAPERS):
        raise ValueError('Symbol directory escapes scrapers')
    scopes = sorted(set(['market', *extra_scopes] +
                        ([p.name for p in symbols.iterdir() if p.is_dir()] if symbols.exists() else [])))
    for scope in scopes:
        for source in ('cafef', 'fireant'):
            folder = daily_path(root, source, scope, '01-01-2000').parent
            files = sorted(folder.glob('*.json'))
            counts = {'articles': 0, 'check': 0, 'uncheck': 0, 'unmarked': 0}
            valid_files = []
            for path in files:
                try:
                    if not path.resolve().is_relative_to(SCRAPERS):
                        raise ValueError('News file escapes scrapers')
                    articles = collector.read_articles(path, source).values()
                    for a in articles:
                        counts['articles'] += 1
                        counts[a['marker'] if a.get('marker') in ('check', 'uncheck') else 'unmarked'] += 1
                    valid_files.append(path.relative_to(root).as_posix())
                except (OSError, ValueError, TypeError) as exc:
                    errors.append({'file': path.relative_to(root).as_posix(), 'error': str(exc)})
            rows.append({'folder': folder.relative_to(root).as_posix(), 'scope': scope, 'source': source,
                         'json_files': len(files), 'readable_files': len(valid_files),
                         'files': [p.relative_to(root).as_posix() for p in files], **counts})
    return {'folders': rows, 'errors': errors}


def display_width(value):
    return sum(0 if unicodedata.combining(c) else
               2 if unicodedata.east_asian_width(c) in ('W', 'F') else 1 for c in value)


def aligned_table(headers, rows, numeric_columns=()):
    """Readable in both monospace terminals and Markdown viewers."""
    cells = [[unicodedata.normalize('NFC', str(value)).replace('\n', ' ').replace('|', '\\|')
              for value in row] for row in [headers, *rows]]
    widths = [max(4 if i in numeric_columns else 3,
                  *(display_width(row[i]) for row in cells)) for i in range(len(headers))]

    def render(row):
        values = []
        for i, value in enumerate(row):
            padding = ' ' * (widths[i] - display_width(value))
            values.append(padding + value if i in numeric_columns else value + padding)
        return '| ' + ' | '.join(values) + ' |'

    separators = ['-' * (width - 1) + ':' if i in numeric_columns else '-' * width
                  for i, width in enumerate(widths)]
    return [render(cells[0]), render(separators), *(render(row) for row in cells[1:])]


def format_report(report):
    summary = report['summary']
    lines = ['# Báo cáo chạy thu thập tin', '',
             f"Thời gian: {report['started_at']} — mã: {', '.join(report['symbols'])}",
             f"Kết quả: {report['status']}; hạn mức {report['limit']} bài mỗi nguồn/phạm vi.", '',
             f"- Nhóm đủ hạn mức và không lỗi: {summary['successful_collection_groups']}/{summary['requested_collection_groups']}",
             f"- Bài hợp lệ trong lượt chạy (gồm bài đã lưu): {summary['accepted_articles']}",
             f"- Lượt bài thêm mới vào JSON hôm nay: {summary['new_article_records']}",
             f"- File dữ liệu được ghi: {summary['saved_files']}; file mới tạo: {summary['created_files']}",
             f"- Cross-check: {report['collector'].get('crosscheck', {}).get('status', 'not_run')}",
             f"- Record cross-check thành công: {summary['crosschecked_records']}; check: {summary['check_records']}; uncheck: {summary['uncheck_records']}",
             f"- Phân tích uncheck: {report['event_analysis']['status']}",
             f"- Bài uncheck được phân tích (URL duy nhất): {summary['analyzed_uncheck_articles']}",
             f"- Cặp ứng viên khác cách viết: {summary['rewritten_candidate_pairs']}; số bài uncheck liên quan: {summary['rewritten_candidate_articles']}",
             f"- Cặp cùng tiêu đề: {summary['same_title_candidate_pairs']}", '',
             'Check là độ giống văn bản >80%. Ứng viên cùng sự kiện cần đọc lại; phân tích không tự đổi marker.',
             'Record có thể lặp giữa ngày/mã. Các chỉ số cross-check và phân tích chỉ thuộc phạm vi lượt chạy.', '',
             '## Thu thập từng nguồn/phạm vi', '']
    collection_rows = []
    collection_errors = []
    for item in report['collector'].get('collection', []):
        accepted = sum(r['accepted'] for r in item['results'])
        errors = sum(r['errors'] for r in item['results'])
        collection_rows.append([item['scope'], item['source'], f"{accepted}/{report['limit']}",
                                errors, item['new_articles'], 'có' if item['saved'] else 'không'])
        if item.get('error'):
            collection_errors.append(f"Lỗi {item['file']}: {item['error']}")
    lines.extend(aligned_table(['Phạm vi', 'Nguồn', 'Hợp lệ/hạn mức', 'Lỗi', 'Thêm mới', 'Ghi file'],
                               collection_rows, (2, 3, 4)))
    if collection_errors:
        lines.extend(['', *collection_errors])
    lines.extend(['', '## Dữ liệu hiện có theo từng thư mục (mọi ngày)', ''])
    inventory_rows = []
    for row in report['inventory']['folders']:
        inventory_rows.append([row['folder'], row['json_files'], row['created_files'],
                               row['articles'], row['check'], row['uncheck'], row['unmarked']])
    lines.extend(aligned_table(['Thư mục', 'File JSON', 'File mới lượt này', 'Record', 'Check',
                                'Uncheck', 'Chưa marker'], inventory_rows, (1, 2, 3, 4, 5, 6)))
    if report['errors']:
        lines.extend(['', '## Lỗi', ''])
        lines.extend(f'- {error}' for error in report['errors'])
    lines.extend(['', 'Bằng chứng ghép cặp: `events.md` và `events.json` cạnh báo cáo này.'])
    return '\n'.join(lines) + '\n'


def run_pipeline(symbols, limit=10, root=SCRAPERS, only_symbols=False, new_only=False):
    root = Path(root).resolve()
    if not root.is_relative_to(SCRAPERS):
        raise ValueError('Root must be inside scrapers')
    output = root / 'pipeline_reports'
    for name in ('latest.json', 'latest.md', 'events.json', 'events.md'):
        if not (output / name).resolve().is_relative_to(SCRAPERS):
            raise ValueError('Report path escapes scrapers')
    started = datetime.now(timezone.utc).isoformat()
    scopes = ([] if only_symbols else ['market']) + symbols
    before = inventory(root, scopes)
    old_files = {p for row in before['folders'] for p in row['files']}
    args = ['--source', 'all', '--symbols', *symbols, '--limit', str(limit)]
    if root != SCRAPERS:
        args.extend(['--output', str(root)])
    if only_symbols:
        args.append('--only-symbols')
    if new_only:
        args.append('--new-only')
    print(f"\nCào CafeF + FireAnt: {', '.join(scopes)}, {limit} bài mỗi nguồn/phạm vi.", flush=True)
    collection, errors = {}, []
    try:
        code = collector.main(args, run_report=collection)
    except Exception as exc:
        code = 1
        errors.append(f'Collector: {exc}')
    if code:
        errors.append('Thu thập/đối chiếu chưa hoàn tất; xem kết quả từng nhóm và lỗi collector.')
    if collection.get('migration_error'):
        errors.append('Migration: ' + collection['migration_error'])
    if collection.get('crosscheck', {}).get('error'):
        errors.append('Cross-check: ' + collection['crosscheck']['error'])
    event_result = {'status': 'failed'}
    event_report = None
    print('\nPhân tích các bài uncheck trong phạm vi vừa chạy...', flush=True)
    try:
        event_report = events.analyze(root, scopes=scopes)
        event_result = {'status': 'ok', 'summary': event_report['summary']}
    except Exception as exc:
        errors.append(f'Phân tích uncheck: {exc}')
        event_result['error'] = str(exc)
    after = inventory(root, scopes)
    errors.extend(f"Đọc {e['file']}: {e['error']}" for e in after['errors'])
    for row in after['folders']:
        row['created_files'] = len(set(row['files']) - old_files)
    collected = collection.get('collection', [])
    cross = collection.get('crosscheck', {})
    cross_scopes = cross.get('scopes', []) if cross.get('status') == 'ok' else []
    event_summary = event_result.get('summary', {})
    summary = {
        'requested_collection_groups': len(scopes) * 2,
        'successful_collection_groups': sum(i['status'] == 'ok' for i in collected),
        'accepted_articles': sum(r['accepted'] for i in collected for r in i['results']),
        'new_article_records': sum(i['new_articles'] for i in collected),
        'saved_files': sum(i['saved'] for i in collected),
        'created_files': sum(row['created_files'] for row in after['folders']),
        'crosschecked_records': sum(s['total'] for s in cross_scopes),
        'check_records': sum(s['check'] for s in cross_scopes),
        'uncheck_records': sum(s['uncheck'] for s in cross_scopes),
        'analyzed_uncheck_articles': event_summary.get('unique_uncheck_articles'),
        'rewritten_candidate_pairs': event_summary.get('unique_rewritten_candidate_pairs'),
        'rewritten_candidate_articles': event_summary.get('unique_uncheck_articles_with_rewritten_candidates'),
        'same_title_candidate_pairs': event_summary.get('unique_same_title_candidate_pairs'),
    }
    report = {'schema_version': '1.0', 'started_at': started,
              'finished_at': datetime.now(timezone.utc).isoformat(), 'symbols': symbols,
              'limit': limit, 'scopes': scopes, 'new_only': new_only,
              'status': 'ok' if not errors else 'partial_or_failed', 'summary': summary,
              'collector': collection, 'event_analysis': event_result, 'inventory': after, 'errors': errors}
    output.mkdir(parents=True, exist_ok=True)
    if event_report is not None:
        collector.write_payload(output / 'events.json', event_report)
        (output / 'events.md').write_text(events.markdown(event_report), encoding='utf-8')
    else:
        # Replace stale successful results with explicit failure information.
        collector.write_payload(output / 'events.json', event_result)
        (output / 'events.md').write_text('Phân tích thất bại: ' + event_result.get('error', ''), encoding='utf-8')
    collector.write_payload(output / 'latest.json', report)
    content = format_report(report)
    (output / 'latest.md').write_text(content, encoding='utf-8')
    print('\n' + content)
    print(f'Báo cáo: {output / "latest.md"}')
    return int(bool(errors)), report


def main(argv=None):
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, 'reconfigure'):
            stream.reconfigure(encoding='utf-8')
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--symbols', nargs='+', help='Skip interactive prompt, e.g. FPT HPG')
    parser.add_argument('--limit', type=int, default=10)
    parser.add_argument('--only-symbols', action='store_true')
    parser.add_argument('--new-only', action='store_true')
    args = parser.parse_args(argv)
    if args.limit < 1:
        parser.error('--limit must be at least 1')
    if args.symbols:
        try:
            symbols = parse_symbols(' '.join(args.symbols))
        except ValueError as exc:
            parser.error(str(exc))
    else:
        while True:
            try:
                symbols = parse_symbols(input('Nhập mã cổ phiếu (ví dụ FPT hoặc FPT HPG VCB): '))
                break
            except ValueError as exc:
                print(exc)
            except (EOFError, KeyboardInterrupt):
                print('\nĐã hủy.')
                return 1
    code, _ = run_pipeline(symbols, args.limit, only_symbols=args.only_symbols, new_only=args.new_only)
    return code


if __name__ == '__main__':
    raise SystemExit(main())
