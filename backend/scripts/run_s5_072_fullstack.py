"""S5-WBS07.2 full-stack rerun of a question set through the same chat engine the API builds.

Unlike the isolated 07.2 harness (recording adapters), this uses every adapter the API wires: historical
prices, the hybrid router (Neo4j), admin news, market, the v2 intent router and the real Gemini provider.

Safety: the DB pool is opened with default_transaction_read_only=on, so any write is refused by
PostgreSQL. No chat session is stored and no admin metric is recorded (the engine is called directly).
Live market services (vnstock collectors) are not started. Prior turns are replayed the way
chat_logic.append_turn threads live_context/previous_result.

Run from the repository root with the tunnel open (15433 DB, 17687 Neo4j):
  $env:PYTHONPATH='backend'
  .venv/Scripts/python.exe backend/scripts/run_s5_072_fullstack.py cases.json --output outputs/s5_072_fullstack/run01
cases.json: [{id, group, question, prior, expected: SERVE|ASK|REFUSE|GREETING, ticker, period}, ...]
"""
import argparse
import asyncio
import json
import time
from pathlib import Path

import asyncpg

EXPECTED_STATUS = {'ASK': {'ASK_CLARIFICATION', 'CLARIFICATION_STALLED'}, 'REFUSE': {'UNSUPPORTED'},
                   'GREETING': {'GREETING'}}


async def read_only_pool():
    from src.core import db
    from src.core.config import get_settings
    db._pool = await asyncpg.create_pool(dsn=get_settings().database_url, min_size=1, max_size=4,
                                         statement_cache_size=0, init=db._init_connection,
                                         server_settings={'default_transaction_read_only': 'on'})
    return db._pool


def engine_like_the_api():
    from src.api.routers import research_chat
    research_chat.get_store.cache_clear()
    engine = research_chat.get_store().engine
    if engine is None:
        raise SystemExit('RESEARCH_CHAT_LIVE is off: nothing to run')
    return getattr(engine, 'engine', engine)  # unwrap ObservedResearch: no admin metric is written


def judge(case, result):
    """Routing-boundary check only (as in Huyền's sheet): answer facts and must_preserve need a human."""
    status, scope = result.get('status'), result.get('scope') or {}
    if status == 'SYSTEM_UNAVAILABLE':
        return 'BLOCKED', ['a backend (e.g. Neo4j) was unavailable: not a routing result']
    problems = []
    expected = case['expected']
    if expected == 'SERVE':
        if status in ('ASK_CLARIFICATION', 'CLARIFICATION_STALLED', 'UNSUPPORTED', 'GREETING'):
            problems.append(f'expected an answer, got {status}')
    elif status not in EXPECTED_STATUS[expected]:
        problems.append(f'expected {expected}, got {status}')
    if expected in ('SERVE', 'ASK') and case.get('ticker') and case['ticker'] not in (scope.get('companies') or []):
        problems.append(f"company {case['ticker']} not kept")
    if expected == 'SERVE' and case.get('period'):
        periods = [str(p) for p in scope.get('periods') or []]
        if case['period'] not in periods and not any(case['period'].startswith(p) or p.startswith(case['period']) for p in periods):
            problems.append(f"period {case['period']} not kept (scope {periods})")
    return 'PASS' if not problems else 'FAIL', problems


async def run(cases, output):
    from src.core.usage_tracking import generation_calls
    from src.retrieval_orchestration.live_research import render_live_response
    await read_only_pool()
    engine = engine_like_the_api()
    try:
        await asyncio.wait_for(engine.retriever.warmup(), 300)
    except Exception as exc:  # retrieval retries on demand; record only the type
        print('retriever warmup failed:', type(exc).__name__)
    timeout = engine.retrieval_timeout + engine.limits.read_timeout_seconds + 5
    rows = []
    for case in cases:
        context, previous, turns = {}, None, []
        for index, text in enumerate([case['prior'], case['question']]):
            if not text:
                continue
            calls = []
            token = generation_calls.set(calls)
            started = time.monotonic()
            try:
                result = await asyncio.wait_for(engine.answer(text, f"s5-072-{case['id']}", context,
                                                              previous_result=previous), timeout)
                error = None
            except Exception as exc:
                result, error = {}, type(exc).__name__
            finally:
                generation_calls.reset(token)
            turns.append(dict(question=text, status=result.get('status'), reason_code=result.get('reason_code'),
                              intent=result.get('intent'), scope={k: (result.get('scope') or {}).get(k)
                                                                  for k in ('companies', 'periods', 'source_type', 'metric_code')},
                              gemini_calls=len(calls), seconds=round(time.monotonic() - started, 2), error=error,
                              reply=render_live_response(result)[:1500] if result else None))
            if result.get('scope') is not None:
                context = result['scope']
            if ((result.get('answering') or {}).get('status') == 'DRAFT_READY'
                    or ((result.get('scope') or {}).get('source_type') == 'NEWS'
                        and (result.get('evidence_pack') or {}).get('schema_version') == '1.2')):
                previous = result
        rows.append(dict(case, turns=turns))
    write_report(rows, output)


def write_report(rows, output):
    for r in rows:
        final = r['turns'][-1]
        r['verdict'], r['problems'] = judge(r, dict(status=final['status'], scope=final['scope'])) \
            if not final['error'] else ('BLOCKED', [f"error {final['error']}"])
        print(r['id'], r['verdict'], final['status'], final['intent'], r['problems'])
    output.mkdir(parents=True, exist_ok=True)
    (output / 'results.json').write_text(json.dumps(rows, ensure_ascii=False, indent=1), encoding='utf-8')
    passed = sum(r['verdict'] == 'PASS' for r in rows)
    blocked = sum(r['verdict'] == 'BLOCKED' for r in rows)
    lines = [f'# S5-WBS07.2 full-stack run: {passed}/{len(rows)} PASS, {blocked} BLOCKED at the routing boundary', '',
             '| ID | Expected | Status | Intent | Gemini calls | Verdict | Problems |', '|---|---|---|---|---|---|---|']
    for r in rows:
        t = r['turns'][-1]
        intent = t['intent'] or {}
        lines.append(f"| {r['id']} | {r['expected']} | {t['status']} | {intent.get('label')}/{intent.get('decision')}/"
                     f"{intent.get('source')} {intent.get('reason') or ''} | {t['gemini_calls']} | {r['verdict']} | "
                     f"{'; '.join(r['problems'])} |")
    (output / 'summary.md').write_text('\n'.join(lines) + '\n', encoding='utf-8')
    print(f'{passed}/{len(rows)} PASS, {blocked} BLOCKED -> {output}')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('cases', help='cases.json, or with --rejudge an earlier results.json')
    parser.add_argument('--output', required=True)
    parser.add_argument('--rejudge', action='store_true', help='re-score saved turns; no engine, DB or Gemini call')
    args = parser.parse_args()
    data = json.loads(Path(args.cases).read_text(encoding='utf-8'))
    if args.rejudge:
        write_report(data, Path(args.output))
    else:
        asyncio.run(run(data, Path(args.output)))


if __name__ == '__main__':
    main()
