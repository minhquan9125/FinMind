"""Read-only Golden Set source/vector coverage and deterministic price checks."""
import asyncio
from collections import Counter
from decimal import Decimal
import json
from pathlib import Path
import re
import sys
import unicodedata

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'backend'))
from src.documents.db_source import FINANCIAL_SQL, PRICES_SQL, NEWS_SQL


def norm(value):
    value = unicodedata.normalize('NFD', str(value).lower().replace('đ', 'd'))
    return re.sub(r'[^a-z0-9]+', ' ', ''.join(c for c in value if unicodedata.category(c) != 'Mn')).strip()


async def main():
    import asyncpg
    from src.core.config import get_settings
    conn = await asyncpg.connect(get_settings().database_url, ssl='require', statement_cache_size=0, timeout=25)
    result = {'database_writes': False, 'b1_executed': False}
    try:
        async with conn.transaction(readonly=True, isolation='repeatable_read'):
            result['snapshot'] = str(await conn.fetchval('SELECT transaction_timestamp()'))
            news = [dict(r) for r in await conn.fetch(NEWS_SQL, None, None)]
            prices = [dict(r) for r in await conn.fetch(PRICES_SQL, None)]
            financial = [dict(r) for r in await conn.fetch(FINANCIAL_SQL.replace('o.observation_id, o.value, o.unit',
                      'o.observation_id, o.value, o.unit, o.locator_json'), ['FPT'])]
            vectors = [dict(r) for r in await conn.fetch('''SELECT t.chunk_id::text,t.index_version_id::text,
                t.content_hash,t.locator_json,i.chunker_version FROM public.text_chunks t
                JOIN public.index_versions i USING(index_version_id) WHERE t.superseded_at IS NULL''')]
            for v in vectors:
                if isinstance(v['locator_json'], str):
                    v['locator_json'] = json.loads(v['locator_json'])
            def coverage(table, source_id=None, row_key=None):
                matches = [v for v in vectors if v['locator_json'].get('source_table') == table
                    and (source_id is None or v['locator_json'].get('source_id') == str(source_id))
                    and (row_key is None or str(row_key) in v['locator_json'].get('row_keys', []))]
                return {'active_chunks_by_index': dict(Counter(v['index_version_id'] for v in matches)),
                        'chunk_ids': [v['chunk_id'] for v in matches]}
            result['news_scope'] = {'articles': len(news), 'by_source': dict(Counter(n['source'] for n in news)),
                'published_min': min(str(n['published_at']) for n in news),
                'published_max': max(str(n['published_at']) for n in news),
                'golden_expected': {'articles':224,'cafef':114,'fireant':110}}
            specs = {
                'Q01': ('2026-09-28', 'MBS dự báo KQKD quý 3/2026 ngành bán lẻ'),
                'Q02': ('2026-07-29', 'Một doanh nghiệp quân đội báo lãi quý 2 tăng trưởng mạnh'),
                'Q03': ('2026-09-29', 'mỗi tháng FPT có thêm 6.000 cổ đông mới'),
                'Q04': ('2026-09-29', 'Có gần 182.000 cổ đông khối ngoại còn nắm 28,5% vốn'),
                'Q05': ('2026-09-29', 'Những ngân hàng có thể lãi trên 10.000 tỷ đồng trong quý III'),
                'Q06': ('2026-09-30', 'MB mở rộng vai trò kết nối dòng vốn'),
                'Q07': ('2026-08-13', '21.8.2026 giao dịch 13.723.654 cp niêm yết bổ sung'),
                'Q08': ('2026-10-06', 'Việt Nam chính thức cán mốc 14 triệu tài khoản chứng khoán'),
                'Q09': ('2026-09-15', 'Viettel Construction dự phòng 100% với 3 khoản nợ xấu liên quan FLC Novaland'),
            }
            result['news_questions'] = {}
            for question, (day, title) in specs.items():
                exact = [n for n in news if norm(title) in norm(n['title'])
                         and str(n['published_at'])[:10] == day]
                # Candidate matches never silently become confirmed evidence.
                tokens = set(norm(title).split())
                candidates = sorted(news, key=lambda n: len(tokens & set(norm(n['title']).split()))/max(len(tokens),1), reverse=True)[:3]
                result['news_questions'][question] = {'status': 'SOURCE_FOUND' if exact else 'NEEDS_SOURCE_REVIEW',
                    'expected_date': day, 'expected_title': title,
                    'exact_sources': [{'article_id':str(n['article_id']),'title':n['title'],'date':str(n['published_at']),
                                       **coverage('news_articles', n['article_id'])} for n in exact],
                    'candidate_titles': [{'title':n['title'],'date':str(n['published_at'])} for n in candidates] if not exact else []}
            price_map = {(p['symbol'], str(p['trade_date'])): p for p in prices}
            def price(symbol, day):
                p = price_map.get((symbol,day))
                if p is None:
                    return {'status':'SOURCE_MISSING','symbol':symbol,'date':day}
                return {'symbol':symbol, 'date':day, **{k:p[k] for k in ('open','high','low','close','volume','price_scale')},
                        **coverage('price_bars',symbol,str(p['price_id']))}
            result['price_specific'] = {'Q15':price('VCB','2026-05-20'), 'Q17':price('MSN','2026-07-27'),
                                       'Q19':price('VCB','2026-04-23')}
            def dec(v): return Decimal(str(v))
            def delta(a,b):return {'first':a, 'last':b, 'difference':dec(b)-dec(a), 'percent':(dec(b)/dec(a)-1)*100}
            result['price_calculations'] = {}
            calc = result['price_calculations']
            calc['Q11'] = delta(price_map[('VCB','2026-04-09')]['close'],price_map[('VCB','2026-10-06')]['close'])
            max_volume = max(p['volume'] for p in prices)
            calc['Q12'] = [price(p['symbol'],str(p['trade_date'])) for p in prices if p['volume']==max_volume]
            fpt = [p for p in prices if p['symbol']=='FPT']
            calc['Q13'] = {'highest_close':max(dec(p['close']) for p in fpt),'lowest_close':min(dec(p['close']) for p in fpt),
                          'highest_days':[str(p['trade_date']) for p in fpt if dec(p['close'])==max(dec(q['close']) for q in fpt)],
                          'lowest_days':[str(p['trade_date']) for p in fpt if dec(p['close'])==min(dec(q['close']) for q in fpt)]}
            ctr = [p for p in prices if p['symbol']=='CTR']
            calc['Q14'] = {'bars':len(ctr),'average_volume':sum(dec(p['volume']) for p in ctr)/len(ctr)}
            calc['Q16'] = []
            for symbol in sorted({p['symbol'] for p in prices}):
                series = sorted([p for p in prices if p['symbol']==symbol],key=lambda p:p['trade_date'])
                calc['Q16'].append({'symbol':symbol,'first_date':str(series[0]['trade_date']),
                                   'last_date':str(series[-1]['trade_date']),**delta(series[0]['close'],series[-1]['close'])})
            calc['Q18'] = {'by_symbol':dict(Counter(p['symbol'] for p in prices)),'total':len(prices)}
            calc['Q20'] = delta(price_map[('MBB','2026-09-30')]['close'],price_map[('MBB','2026-10-06')]['close'])
            # Compare the Golden Set's exact cited metric codes as well as nearby real fields.
            metric_specs = {'Q31':['CASH_AND_CASH_EQUIVALENTS'],'Q32':['SHORT_TERM_LOANS_AND_FINANCE_LEASES'],
                'Q33':['RETAINED_EARNINGS'],'Q34':['NET_REVENUE'],
                'Q35':['PARENT_NET_PROFIT','BASIC_EARNINGS_PER_SHARE'],'Q36':['CASH_FLOW_OPERATING'],
                'Q37':['PURCHASE_FIXED_ASSETS'],'Q38':['ROE','GROSS_MARGIN'],'Q39':['NET_REVENUE']}
            result['financial_questions'] = {}
            for question, codes in metric_specs.items():
                periods = {'2026-Q2','2026-Q1'} if question=='Q39' else {'2026-Q2'}
                found = [r for r in financial if r['period_code'] in periods and r['code'] in codes]
                result['financial_questions'][question] = {'golden_codes':codes,'found_codes':sorted({r['code'] for r in found}),
                    'rows':[{'code':r['code'],'name':r['canonical_name'],'period':r['period_code'],
                            'value':r['value'],'unit':r['unit'],'statement_scope':r['statement_scope'],
                            'source_locator':r['locator_json'],
                            **coverage('financial_reports',r['report_id'],r['observation_id'])} for r in found]}
            q2 = [r for r in financial if r['period_code']=='2026-Q2']
            result['financial_actual_candidates'] = [{'code':r['code'],'name':r['canonical_name'],'value':r['value'],
                'source_locator':r['locator_json']} for r in q2 if any(t in r['code'] for t in
                ['CASH','SHORT_TERM','BORROW','EARNING','EPS','PROFIT','REVENUE'])]
            result['fpt_2026_q4_rows'] = sum(r['period_code']=='2026-Q4' for r in financial)
            result['non_db_documents'] = [dict(r) for r in await conn.fetch('''
                SELECT d.document_id::text,d.title,d.doc_type,d.file_type,count(t.chunk_id)::int AS active_chunks
                FROM public.documents d LEFT JOIN public.text_chunks t ON t.document_id=d.document_id AND t.superseded_at IS NULL
                WHERE d.file_type <> 'DB' GROUP BY d.document_id,d.title,d.doc_type,d.file_type''')]
            result['vector_inventory'] = [dict(r) for r in await conn.fetch('''SELECT i.index_version_id::text,
                i.status,i.chunker_version,count(t.chunk_id)::int AS active_chunks
                FROM public.index_versions i LEFT JOIN public.text_chunks t ON t.index_version_id=i.index_version_id
                AND t.superseded_at IS NULL GROUP BY i.index_version_id,i.status,i.chunker_version''')]
            from src.documents.repository import resolve_result_rows
            selected = {cid for q in result['news_questions'].values() for n in q['exact_sources'] for cid in n['chunk_ids']}
            selected.update(cid for q in result['price_specific'].values() for cid in q.get('chunk_ids', []))
            checked = [v for v in vectors if v['chunk_id'] in selected]
            try:
                rebuilt = await resolve_result_rows(conn, checked)
                result['selected_source_reconstruction'] = {'status':'PASS','chunks':len(rebuilt),
                    'scope':'All active chunks of exact matched Q01-Q09 articles and Q15/Q17/Q19 price rows; no semantic ranking/B1 run.'}
            except Exception as exc:
                result['selected_source_reconstruction'] = {'status':'FAILED','type':type(exc).__name__,
                                                            'code':getattr(exc,'code',None),'message':str(exc)}
    finally:
        await conn.close()
    target = ROOT/'backend/.tmp/golden-source-audit-20261021.json'
    target.write_text(json.dumps(result,ensure_ascii=False,indent=2,default=str),encoding='utf-8')
    print(json.dumps(result,ensure_ascii=False,default=str),flush=True)


if __name__ == '__main__':
    asyncio.run(main())
