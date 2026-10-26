"""Reproducible user-persona conversations against the real chat service.

Default: deterministic interpretation only. --live additionally uses the pinned
read-only corpus and configured Gemini, capped at eight generation calls.
Reports contain public questions/answers and safe status metadata, never secrets.
"""
import argparse
import asyncio
from dataclasses import replace
from datetime import date
import json
from pathlib import Path
import re
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.retrieval_orchestration.live_research import analyze_live, render_live_response


def step(text, decision='SEARCH', **scope):
    return {'text': text, 'decision': decision, 'scope': scope}


CASES = [
    ('pho_thong', 'Hỏi bổ sung từng thông tin', [
        step('lợi nhuận là bao nhiêu', 'ASK_CLARIFICATION'),
        step('fpt', 'ASK_CLARIFICATION', companies=['FPT']),
        step('sau thuế', 'ASK_CLARIFICATION', metric_code='PROFIT_AFTER_TAX'),
        step('quý 4 2025', metric_code='PROFIT_AFTER_TAX', periods=['2025-Q4'])]),
    ('pho_thong', 'Câu đầy đủ nhưng thứ tự từ tự nhiên', [
        step('lợi nhuận của fpt quý 4 sau thuế năm 2025 là bao nhiêu',
             metric_code='PROFIT_AFTER_TAX', periods=['2025-Q4'])]),
    ('pho_thong', 'Nhớ quý khi người dùng bổ sung năm', [
        step('lợi nhuận của fpt quý 4 sau thuế là bao nhiêu', 'ASK_CLARIFICATION'),
        step('2025', metric_code='PROFIT_AFTER_TAX', periods=['2025-Q4'])]),
    ('pho_thong', 'Dùng từ lời thay lợi nhuận', [
        step('FPT lời bao nhiêu năm 2025', 'ASK_CLARIFICATION'),
        step('sau thuế', metric_code='PROFIT_AFTER_TAX', periods=['2025'])]),
    ('pho_thong', 'Gõ không dấu', [
        step('loi nhuan cua fpt quy 4 sau thue nam 2025', metric_code='PROFIT_AFTER_TAX')]),
    ('pho_thong', 'Gõ sai một dấu trong lợi nhuận', [
        step('lợi nhuân fpt năm 2025', 'ASK_CLARIFICATION'),
        step('sau thuế', metric_code='PROFIT_AFTER_TAX', periods=['2025'])]),
    ('pho_thong', 'Đổi mã bằng câu ngắn', [
        step('tiền và tương đương tiền FPT quý 2/2026'),
        step('còn SSI', companies=['SSI'], metric_code='CASH_AND_CASH_EQUIVALENTS')]),
    ('pho_thong', 'Đổi năm bằng câu ngắn', [
        step('tổng tài sản FPT năm 2025'), step('còn năm 2024', periods=['2024'])]),
    ('pho_thong', 'Bắt đầu lại hội thoại', [
        step('tổng tài sản FPT năm 2025'), step('/moi', 'ASK_CLARIFICATION')]),
    ('pho_thong', 'Hỏi nguồn của câu trước', [
        step('tổng tài sản FPT năm 2025'), step('nguồn đâu', 'RESOLVE_REFERENCE')]),
    ('pho_thong', 'Hỏi giá cổ phiếu', [step('giá cổ phiếu FPT hôm nay', 'MARKET_LOOKUP')]),
    ('pho_thong', 'Hỏi nên mua hay không', [step('nên mua FPT không', 'UNSUPPORTED')]),
    ('chuyen_mon', 'Viết tắt LNST', [step('LNST FPT quý 4/2025', metric_code='PROFIT_AFTER_TAX')]),
    ('chuyen_mon', 'Viết tắt LNTT', [step('LNTT FPT quý 4/2025', metric_code='PROFIT_BEFORE_TAX')]),
    ('chuyen_mon', 'LNST cổ đông công ty mẹ phải khác LNST tổng', [
        step('lợi nhuận sau thuế thuộc cổ đông công ty mẹ FPT quý 4/2025',
             metric_code='PARENT_NET_PROFIT', reporting_entity='UNKNOWN')]),
    ('chuyen_mon', 'Lợi nhuận chưa phân phối phải khác LNST', [
        step('lợi nhuận sau thuế chưa phân phối FPT quý 4/2025', metric_code='RETAINED_EARNINGS')]),
    ('chuyen_mon', 'Lũy kế không được lấy riêng quý', [
        step('lợi nhuận sau thuế FPT lũy kế quý 3/2025', measure_basis='YTD')]),
    ('chuyen_mon', 'Riêng quý không được lấy lũy kế', [
        step('lợi nhuận sau thuế FPT quý 4/2025', measure_basis='STANDALONE_QUARTER')]),
    ('chuyen_mon', 'Kỳ canonical vẫn phải hiểu riêng quý', [
        step('PROFIT_AFTER_TAX FPT 2025-Q4', periods=['2025-Q4'], measure_basis='STANDALONE_QUARTER')]),
    ('chuyen_mon', 'Yêu cầu báo cáo hợp nhất', [
        step('tổng tài sản FPT hợp nhất quý 2/2026', reporting_entity='CONSOLIDATED')]),
    ('chuyen_mon', 'Tách câu hỏi có nhiều chỉ tiêu', [
        step('doanh thu thuần và lợi nhuận sau thuế FPT năm 2025', 'ASK_CLARIFICATION')]),
    ('chuyen_mon', 'Hai nhà xuất bản cần làm rõ', [
        step('tin tức FPT từ CafeF và FireAnt tháng 9/2026', 'ASK_CLARIFICATION')]),
    ('chuyen_mon', 'Ngày tin tức chính xác', [
        step('tin tức FPT CafeF ngày 29/9/2026', source_type='NEWS', publisher='cafef', periods=['2026-09-29'])]),
    ('chuyen_mon', 'Kỳ không hợp lệ phải hỏi lại', [
        step('lợi nhuận sau thuế FPT quý 5/2025', 'ASK_CLARIFICATION')]),
]


def evaluate_parser():
    reports = []
    for persona, title, steps in CASES:
        context, turns = {}, []
        for expected in steps:
            result = analyze_live(expected['text'], context, today=date(2026, 10, 23))
            actual = result['scope']
            mismatches = []
            if result['decision'] != expected['decision']:
                mismatches.append(f"decision: cần {expected['decision']}, nhận {result['decision']}")
            for key, value in expected['scope'].items():
                if actual.get(key) != value:
                    mismatches.append(f'{key}: cần {value}, nhận {actual.get(key)}')
            turns.append({'question': expected['text'], 'decision': result['decision'],
                          'reason_code': result['reason_code'], 'response': result['message'],
                          'scope': actual, 'mismatches': mismatches})
            context = actual
        reports.append({'persona': persona, 'title': title, 'passed': not any(t['mismatches'] for t in turns), 'turns': turns})
    return reports


LIVE_CASES = [
    ('pho_thong', 'Bổ sung thông tin và lấy số lợi nhuận', [
        'lợi nhuận là bao nhiêu', 'fpt', 'sau thuế', 'quý 4 2025', 'nguồn đâu'], 'DRAFT_READY'),
    ('pho_thong', 'Câu tự nhiên đủ thông tin', [
        'lợi nhuận của fpt quý 4 sau thuế năm 2025 là bao nhiêu'], 'DRAFT_READY'),
    ('pho_thong', 'Đổi mã giữ câu trước', [
        'tiền và tương đương tiền FPT quý 2/2026', 'còn SSI'], 'ANY_SUPPORTED'),
    ('chuyen_mon', 'Lợi nhuận trước thuế riêng quý', [
        'lợi nhuận trước thuế FPT quý 4/2025'], 'DRAFT_READY'),
    ('chuyen_mon', 'Tin theo nhà xuất bản và ngày', [
        'tin tức FPT theo CafeF ngày 29/9/2026'], 'DRAFT_READY'),
    ('chuyen_mon', 'Kỳ tương lai không có nguồn', [
        'tổng tài sản FPT quý 4/2099'], 'NO_DATA'),
    ('chuyen_mon', 'LNST thuộc cổ đông công ty mẹ', [
        'LNST cổ đông công ty mẹ FPT quý 4/2025'], 'DRAFT_READY'),
    ('pho_thong', 'Bổ sung năm giữ quý trước đó', [
        'lợi nhuận của FPT quý 4 sau thuế là bao nhiêu', '2025'], 'DRAFT_READY'),
    ('chuyen_mon', 'Viết tắt LNTT', ['LNTT FPT quý 4/2025'], 'DRAFT_READY'),
]

LIVE_SCOPES = [
    {'companies': ['FPT'], 'periods': ['2025-Q4'], 'metric_code': 'PROFIT_AFTER_TAX'},
    {'companies': ['FPT'], 'periods': ['2025-Q4'], 'metric_code': 'PROFIT_AFTER_TAX'},
    {'companies': ['SSI'], 'periods': ['2026-Q2'], 'metric_code': 'CASH_AND_CASH_EQUIVALENTS'},
    {'companies': ['FPT'], 'periods': ['2025-Q4'], 'metric_code': 'PROFIT_BEFORE_TAX'},
    {'companies': ['FPT'], 'periods': ['2026-09-29'], 'source_type': 'NEWS'},
    {'companies': ['FPT'], 'periods': ['2099-Q4'], 'metric_code': 'TOTAL_ASSETS'},
    {'companies': ['FPT'], 'periods': ['2025-Q4'], 'metric_code': 'PARENT_NET_PROFIT'},
    {'companies': ['FPT'], 'periods': ['2025-Q4'], 'metric_code': 'PROFIT_AFTER_TAX'},
    {'companies': ['FPT'], 'periods': ['2025-Q4'], 'metric_code': 'PROFIT_BEFORE_TAX'},
]


async def evaluate_live():
    from src.core.config import get_settings
    from src.core.db import connect, disconnect
    from src.documents.embeddings import get_embedding_service
    from src.b1_answering.core.policy import Limits
    from src.b1_answering.providers.gemini import GeminiProvider
    from src.retrieval_orchestration.live_research import DenseEvidenceRetriever, LiveResearchService
    settings = get_settings()
    if not settings.gemini_api_key.get_secret_value() or not settings.b1_gemini_free_tier_confirmed:
        return {'status': 'SKIPPED', 'reason': 'Thiếu Gemini key hoặc xác nhận Free Tier'}
    limits = replace(Limits.load(), max_generation_calls=8)
    provider = GeminiProvider(limits, api_key=settings.gemini_api_key.get_secret_value(), free_tier_confirmed=True)
    print('Đang kết nối cơ sở dữ liệu chỉ đọc...', flush=True)
    pool = await asyncio.wait_for(connect(), timeout=60)
    try:
        retriever = DenseEvidenceRetriever(pool, get_embedding_service(), backend=settings.research_retrieval_backend,
                                           corpus_version_id=settings.research_corpus_version_id, model_ref=settings.embedding_model_ref)
        started = time.monotonic()
        print('Đang warmup model và cache...', flush=True)
        await asyncio.wait_for(retriever.warmup(), timeout=180)
        print('Warmup hoàn tất; bắt đầu các hội thoại với nguồn và Gemini thật.', flush=True)
        service = LiveResearchService(retriever, provider=provider, limits=limits)
        reports = []
        for index, (persona, title, questions, expected) in enumerate(LIVE_CASES):
            context, turns, previous = {}, [], None
            for question in questions:
                before = time.monotonic()
                # One service/budget shared by all conversations; only scope resets.
                before_calls = service.budget.snapshot()['calls_used']
                result = await service.answer(question, f'persona-{index}', context, previous_result=previous)
                context = result['scope']
                answer = result.get('answering') or {}
                response = render_live_response(result)
                turns.append({'question': question, 'status': answer.get('status', result['status']),
                              'reason_code': answer.get('reason_code', result['reason_code']),
                              'response': response, 'scope': context,
                              'seconds': round(time.monotonic()-before, 2),
                              'citations': len(answer.get('citations', [])),
                              'model_returned': answer.get('manifest', {}).get('model_returned'),
                              'prompt_version': answer.get('manifest', {}).get('prompt_version'),
                              'generation_calls_this_turn': service.budget.snapshot()['calls_used']-before_calls,
                              'raw_metric_in_answer': bool(re.search(r'\([A-Z_]{5,}\)', response)),
                              'uuid_in_answer': bool(re.search(r'\[[0-9a-f]{8}-', response))})
                if answer.get('status') == 'DRAFT_READY':
                    previous = result
            final = turns[-1]
            passed = (final['status'] == expected if expected != 'ANY_SUPPORTED'
                      else final['status'] in ('DRAFT_READY', 'NO_DATA'))
            if final['status'] == 'DRAFT_READY':
                passed = passed and final['citations'] > 0 and not final['raw_metric_in_answer'] and not final['uuid_in_answer']
            reports.append({'persona': persona, 'title': title, 'passed': passed, 'turns': turns})
            print(f"{index+1}/{len(LIVE_CASES)}: {title}: {final['status']}", flush=True)
        return {'status': 'COMPLETED', 'elapsed_seconds': round(time.monotonic()-started, 2),
                'budget': service.budget.snapshot(), 'conversations': reports}
    finally:
        await disconnect()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--live', action='store_true')
    parser.add_argument('--render-only', action='store_true', help='Chỉ dựng lại báo cáo đã lưu, không gọi dịch vụ')
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1] / 'src/retrieval_orchestration/evaluations'
    root.mkdir(parents=True, exist_ok=True)
    path = root / 'user_personas_results.json'
    if args.render_only:
        report = json.loads(path.read_text(encoding='utf-8'))
    else:
        report = {'evaluation_date': '2026-10-23', 'parser_conversations': evaluate_parser()}
        if args.live:
            try:
                report['live'] = asyncio.run(evaluate_live())
            except Exception as exc:
                # Keep parser results even if external dependencies fail; no raw DSN/key.
                report['live'] = {'status': 'ERROR', 'reason': type(exc).__name__}
    for row, expected_scope in zip(report.get('live', {}).get('conversations', []), LIVE_SCOPES):
        final = row['turns'][-1]
        final['mismatches'] = [f"{key}: cần {value}, nhận {final['scope'].get(key)}"
                               for key, value in expected_scope.items() if final['scope'].get(key) != value]
        row['passed'] = row['passed'] and not final['mismatches']
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    lines = ['# Mô phỏng người dùng phổ thông và có chuyên môn', '',
             'Phần parser kiểm tra hội thoại xác định; phần LIVE (nếu chạy) dùng corpus thật và Gemini thật. '
             'Kiểm tra qua service backend hiện có, chưa mô phỏng thao tác trình duyệt/auth.', '']
    parser_rows = report['parser_conversations']
    live_rows = report.get('live', {}).get('conversations', [])
    lines += ['## Kết quả và giới hạn', '',
              f"- Hiểu câu hỏi: {sum(row['passed'] for row in parser_rows)}/{len(parser_rows)} hội thoại đạt kỳ vọng.",
              f"- Luồng LIVE: {sum(row['passed'] for row in live_rows)}/{len(live_rows)} hội thoại đạt; trạng thái {report.get('live', {}).get('status', 'NOT_RUN')}.",
              '- Đây là các kịch bản mẫu, không phải xác nhận mọi câu tiếng Việt đều được hỗ trợ.',
              '- Ca hỏi nguồn kiểm tra tham chiếu đã lưu; ca SSI cho phép NO_DATA khi vẫn giữ đúng mã/kỳ/chỉ tiêu.',
              '- Transcript LIVE giữ nguyên lúc chạy; tên nguồn được làm gọn thêm sau lượt đo và đã kiểm tra bằng regression lưu phiên.', '']
    if report.get('live', {}).get('budget'):
        budget = report['live']['budget']
        lines += [f"- Gemini: {budget['calls_used']} generation; {budget['tokens_reserved']} token đã dùng hoặc giữ dự phòng; {budget['unknown_usage']} lượt chưa xác định usage chính xác.", '']
    lines += ['## Những lỗi đã kiểm tra lại', '',
              '1. Phân biệt LNST thuộc cổ đông công ty mẹ với LNST tổng và phạm vi báo cáo riêng.',
              '2. Giữ quý khi quý/năm nằm xa nhau hoặc bổ sung năm; kỳ canonical có basis.',
              '3. Hiểu lời, LNST, LNTT; không coi viết tắt chỉ tiêu là ticker.',
              '4. Hỏi nguồn dùng câu trả lời đã lưu, không tìm kiếm/gọi Gemini lại.',
              '5. Tin tức giới hạn số claim và quote trong output2048, không tăng trần token.',
              '', 'Bản trước sửa: `USER_PERSONAS_REPORT_BEFORE_FIXES.md` và `user_personas_results_before_fixes.json`.', '']
    for title, rows in [('Hiểu câu hỏi', report['parser_conversations']),
                        ('Nguồn và trả lời thật', report.get('live', {}).get('conversations', []))]:
        if not rows: continue
        passed = sum(row['passed'] for row in rows)
        lines += [f'## {title}: {passed}/{len(rows)} hội thoại đạt', '']
        for row in rows:
            lines += [f"### {'ĐẠT' if row['passed'] else 'CHƯA ĐẠT'} — {row['title']} ({row['persona']})", '']
            for turn in row['turns']:
                lines += [f"- Người dùng: {turn['question']}", f"- Hệ thống: {turn['response']}"]
                lines += [f'- Lệch kỳ vọng: {text}' for text in turn.get('mismatches', [])]
            lines.append('')
    (root / 'USER_PERSONAS_REPORT.md').write_text('\n'.join(lines), encoding='utf-8')
    print(f'Đã ghi báo cáo: {root}', flush=True)


if __name__ == '__main__':
    main()
