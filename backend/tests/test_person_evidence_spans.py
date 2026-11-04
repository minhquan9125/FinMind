from src.person_role.evidence_spans import person_spans
from src.graph_review.positions import position_supported


def test_quote_excludes_other_person_and_preserves_original_offsets():
    text='HĐQT\nÔng Nguyễn Văn An — Thành viên HĐQT\nÔng Trần Văn Bình không còn giữ chức vụ.\n'
    spans=person_spans(text,'Nguyễn Văn An',['Nguyễn Văn An','Trần Văn Bình'])
    assert len(spans)==1
    assert 'không còn' not in spans[0]['quote']
    assert text[spans[0]['start']:spans[0]['end']]==spans[0]['quote']


def test_target_negation_is_never_removed():
    text='Ông Nguyễn Văn An không còn là Giám đốc.\n'
    assert 'không còn' in person_spans(text,'Nguyễn Văn An',['Nguyễn Văn An'])[0]['quote']


def test_different_name_diacritic_does_not_match():
    assert not person_spans('Ông Trần Văn Tần — Chủ tịch','Trần Văn Tân',['Trần Văn Tân'])


def test_role_alias_does_not_promote_deputy_or_infer_board_scope():
    assert position_supported('Phó Tổng Giám đốc','Ông An — Phó TGĐ')
    assert not position_supported('Tổng Giám đốc','Ông An — Phó TGĐ')
    assert not position_supported('Thành viên HĐQT','Ông An — Thành viên')
