from src.b1_answering.evidence.grounded import locate_quote
from src.retrieval_orchestration.web_chat_router import graph_relations_extract

TABLE = 'STT Họ và tên Chức vụ\n1 Ông Jens Lottner\nThành viên Ban điều hành Tổng Giám đốc kiêm Giám đốc Khối Quản trị Nguồn nhân lực'


def test_a_quote_joining_table_cells_is_located_and_bound_to_source_words():
    quote = 'Ông Jens Lottner Tổng Giám đốc kiêm Giám đốc Khối Quản trị Nguồn nhân lực'
    span, pieces = locate_quote(TABLE, quote, column_ocr=True)
    assert span in TABLE and span.startswith('Ông Jens Lottner') and span.endswith('nhân lực')
    assert pieces == ['Ông Jens Lottner', 'Tổng Giám đốc kiêm Giám đốc Khối Quản trị Nguồn nhân lực']


def test_scattered_matching_stays_narrow():
    quote = 'Ông Jens Lottner Tổng Giám đốc kiêm Giám đốc Khối Quản trị Nguồn nhân lực'
    assert locate_quote(TABLE, quote) is None                                        # only for scanned reports
    deputy = 'Ông A\nPhó Tổng Giám đốc phụ trách khối vận hành ngân hàng'
    assert locate_quote(deputy, 'Ông A Tổng Giám đốc phụ trách khối', column_ocr=True) is None   # "Phó" skipped
    negated = 'Ông A\nkhông giữ chức Tổng Giám đốc của ngân hàng'
    assert locate_quote(negated, 'Ông A giữ chức Tổng Giám đốc', column_ocr=True) is None        # "không" skipped
    far = 'Ông A ' + ' '.join(['x'] * 12) + ' Tổng Giám đốc của ngân hàng'
    assert locate_quote(far, 'Ông A Tổng Giám đốc', column_ocr=True) is None                     # too far apart
    assert locate_quote(TABLE, 'Ông Jens Lottner Chủ tịch Hội đồng', column_ocr=True) is None    # word not in source


def _pack(passage):
    return {'items': [dict(evidence_id='e1', source_id='s', chunk_id='c', source_sha256='a' * 64,
                           locator={}, passage=passage, title='BCTN TCB', source_type='BCTN')]}


def test_role_question_falls_back_to_the_approved_person_and_title():
    facts = [dict(relation_type='HOLDS_ROLE', subject='Jens Lottner', object='TCB', position='Tổng Giám đốc',
                  evidence_ids=['e1']),
             dict(relation_type='HOLDS_ROLE', subject='Người Không Có', object='TCB', position='Tổng Giám đốc',
                  evidence_ids=['e1'])]
    out = graph_relations_extract(facts, _pack(TABLE), ['HOLDS_ROLE'])
    assert out['reason_code'] == 'GRAPH_RELATIONS_EXTRACT'
    assert 'Jens Lottner (Tổng Giám đốc) [1]' in out['draft']
    assert 'Người Không Có' not in out['draft']
    assert graph_relations_extract(facts[1:], _pack(TABLE), ['HOLDS_ROLE']) is None
