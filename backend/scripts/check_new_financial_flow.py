"""Collect fresh data in an isolated folder and validate clean financial chunks.

No database connection, embeddings or shared source-file overwrites.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT/'backend'), str(ROOT/'backend/scripts'),
               str(ROOT/'data_pipeline/financial_data'), str(ROOT/'data_pipeline/FinancialCleaner')]
from collect_financial_data import TARGET_SYMBOLS, VietnamStockDataCollector
from cleaner import codec
from cleaner.core import clean_financial_data
from cleaner.mapping import load_mapping, MAPPING_PATH
from cleaner.display import add_display_values, load_display_config
from import_clean_financials import read_input, SECTION, stable_id
from check_financial_flow import check_documents


def validate_new_file(source, output_root):
    raw = source.read_bytes()
    payload = codec.loads(raw.decode('utf-8-sig'))
    maps, labels, meta = load_mapping(payload['industry'])
    clean = clean_financial_data(payload, section_maps=maps, labels_vi=labels, meta_keys=meta)
    add_display_values(clean, load_display_config())
    clean['nguồn_dữ_liệu'] = {
        'file_nguồn': source.name, 'sha256_nguồn': hashlib.sha256(raw).hexdigest(),
        'sha256_mapping': hashlib.sha256(MAPPING_PATH.read_bytes()).hexdigest(),
        'nguồn_tài_chính': payload['sources']['fundamentals'],
        'thời_điểm_tạo_nguồn': payload['generated_at'],
        'đơn_vị_giá_trị': 'Giữ nguyên đơn vị và giá trị trong JSON nguồn; không quy đổi hoặc làm tròn.',
        'bỏ_chỉ_số_định_giá': False,
    }
    dest = output_root/'clean'/payload['symbol']/'tai_chinh_clean.json'
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(codec.dumps(clean)+'\n', encoding='utf-8')
    item = read_input(dest)
    rows = []
    for period, section, metric, value in item['values']:
        report = stable_id('clean-report', item['symbol'], period, item['digest'])
        metric_id = stable_id('metric', item['data']['ngành'], SECTION[section], metric['mã_chuẩn'])
        rows.append({'report_id': str(report), 'symbol': item['symbol'],
                     'company_name': item['data']['tên_doanh_nghiệp'], 'period_code': period,
                     'statement_scope': 'UNKNOWN', 'section': SECTION[section],
                     'code': metric['mã_chuẩn'], 'canonical_name': metric['tên_chỉ_tiêu'],
                     'observation_id': str(stable_id('observation', report, metric_id)),
                     'value': value, 'unit': 'SOURCE_NATIVE'})
    return {'symbol': item['symbol'], 'generated_at': payload['generated_at'],
            'normalized_sha256': hashlib.sha256(raw).hexdigest(),
            'price_sessions': len(payload['price_history']),
            'sections': payload['meta'], **check_documents(rows)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--symbols', nargs='+', choices=TARGET_SYMBOLS, default=TARGET_SYMBOLS)
    args = parser.parse_args()
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    output = ROOT/'backend/.tmp/new-financial-flow'/stamp
    collector = VietnamStockDataCollector(output_root=output)
    report = {'database_writes': False, 'embedding_calls': False, 'output': str(output),
              'requested_symbols': args.symbols, 'results': []}
    for i, symbol in enumerate(args.symbols, 1):
        try:
            collected = collector.process_stock(i, len(args.symbols), symbol)
            if collected['status'] != 'PASSED':
                result = {'symbol': symbol, 'status': 'FAILED', 'collection': collected}
            else:
                result = {'status': 'PASS', 'collection': collected,
                          **validate_new_file(output/'normalized'/f'{symbol}.json', output)}
        except Exception as exc:
            result = {'symbol': symbol, 'status': 'FAILED', 'error_type': type(exc).__name__, 'message': str(exc)}
        report['results'].append(result)
        (output/'result.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
        print(json.dumps({'validated': result}, ensure_ascii=False), flush=True)
    print('REPORT', output/'result.json', flush=True)
    return 0 if all(r['status'] == 'PASS' for r in report['results']) else 1


if __name__ == '__main__':
    sys.exit(main())
