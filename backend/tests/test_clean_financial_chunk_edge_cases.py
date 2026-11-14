"""WBS19 diagnostics: clean JSON and financial DB-shaped rows; no PDF/network.

These tests cover the clean reader, invalid report guards and chunk roundtrips
without PDF files, a live database or network access.
"""
from collections import Counter
import copy
from decimal import Decimal
import json
from pathlib import Path
import random
import sys

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'backend/scripts'))
from import_clean_financials import read_input, SECTION, stable_id
from src.documents.db_chunking import financial_documents, chunk_document
from src.documents.chunk_reconstruction import reconstruct_document_chunk


def clean_payload():
    return {'mã_chứng_khoán': 'FPT', 'tên_doanh_nghiệp': 'Công ty FPT',
            'ngành': 'TECH', 'tên_ngành': 'Công nghệ thông tin', 'sàn': 'HOSE',
            'báo_cáo_tài_chính': {
                'bảng_cân_đối_kế_toán': [{
                    'kỳ_báo_cáo': '2026-Q2', 'loại_kỳ': 'Quý', 'năm': 2026, 'quý': 2,
                    'chỉ_tiêu': [{'mã_chuẩn': 'TOTAL_ASSETS', 'tên_chỉ_tiêu': 'Tổng tài sản',
                                 'trường_gốc': 'bsa53', 'giá_trị': 123456789}]}],
                'kết_quả_kinh_doanh': [], 'lưu_chuyển_tiền_tệ': [], 'chỉ_số_tài_chính': []}}


def read_clean(tmp_path, payload):
    folder = tmp_path / 'FPT'
    folder.mkdir(exist_ok=True)
    path = folder / 'tai_chinh_clean.json'
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding='utf-8')
    item = read_input(path)
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
    return rows


def rows(n, report='r1', period='2026-Q2', section='BALANCE_SHEET'):
    # Shape of the SELECT joining observations/metrics after clean JSON import.
    return [{'report_id': report, 'symbol': 'FPT', 'company_name': 'Công ty FPT',
             'period_code': period, 'statement_scope': 'UNKNOWN', 'section': section,
             'code': f'TEST_{i:05}', 'canonical_name': f'Chỉ tiêu thử {i}',
             'observation_id': f'{report}-{section}-{i}', 'value': Decimal(i),
             'unit': 'SOURCE_NATIVE'} for i in range(n)]


def assert_coverage_and_roundtrip(doc, sample_only=False):
    chunks = chunk_document(doc)
    expected = Counter(r.key for s in doc.sections for r in s.rows)
    actual = Counter(k for c in chunks for k in c.locator['row_keys'])
    assert actual == expected
    assert len({c.chunk_id for c in chunks}) == len(chunks)
    assert [c.to_dict() for c in chunks] == [c.to_dict() for c in chunk_document(doc)]
    chosen = [chunks[0], chunks[len(chunks)//2], chunks[-1]] if sample_only else chunks
    for c in chosen:
        assert c.text.startswith(doc.sections[c.section_index].header + '\n')
        assert reconstruct_document_chunk(doc, c.locator, c.content_hash).text == c.text
    return chunks


def test_clean_json_goes_through_real_reader_without_database(tmp_path):
    source = clean_payload()
    before = copy.deepcopy(source)
    rs = read_clean(tmp_path, source)
    assert source == before
    assert rs[0]['value'] == Decimal('123456789')
    assert_coverage_and_roundtrip(financial_documents(rs)[0])


def test_very_long_clean_metric_name_stays_with_its_code_and_value(tmp_path):
    source = clean_payload()
    source['báo_cáo_tài_chính']['bảng_cân_đối_kế_toán'][0]['chỉ_tiêu'][0]['tên_chỉ_tiêu'] = 'Tên chỉ tiêu dài ' * 150
    doc = financial_documents(read_clean(tmp_path, source))[0]
    chunks = assert_coverage_and_roundtrip(doc)
    assert len(chunks) == 1 and len(chunks[0].locator['row_keys']) == 1
    assert doc.sections[0].rows[0].text in chunks[0].text
    # Intentional row-preservation exception: the indivisible row exceeds budget.
    assert chunks[0].token_count > 130


@pytest.mark.parametrize('change', ['missing-period', 'wrong-quarter', 'duplicate-metric', 'wrong-field-code'])
def test_clean_reader_rejects_invalid_period_or_mapping(tmp_path, change):
    source = clean_payload()
    report = source['báo_cáo_tài_chính']['bảng_cân_đối_kế_toán'][0]
    if change == 'missing-period': del report['kỳ_báo_cáo']
    if change == 'wrong-quarter': report['quý'] = 3
    if change == 'duplicate-metric': report['chỉ_tiêu'] *= 2
    if change == 'wrong-field-code': report['chỉ_tiêu'][0]['trường_gốc'] = 'bsa1'
    with pytest.raises((ValueError, KeyError)):
        read_clean(tmp_path, source)


def test_large_report_covers_1200_indicators_once():
    doc = financial_documents(rows(1200))[0]
    chunks = assert_coverage_and_roundtrip(doc, sample_only=True)
    assert len(chunks) > 1
    assert all(c.token_count <= 130 for c in chunks)


def test_uneven_periods_and_sections_do_not_mix():
    source = (rows(75, 'r1', '2026-Q2') + rows(3, 'r1', '2026-Q2', 'INCOME_STATEMENT')
              + rows(70, 'r2', '2026-Q1') + rows(1, 'r3', '2025-YEAR'))
    docs = financial_documents(source)
    assert len(docs) == 3
    for doc in docs:
        for chunk in assert_coverage_and_roundtrip(doc):
            assert chunk.locator['source_id'] == doc.source_id
            assert all(k.startswith(doc.source_id + '-') for k in chunk.locator['row_keys'])


def test_reordered_indicators_have_identical_chunks_per_report():
    source = rows(43) + rows(7, 'r2', '2026-Q1')
    shuffled = copy.deepcopy(source)
    random.Random(19).shuffle(shuffled)
    def result(rs):
        return {d.source_id: [c.to_dict() for c in chunk_document(d)] for d in financial_documents(rs)}
    assert result(source) == result(shuffled)


def test_missing_name_uses_metric_code():
    source = rows(1)
    source[0]['canonical_name'] = None
    doc = financial_documents(source)[0]
    assert 'TEST_00000' in doc.sections[0].rows[0].text
    assert_coverage_and_roundtrip(doc)


def test_null_value_is_explicit_not_zero():
    source = rows(1)
    source[0]['value'] = None
    text = financial_documents(source)[0].sections[0].rows[0].text
    assert 'không có dữ liệu' in text
    assert ': 0' not in text


def test_zero_and_negative_are_not_dropped():
    source = rows(2)
    source[1]['value'] = Decimal('-42')
    doc = financial_documents(source)[0]
    assert len(doc.sections[0].rows) == 2
    assert ': 0 (đơn vị chưa xác minh)' in doc.sections[0].rows[0].text
    assert ': -42 (đơn vị chưa xác minh)' in doc.sections[0].rows[1].text
    assert_coverage_and_roundtrip(doc)


# Regression guards for the five issues found during the initial audit.
def test_unknown_source_unit_does_not_claim_million_vnd():
    doc = financial_documents(rows(1))[0]
    assert 'triệu VND' not in doc.sections[0].header, 'SOURCE_NATIVE cannot be labelled as million VND'


@pytest.mark.parametrize('field,value', [('period_code', '2026-Q1'), ('symbol', 'VCB')])
def test_conflicting_metadata_for_same_report_is_rejected(field, value):
    source = rows(2)
    source[1][field] = value
    with pytest.raises(ValueError, match='.'):
        financial_documents(source)


@pytest.mark.parametrize('period', ['2026-Q1', '2025-YEAR', None, ''])
@pytest.mark.parametrize('reverse', [False, True])
def test_conflicting_period_is_rejected_across_sections_in_either_order(period, reverse):
    source = rows(1) + rows(1, section='INCOME_STATEMENT')
    source[1]['period_code'] = period
    if reverse:
        source.reverse()
    with pytest.raises(ValueError, match=r'Báo cáo r1: period_code không thống nhất'):
        financial_documents(iter(source))


def test_period_validation_preserves_valid_input_and_roundtrip():
    source = rows(2) + rows(1, section='INCOME_STATEMENT')
    before = copy.deepcopy(source)
    doc = financial_documents(source)[0]
    assert source == before
    assert doc.meta['period_code'] == '2026-Q2'
    assert_coverage_and_roundtrip(doc)


@pytest.mark.parametrize('symbol', ['VCB', None, ''])
@pytest.mark.parametrize('reverse', [False, True])
def test_conflicting_company_is_rejected_across_sections_in_either_order(symbol, reverse):
    source = rows(1) + rows(1, section='INCOME_STATEMENT')
    source[1]['symbol'] = symbol
    if reverse:
        source.reverse()
    before = copy.deepcopy(source)
    with pytest.raises(ValueError, match=r'Báo cáo r1: symbol không thống nhất'):
        financial_documents(iter(source))
    assert source == before


def test_different_companies_in_separate_reports_are_not_mixed():
    source = rows(2) + rows(2, report='r2')
    for row in source[2:]:
        row.update(symbol='VCB', company_name='Ngân hàng VCB')
    docs = financial_documents(source)
    assert {doc.source_id: doc.symbol for doc in docs} == {'r1': 'FPT', 'r2': 'VCB'}
    for doc in docs:
        assert_coverage_and_roundtrip(doc)


def test_duplicate_observation_identity_is_rejected():
    source = rows(2)
    source[1]['observation_id'] = source[0]['observation_id']
    with pytest.raises(ValueError, match='.'):
        financial_documents(source)


@pytest.mark.parametrize('placement', ['same-section', 'other-section', 'other-report'])
@pytest.mark.parametrize('reverse', [False, True])
def test_duplicate_identity_is_rejected_across_entire_input(placement, reverse):
    source = rows(1) + rows(1, report='r2' if placement == 'other-report' else 'r1',
                            section='INCOME_STATEMENT' if placement == 'other-section' else 'BALANCE_SHEET')
    source[1]['observation_id'] = source[0]['observation_id']
    source[1]['value'] = Decimal('999')
    if reverse:
        source.reverse()
    before = copy.deepcopy(source)
    with pytest.raises(ValueError, match=r'observation_id trùng') as error:
        financial_documents(iter(source))
    assert source[0]['observation_id'] in str(error.value)
    assert source == before


def test_duplicate_identical_row_is_rejected_instead_of_silently_deduplicated():
    source = rows(1)
    with pytest.raises(ValueError, match=r'observation_id trùng'):
        financial_documents(source + copy.deepcopy(source))


def test_same_metric_code_with_distinct_observations_in_different_reports_is_valid():
    source = rows(2) + rows(2, report='r2', period='2026-Q1')
    assert source[0]['code'] == source[2]['code']
    assert source[0]['observation_id'] != source[2]['observation_id']
    docs = financial_documents(source)
    assert len(docs) == 2
    for doc in docs:
        assert_coverage_and_roundtrip(doc)


def test_missing_unit_is_marked_unverified_in_row():
    source = rows(1)
    source[0]['unit'] = None
    text = financial_documents(source)[0].sections[0].rows[0].text
    assert 'chưa xác minh' in text, 'Missing source unit needs an explicit warning'


@pytest.mark.parametrize('unit', [None, '', '  ', 'SOURCE_NATIVE', 'source_native'])
def test_unverified_unit_warning_stays_with_each_financial_row(unit):
    source = rows(2)
    for row in source:
        row['unit'] = unit
    doc = financial_documents(source)[0]
    assert all('đơn vị chưa xác minh' in row.text for row in doc.sections[0].rows)
    assert_coverage_and_roundtrip(doc)


def test_explicit_vnd_keeps_value_format_without_unknown_unit_warning():
    source = rows(1)
    source[0].update(unit='VND', value=Decimal('2000000'))
    text = financial_documents(source)[0].sections[0].rows[0].text
    assert text.endswith('2.00 triệu VND')
    assert 'chưa xác minh' not in text
