"""Ownership-table rule for WBS03 (FPT/CTG/CMG layouts); no database is accessed."""

import json
from pathlib import Path
import unittest

from backend.scripts.build_registry_revision import apply_changes
from backend.src.sprint4_runtime.relation_extractor import extract_candidates

RUNTIME = Path(__file__).resolve().parents[1] / 'src' / 'sprint4_runtime'


def company(entity_id, name, *aliases, tickers=()):
    return {'entity_id': entity_id, 'entity_type': 'Company', 'canonical_name': name,
            'aliases': [name, *aliases, *tickers], 'ticker_aliases': list(tickers),
            'identity_key': 'name:' + name.casefold(), 'verified': True}


REGISTRY = [
    company('p', 'Công ty Cổ phần Mẹ Alpha', tickers=('ALP',)),
    company('s1', 'Công ty TNHH Phần mềm Alpha'),
    company('s2', 'Công ty Cổ phần Viễn thông Alpha'),
    company('a1', 'Công ty Cổ phần Bán lẻ Kỹ thuật số Alpha'),
    company('l1', 'Công ty Cho thuê tài chính TNHH MTV Ngân hàng TMCP Alpha Việt Nam'),
    company('l2', 'Ngân hàng TNHH Alpha tại Lào'),
    company('jv', 'Ngân hàng TNHH Indochina'),
    company('g', 'Công ty TNHH Alpha Global', 'Alpha Global'),
    company('g1', 'Công ty TNHH Alpha Japan'),
    company('x', 'Công ty Cổ phần Chứng khoán'),  # industry-only name, must never match
    company('fpt_like', 'Công ty Cổ phần Gamma'),
]
DOC = 'doc:' + 'a' * 64


def envelope(pages, issuer_name='Công ty Cổ phần Mẹ Alpha'):
    """pages: {page: [chunk text, ...]} in reading order."""
    chunks = []
    for page, texts in pages.items():
        for index, text in enumerate(texts):
            chunk_id = f'p{page}:b{index}'
            chunks.append({'document_id': DOC, 'document_version': 'b' * 64, 'chunk_id': chunk_id, 'text': text,
                           'locator': {'page': page, 'block_id': chunk_id, 'bbox': [0, 0, 1, 1]}})
    return {'schema_version': '2.1.0', 'corpus_id': 'test', 'dataset_version': 'test',
            'documents': [{'document_id': DOC, 'document_version': 'b' * 64, 'source_sha256': 'a' * 64,
                           'extraction_sha256': 'b' * 64, 'source_path': 'x.pdf', 'extraction_path': 'x.json',
                           'doc_type': 'ANNUAL_REPORT', 'issuer_symbol': 'ALP', 'issuer_company_id': 'c1',
                           'issuer_company_name': issuer_name, 'title': 'ALP — Báo cáo thường niên 2025'}],
            'chunks': chunks, 'entities': [], 'mentions': [], 'relations': []}


def run(pages, **kwargs):
    diagnostics = []
    result = extract_candidates(envelope(pages, **kwargs), REGISTRY, diagnostics)
    # Only this rule's output: the sentence rules have their own tests.
    triples = sorted(((r['relation_type'], r['subject_id'], r['object_id'], r['attributes'].get('ownership_percent'),
                       r['temporal']['as_of']) for r in result['relations']
                      if r['attributes'].get('inference_basis') == 'ownership_table'), key=str)
    return triples, diagnostics, result


FPT_LIKE = {175: [
    '02 DẤU ẤN 2025 (i) Công ty con trực tiếp\n'
    'Tại ngày 31/12/2025 và 31/12/2024\n'
    '04 CHIẾN LƯỢC PHÁT TRIỂN Công ty con Hoạt động chính Nơi thành lập Tỷ lệ sở hữu Tỷ lệ quyền biểu quyết\n'
    '05 PHÂN TÍCH HOẠT ĐỘNG KINH DOANH Công ty TNHH Phần mềm Alpha Cung cấp phần mềm Tòa nhà A, Phường 100% 100%\n'
    'sản phẩm phần mềm Cầu Giấy, Hà Nội\n'
    '06 QUẢN TRỊ CÔNG TY\n'
    'Công ty Cổ phần Cung cấp dịch vụ ADSL, Tầng 2, số 17 phố Duy Tân, 45,66% (*)\n'
    'Viễn thông Alpha (*) cho thuê đường truyền, Phường Cầu Giấy',
], 176: [
    '(ii) Công ty liên kết trực tiếp:\n'
    'Tại ngày 31/12/2025 và 31/12/2024\n'
    'Công ty con Hoạt động chính Nơi thành lập Tỷ lệ sở hữu Tỷ lệ quyền biểu quyết\n'
    'Công ty Cổ phần Bán lẻ Bán lẻ máy vi tính, Số 261 Khánh Hội, 46,54% 46,54%\n'
    '04 PHÂN TÍCH HOẠT ĐỘNG KINH DOANH\n'
    'Kỹ thuật số Alpha phần mềm và thiết bị TP. Hồ Chí Minh',
]}

CTG_LIKE = {142: [
    '31.12.2025 31.12.2024\nSTT TÊN CÔNG TY ĐƯỢC THÀNH LẬP THEO TỶ LỆ SỞ HỮU\nCông ty con\n'
    '1 Công ty Cho Quyết định Thành lập số 53/1998/ Cho thuê 100% 100% 100% 100%\n'
    'thuê tài chính QĐ-NHNN5 do Thống đốc Ngân hàng tài chính\n'
    'TNHH MTV Nhà nước cấp ngày 26 tháng 1 năm\n'
    'Ngân hàng 1998, Giấy phép Hoạt động số 04/GP-',
    'TMCP CTCTTC do Thống đốc Ngân hàng Nhà\n'
    'Doanh nghiệp số 0101047075 do Sở\n'
    'Alpha Việt Nam năm 1998, Giấy Chứng nhận\n'
    '17 tháng 01 năm 2025',
], 143: [
    '31.12.2025 31.12.2024\n'
    '8 Ngân hàng Giấy phép hoạt động số 37/ Tài chính 100% 100% 100% 100%\n'
    'TNHH Alpha NHCHDCNDL do Ngân hàng Trung ngân',
    'tại Lào cấp ngày 30 tháng 8 năm 2024. Đăng\nCông ty liên doanh\n'
    '1 Ngân hàng Giấy phép Thành lập và Hoạt động số Tài chính 50% 50% 50% 50%\n'
    'TNHH 08/NH-GP do Ngân hàng Nhà nước ngân\n'
    'cấp ngày 29 tháng 10 năm 1992 và các hàng\nIndochina',
]}

CMG_LIKE = {7: [
    'a. Cơ cấu quản lý theo các khối kinh doanh b. Các công ty con, công ty liên kết:\n'
    'STT Tên Công ty Tên viết tắt Địa chỉ Lĩnh vực hoạt động Tỷ lệ sở hữu\n'
    '4 4 Công ty TNHH Alpha Global Alpha Global Tower, số 11 phố Duy Tân Xuất bản phần mềm 100%\n'
    'Các công ty con của Công ty TNHH Alpha Global (Alpha Global) bao gồm:\n'
    'Công ty TNHH Alpha Japan Alpha Japan Yokohama, Nhật Bản Dịch vụ phần mềm Alpha Global sở hữu 100% vốn góp\n'
    'Công ty TNHH Không Biết Unknown Seoul Dịch vụ phần mềm Alpha Global sở hữu 100% vốn góp\n'
    '5 5 Công ty Cổ phần Viễn thông Alpha Alpha Telecom Tower, Hà Nội Viễn thông 54,628%',
]}


class OwnershipTableTests(unittest.TestCase):
    def test_fpt_layout_menu_lines_split_name_and_associate_section(self):
        triples, diagnostics, result = run(FPT_LIKE)
        self.assertEqual(triples, [
            ('HAS_ASSOCIATE', 'p', 'a1', '46.54', '2025-12-31'),
            ('HAS_SUBSIDIARY', 'p', 's1', '100', '2025-12-31'),
            ('HAS_SUBSIDIARY', 'p', 's2', '45.66', '2025-12-31'),
        ])
        self.assertEqual(diagnostics, [])
        relation = next(r for r in result['relations'] if r['object_id'] == 's2')
        quotes = [e['quote'] for e in relation['evidence']]
        self.assertIn('(i) Công ty con trực tiếp', quotes[0])
        # The row quote stops at the line that completes the name.
        self.assertTrue(quotes[-1].endswith('Viễn thông Alpha (*) cho thuê đường truyền, Phường Cầu Giấy'))

    def test_ctg_layout_interleaved_name_page_carry_and_joint_venture(self):
        triples, diagnostics, result = run(CTG_LIKE)
        self.assertEqual(triples, [
            ('HAS_ASSOCIATE', 'p', 'jv', '50', '2025-12-31'),
            ('HAS_SUBSIDIARY', 'p', 'l1', '100', '2025-12-31'),
            ('HAS_SUBSIDIARY', 'p', 'l2', '100', '2025-12-31'),
        ])
        jv = next(r for r in result['relations'] if r['object_id'] == 'jv')
        self.assertEqual(jv['attributes']['relation_label'], 'công ty liên doanh')
        # The leasing row spans two chunks; each quote is an exact substring of its chunk.
        leasing = next(r for r in result['relations'] if r['object_id'] == 'l1')
        chunks = {c['chunk_id']: c['text'] for c in result['chunks']}
        self.assertTrue(all(e['quote'] in chunks[e['chunk_id']] for e in leasing['evidence']))
        self.assertEqual({e['chunk_id'] for e in leasing['evidence']} >= {'p142:b0', 'p142:b1'}, True)

    def test_cmg_layout_nested_owner_and_ambiguous_combined_heading(self):
        triples, diagnostics, _ = run(CMG_LIKE)
        self.assertEqual(triples, [('HAS_SUBSIDIARY', 'g', 'g1', '100', None)])
        reasons = sorted((d['reason'], d['line'][:20]) for d in diagnostics)
        self.assertEqual(reasons, [
            ('CHILD_UNRESOLVED', 'Công ty TNHH Không B'),
            ('SECTION_KIND_AMBIGUOUS', '4 4 Công ty TNHH Alp'),
            ('SECTION_KIND_AMBIGUOUS', '5 5 Công ty Cổ phần '),
        ])

    def test_issuer_resolved_by_ticker_when_db_name_is_a_short_form(self):
        triples, _, _ = run(FPT_LIKE, issuer_name='Tập đoàn Mẹ Alpha')
        self.assertIn(('HAS_SUBSIDIARY', 'p', 's1', '100', '2025-12-31'), triples)

    def test_negative_cases(self):
        pages = {9: [
            'Lợi nhuận được chia từ các công ty con\n'  # prose ending with the phrase: not a heading
            'Công ty TNHH Phần mềm Alpha Cung cấp phần mềm 100%\n'
            'Công ty con\n'
            '17 tháng 01 năm 2025\n'  # lone wrapped date: not the table date
            '2 Công ty Cổ phần Chứng Giấy phép số 107 Hoạt động 75,64%\n'
            'khoán Ngân hàng UBCK-GP do Ủy ban\n'
            '3 Công ty Cổ phần Cung cấp dịch vụ 30%\n'
            'phân phối linh kiện\n'
            'thiết bị viễn thông\n'
            'Gamma phần mềm',
        ]}
        triples, diagnostics, _ = run(pages)
        self.assertEqual(triples, [])
        # Industry-only "Công ty Cổ phần Chứng khoán" never matches; "Công ty Cổ phần" plus
        # skipped lines plus "Gamma" is not accepted as Công ty Cổ phần Gamma.
        self.assertEqual([d['reason'] for d in diagnostics], ['CHILD_UNRESOLVED', 'CHILD_UNRESOLVED'])

    def test_table_without_date_header_keeps_as_of_empty(self):
        pages = {3: ['(i) Công ty con trực tiếp\nSTT Tên Tỷ lệ\nCông ty TNHH Phần mềm Alpha Cung cấp phần mềm 100%']}
        triples, _, _ = run(pages)
        self.assertEqual(triples, [('HAS_SUBSIDIARY', 'p', 's1', '100', None)])

    def test_pair_already_stated_by_another_rule_gains_evidence_not_a_duplicate(self):
        # "Công ty con" followed by the name is also the older list rule's cue.
        pages = {3: ['Công ty con\nCông ty TNHH Phần mềm Alpha Cung cấp phần mềm 100%']}
        _, _, result = run(pages)
        self.assertEqual([(r['subject_id'], r['object_id']) for r in result['relations']], [('p', 's1')])
        quotes = [e['quote'] for e in result['relations'][0]['evidence']]
        self.assertIn('Công ty TNHH Phần mềm Alpha Cung cấp phần mềm 100%', quotes)


class RegistryRevisionTests(unittest.TestCase):
    def test_r2_is_r1_plus_reviewed_changes(self):
        changes = json.loads((RUNTIME / 'company.registry.20261104.r2.changes.json').read_text('utf-8'))
        base = json.loads((RUNTIME / changes['base']).read_text('utf-8'))
        committed = json.loads((RUNTIME / changes['result']).read_text('utf-8'))
        self.assertEqual(apply_changes(base, changes), committed)
        by_id = {row['entity_id']: row for row in committed}
        self.assertNotIn('VietinBank Leasing', by_id['CMP-c8ff5c1af9a79b27bdfb']['aliases'])
        self.assertIn('Tập đoàn Công nghệ CMC', by_id['CMP-bda9e53cfba37e417ef8']['aliases'])


if __name__ == '__main__':
    unittest.main()
