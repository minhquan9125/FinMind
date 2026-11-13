"""Financial snapshot analysis/report, no database or market/provider calls."""
import argparse
import asyncio
from datetime import date
from pathlib import Path
import sys
from uuid import UUID

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0,str(ROOT))
from backend.src.financial.exact_json import dumps, loads
from backend.src.financial.health import _period, analyze_company
from backend.src.financial.health_store import canonical_rows
from backend.src.financial.peers import compare_peers


def build_report(records, period=None):
    if period is not None:
        _period(period)
    rows = canonical_rows(records)
    analyses = {}
    for symbol in sorted({row['symbol'] for row in rows}):
        dates = {row['period'] for row in rows if row['symbol']==symbol}
        selected = period or max(dates,key=lambda p:(_period(p)[0],_period(p)[1] or 4,'-Q' not in p))
        analyses[symbol] = analyze_company(rows,symbol=symbol,period=selected)
    peers = {symbol:compare_peers(list(analyses.values()),symbol=symbol) for symbol in analyses}
    return dict(analyses=analyses,peers=peers,
        limitations=['Peer subgroup is the available comparable database sample, not the entire industry.',
            'Unknown units, periods, scope or restatement basis prevent unsupported conclusions.',
            'No overall strength score, price prediction, investment recommendation or source approval is generated.'])


DEFAULT_SYMBOLS = ['VCB','BID','CTG','MBB','TCB','FPT','CMG','ELC','ITD','ICT']


async def _records_from_db(dsn, symbols):
    import asyncpg
    from backend.src.core.config import get_settings
    from backend.src.financial.health_db import fetch_health_records
    conn = await asyncpg.connect(dsn or get_settings().database_url,
        server_settings={'default_transaction_read_only':'on'})
    try:
        records = await fetch_health_records(conn,symbols)
        # exact_json.dumps handles only JSON types, so ids and dates become strings for the report
        return [{k:str(v) if isinstance(v,(UUID,date)) else v for k,v in r.items()} for r in records]
    finally:
        await conn.close()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument('--snapshot',type=Path)
    source.add_argument('--from-db',action='store_true')
    parser.add_argument('--symbols',nargs='+',default=DEFAULT_SYMBOLS)
    parser.add_argument('--dsn')
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--period')
    args = parser.parse_args(argv)
    targets = [args.output/name for name in ('report.json','report.md')]
    if args.from_db:
        records = asyncio.run(_records_from_db(args.dsn,args.symbols))
    else:
        snapshot = args.snapshot.resolve(strict=True)
        if any(path.resolve()==snapshot for path in targets):
            raise ValueError('Output must not overwrite the input snapshot')
        records = loads(snapshot.read_text(encoding='utf-8-sig'))
        if not isinstance(records,list):
            raise ValueError('Expected a list of financial observation records')
    report = build_report(records,args.period)
    lines = ['# BCTC: tăng trưởng và vị thế trong nhóm có dữ liệu','',
        '| Mã | Kỳ | Chất lượng | So sánh peer |','|---|---|---|---|']
    for symbol, analysis in report['analyses'].items():
        lines.append(f"| {symbol} | {analysis['period']} | {analysis['status']} | {report['peers'][symbol]['status']} |")
    lines.extend(['','## Chi tiết từng mã',''])
    for symbol, analysis in report['analyses'].items():
        lines.extend([f'### {symbol}', '', '| Chỉ tiêu | Giá trị (%) | Trạng thái | Lý do |', '|---|---:|---|---|'])
        for name, signal in analysis['signals'].items():
            value = signal['value'] if signal['value'] is not None else '—'
            lines.append(f"| {name} | {value} | {signal['status']} | {', '.join(signal['reasons'])} |")
        lines.append('')
    lines.extend(['## Giới hạn','',*['- '+note for note in report['limitations']],
        '', 'Nguồn và observation/payload/hash/locator được giữ trong report.json.'])
    args.output.mkdir(parents=True,exist_ok=True)
    targets[0].write_text(dumps(report),encoding='utf-8')
    targets[1].write_text('\n'.join(lines)+'\n',encoding='utf-8')
    print(f"Financial report: {len(report['analyses'])} companies; output {args.output}")
    return 0


if __name__=='__main__':
    raise SystemExit(main())
