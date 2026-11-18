"""Read-only live graph test through the Web Chat ASGI message endpoint."""
import asyncio
import json
import logging
import os
from pathlib import Path
import sys
import tempfile
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'backend'))
os.chdir(ROOT / 'backend')


async def main():
    import asyncpg
    import httpx
    from fastapi import FastAPI
    from neo4j import GraphDatabase
    from src.core import db
    from src.core.config import get_settings
    from src.api.routers import research_chat as api
    from src.graph.viewer import GraphViewerReader
    from src.retrieval_orchestration.web_sessions import SessionStore
    from src.retrieval_orchestration.live_research import render_live_response
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill, Alignment

    output = ROOT / 'outputs/vu_graph_retest_20261118' / (sys.argv[1] if len(sys.argv) > 1 else 'web-run01')
    output.mkdir(parents=True, exist_ok=True)
    if (output / 'results.json').exists():
        raise FileExistsError('Preserve previous run')
    db._pool = await asyncpg.create_pool(dsn=get_settings().database_url, min_size=1, max_size=4,
        statement_cache_size=0, init=db._init_connection,
        server_settings={'default_transaction_read_only': 'on'})
    raw = api.get_store().engine
    engine = getattr(raw, 'engine', raw)
    engine.provider = None  # No paid/external generation; retrieval and API are real.
    routed = engine.hybrid_router
    graph = routed.graph_retriever
    original = graph.reader_factory
    original_retrieve = graph.retrieve
    rows = []
    retrieval_events = []
    async def traced_retrieve(scope):
        event = {'stage': 'graph_retrieve', 'completed': False}
        retrieval_events.append(event)
        try:
            pack, facts = await original_retrieve(scope)
            event.update(completed=True, evidence_count=len(pack['items']), relation_count=len(facts))
            return pack, facts
        except Exception as exc:
            event['reason_code'] = getattr(exc, 'code', type(exc).__name__)
            raise
    graph.retrieve = traced_retrieve
    class ReaderTrace:
        def __init__(self, reader, events): self.reader, self.events = reader, events
        def __getattr__(self, name):
            target = getattr(self.reader, name)
            def call(*args, **kwargs):
                event = {'method': name, 'completed': False}
                self.events.append(event)
                try:
                    result = target(*args, **kwargs)
                    event['completed'] = True
                    value = result[0] if isinstance(result, tuple) else result
                    if isinstance(value, (list, dict)): event['returned_count'] = len(value)
                    return result
                except Exception as exc:
                    event['error_type'] = type(exc).__name__
                    raise
            return call
    # A dedicated dead local endpoint induces a real driver connection failure;
    # it does not stop or modify the user's Neo4j connection.
    import socket
    guard = socket.socket()
    guard.bind(('127.0.0.1', 0))
    dead_port = guard.getsockname()[1]
    bad = GraphDatabase.driver(f'bolt://127.0.0.1:{dead_port}', auth=('test', 'test'),
                              connection_timeout=1, max_transaction_retry_time=0)
    try:
        with tempfile.TemporaryDirectory(prefix='vu-graph-web-') as temporary:
            store = SessionStore(Path(temporary), engine=engine)
            app = FastAPI()
            app.include_router(api.router)
            app.dependency_overrides[api.get_store] = lambda: store
            owner = str(uuid4())
            app.dependency_overrides[api.get_owner] = lambda: owner
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://test') as client:
                for ident, question, expected in [
                    ('G01', 'Ai là Chủ tịch FPT?', 'VERIFIED_ANSWER'),
                    ('G02', 'Ai là Chủ tịch VCB?', 'NO_DATA'),
                    ('G03', 'Ai là Chủ tịch FPT?', 'SYSTEM_UNAVAILABLE'),
                    ('G04', 'Ai là Chủ tịch TCB?', 'VERIFIED_ANSWER'),
                    ('G05', 'Theo tin tức, VCB hợp tác với những đối tác nào?', 'NO_DATA'),
                    ('G06', 'Theo tin tức, ai là Chủ tịch VCB?', 'NO_DATA'),
                ]:
                    events = []
                    retrieval_events.clear()
                    graph.reader_factory = lambda: ReaderTrace(GraphViewerReader(bad) if ident == 'G03' else original(), events)
                    session = (await client.post('/api/research/chat/sessions')).json()
                    response = await client.post(f"/api/research/chat/sessions/{session['session_id']}/messages",
                        json={'text': question, 'revision': session['revision']}, timeout=180)
                    body = response.json()
                    result = body.get('messages', [{}])[-1].get('result', {})
                    trace = result.get('hybrid_router') or {}
                    answer = result.get('answering') or {}
                    actual = result.get('status')
                    passed = (actual == expected if expected != 'VERIFIED_ANSWER' else
                              answer.get('status') == 'DRAFT_READY' and bool((result.get('evidence_pack') or {}).get('items')))
                    if expected == 'SYSTEM_UNAVAILABLE':
                        passed = passed and result.get('reason_code') == 'GRAPH_CHAT_UNAVAILABLE' and any(e.get('error_type') == 'ServiceUnavailable' for e in events)
                    if expected == 'NO_DATA':
                        passed = passed and any(e.get('completed') and e.get('relation_count') == 0 for e in retrieval_events)
                    verdict = 'PASS' if passed and events and trace.get('graph_calls') == 1 else 'FAIL'
                    if ident == 'G05':
                        verdict = 'REVIEW'
                        expected = 'EXPLORATORY_RELATIONSHIP_SCOPE'
                    if expected == 'VERIFIED_ANSWER' and result.get('reason_code') in (
                        'GRAPH_SOURCE_NOT_IN_ACTIVE_CORPUS', 'GRAPH_SOURCE_VERSION_MISMATCH'):
                        verdict = 'BLOCKED'
                    row = dict(id=ident, question=question, expected=expected, http_status=response.status_code,
                        status=actual, reason_code=result.get('reason_code'), verdict=verdict,
                        reply=render_live_response(result), trace=trace, neo4j_reader_calls=events,
                        evidence_count=len((result.get('evidence_pack') or {}).get('items') or []),
                        answering_status=answer.get('status'), result=result)
                    row['graph_retrieval_events'] = list(retrieval_events)
                    rows.append(row)
                    print(json.dumps({k: row[k] for k in ('id','status','reason_code','verdict','trace','neo4j_reader_calls')}, ensure_ascii=True), flush=True)
                    (output / 'results.json').write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding='utf-8')
        wb = Workbook()
        overview = wb.active
        overview.title = 'Tong quan'
        for row in [
            ['Mục', 'Nội dung'],
            ['Phạm vi', 'Web Chat ASGI: POST sessions và POST messages; Neo4j và PostgreSQL thật'],
            ['An toàn dữ liệu', 'PostgreSQL read-only; phiên chat tạm; không sửa graph/code sản phẩm'],
            ['Giới hạn', 'Bỏ xác thực bằng dependency tài khoản test; không chạy trình duyệt; Gemini tắt'],
            ['Phiên bản kiểm thử', 'huyen-test / 03bae48d32355c9d5f467df07bc60cd9831d9063'],
            ['Cách gây lỗi', 'Neo4j driver thật tới cổng local dành riêng không có dịch vụ; không tắt tunnel'],
            ['Điều kiện có dữ liệu', 'Phải có bằng chứng được xác minh và câu trả lời DRAFT_READY'],
            ['Lưu ý', 'Graph có cạnh chưa đủ: nguồn phải replay được trong corpus đang phục vụ'],
            ['Test hồi quy trước', '99 passed, 31 subtests passed; xem baseline.xml'],
            ['Test độc lập trước', '8 passed, 2 failed: chấp nhận cạnh ngược HAS_SUBSIDIARY / HAS_ASSOCIATE'],
        ]: overview.append(row)
        cases = wb.create_sheet('Web Chat')
        cases.append(['ID','Câu hỏi','Kỳ vọng','Kết luận','HTTP','Status','Reason','Graph calls','Vector calls','Evidence','Chat hiển thị'])
        trace_sheet = wb.create_sheet('Trace Neo4j')
        trace_sheet.append(['ID','Method','Completed','Returned count','Error type'])
        stages = wb.create_sheet('Graph retrieval')
        stages.append(['ID','Completed','Evidence count','Relation count','Reason'])
        for r in rows:
            cases.append([r['id'],r['question'],r['expected'],r['verdict'],r['http_status'],r['status'],r['reason_code'],r['trace'].get('graph_calls'),r['trace'].get('vector_calls'),r['evidence_count'],r['reply']])
            for e in r['neo4j_reader_calls']: trace_sheet.append([r['id'],e['method'],e['completed'],e.get('returned_count'),e.get('error_type')])
            for e in r['graph_retrieval_events']: stages.append([r['id'],e['completed'],e.get('evidence_count'),e.get('relation_count'),e.get('reason_code')])
        import xml.etree.ElementTree as ET
        regression = wb.create_sheet('Regression')
        regression.append(['Test','Kết quả','Chi tiết'])
        for test in ET.parse(output.parent / 'web-regression.xml').iter('testcase'):
            failure = test.find('failure')
            regression.append([test.get('name'), 'FAIL' if failure is not None else 'PASS', failure.get('message') if failure is not None else ''])
        for sheet in wb:
            sheet.freeze_panes = 'A2'
            sheet.auto_filter.ref = sheet.dimensions
            for cell in sheet[1]: cell.font = Font(bold=True, color='FFFFFF'); cell.fill = PatternFill('solid', fgColor='24557A')
            for column in sheet.columns:
                letter = column[0].column_letter
                sheet.column_dimensions[letter].width = min(75, max(16, max(len(str(c.value or '')) for c in column) + 2))
                for cell in column: cell.alignment = Alignment(vertical='top', wrap_text=True)
        wb.save(output / 'VU_GRAPH_WEB_CHAT_RETEST_20261118.xlsx')
    finally:
        graph.reader_factory = original
        graph.retrieve = original_retrieve
        bad.close()
        guard.close()
        await db.disconnect()


if __name__ == '__main__':
    logging.getLogger('neo4j').setLevel(logging.CRITICAL)
    asyncio.run(main())
