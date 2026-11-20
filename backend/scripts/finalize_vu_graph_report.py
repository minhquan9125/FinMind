"""Validate captured traces and annotate the handoff workbook; no network."""
import json
import sys
from pathlib import Path
from collections import Counter
from openpyxl import load_workbook
from openpyxl.styles import Font, PatternFill, Alignment

root = Path(__file__).resolve().parents[2]
out = root / 'outputs/vu_graph_retest_20261118' / (sys.argv[1] if len(sys.argv) > 1 else 'final-run')
rows = json.loads((out / 'results.json').read_text(encoding='utf-8'))
by_id = {r['id']: r for r in rows}
assert len(rows) == 6
empty, error = by_id['G06'], by_id['G03']
assert empty['status'] == 'NO_DATA' and empty['reason_code'] == 'GRAPH_NO_VERIFIED_RELATIONS'
assert any(e.get('completed') and e.get('relation_count') == 0 for e in empty['graph_retrieval_events'])
assert error['reason_code'] == 'GRAPH_CHAT_UNAVAILABLE'
assert any(e.get('error_type') == 'ServiceUnavailable' for e in error['neo4j_reader_calls'])
assert all(r['http_status'] == 200 and r['trace']['graph_calls'] == 1 for r in rows)
for ident in ('G01', 'G04'):
    assert by_id[ident]['trace']['graph_source_stale'] == 'GRAPH_SOURCE_NOT_IN_ACTIVE_CORPUS'
    assert by_id[ident]['reason_code'] == 'GRAPH_CHAT_TIMEOUT'
assert any(e.get('completed') and e.get('relation_count') == 0 for e in by_id['G02']['graph_retrieval_events'])
by_id['G05'].update(verdict='REVIEW', expected='EXPLORATORY_RELATIONSHIP_SCOPE',
    review_note='Không có oracle chứng minh graph rỗng; quan sát planner EVENT_IMPACT/BCTC cho câu hỏi đối tác theo tin tức.')
(out / 'results.json').write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding='utf-8')
file = out / 'VU_GRAPH_WEB_CHAT_RETEST_20261118.xlsx'
wb = load_workbook(file)
cases = wb['Web Chat']
for cells in cases.iter_rows(min_row=2):
    r = by_id[cells[0].value]
    cells[2].value, cells[3].value = r['expected'], r['verdict']
summary = wb['Tong quan']
summary.append(['Kết quả Web Chat', '2 PASS, 3 FAIL, 1 REVIEW. Chưa đạt toàn bộ nghiệm thu.'])
summary.append(['Các lượt chạy', 'G01–G05: web-run02; G06: final-run. Không cộng lại các lượt trùng.'])
summary.append(['Điều kiện graph thật', 'ĐẠT: reader thật hoàn tất truy vấn và trace graph_calls=1.'])
summary.append(['Điều kiện rỗng / lỗi', 'ĐẠT ở G06/G03; G02 bị fallback timeout nên chưa đạt tổng thể.'])
summary.append(['Điều kiện có dữ liệu', 'CHƯA ĐẠT: FPT/TCB có cạnh, nguồn chưa khớp corpus, fallback timeout.'])
summary.append(['Báo cáo chi tiết', 'docs/graph/user-retest-20261118/WEB_CHAT_RETEST.md'])
sheet = wb['Van de'] if 'Van de' in wb.sheetnames else wb.create_sheet('Van de')
for row in [
    ['ID', 'Bằng chứng', 'Ảnh hưởng', 'Việc cần làm / giới hạn'],
    ['I01', 'G01/G04: GRAPH_SOURCE_NOT_IN_ACTIVE_CORPUS', 'Chưa trả lời có nguồn hợp lệ', 'Đối chiếu corpus, chunk, hash, source graph; giữ nguyên kiểm tra nguồn.'],
    ['I02', 'G01/G02/G04: vector_calls=1 rồi GRAPH_CHAT_TIMEOUT', 'Ca rỗng hoặc nguồn stale hiện thành lỗi timeout', 'Kiểm tra fallback báo cáo và thời gian tải embedding; tách khỏi kết luận Neo4j lỗi.'],
    ['I03', 'Regression: incoming OTHER → FPT, HAS_SUBSIDIARY', 'Có thể trả nhầm công ty mẹ thành công ty con', 'Sửa kiểm tra chiều quan hệ; tái hiện bằng fixture độc lập, chưa khẳng định dữ liệu thật có cạnh đó.'],
    ['I04', 'Regression: incoming OTHER → FPT, HAS_ASSOCIATE', 'Có thể trả sai chiều liên kết', 'Sửa theo ngữ nghĩa từng loại quan hệ, chạy lại hai ca lỗi.'],
    ['I05', 'G05 EVENT_IMPACT/BCTC; G06 MULTI_HOP/BCTC', 'Phạm vi nguồn/topic cần rà soát với câu hỏi tin tức', 'REVIEW: G06 PASS chỉ ở ranh giới rỗng/lỗi; không xác nhận toàn bộ planner đúng.'],
    ['I06', 'intent_classifier_unavailable; dotenv parse warnings 32,36,43,45', 'Giới hạn môi trường kiểm thử', 'Đã kết nối DB được; không sửa hoặc đưa giá trị .env vào báo cáo.'],
]: sheet.append(row)
for tab in wb:
    tab.freeze_panes = 'A2'
    tab.auto_filter.ref = tab.dimensions
    for cell in tab[1]:
        cell.font = Font(bold=True, color='FFFFFF')
        cell.fill = PatternFill('solid', fgColor='24557A')
    for column in tab.columns:
        tab.column_dimensions[column[0].column_letter].width = min(75, max(16, max(len(str(c.value or '')) for c in column)+2))
        for cell in column: cell.alignment = Alignment(vertical='top', wrap_text=True)
wb.save(file)
check = load_workbook(file, read_only=True)
assert check['Web Chat'].max_row == 7 and check['Regression'].max_row == 46
assert check['Graph retrieval'].max_row == 7
check.close()
print(json.dumps({'counts': dict(Counter(r['verdict'] for r in rows)), 'workbook': str(file), 'verified': True}, ensure_ascii=True))
