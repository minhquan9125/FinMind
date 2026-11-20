"""JSON/JSONL crawler output -> rule candidates and quarantine, with no AI/DB."""
import argparse,json,sys
from pathlib import Path
from collections import Counter
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from src.person_role.rules_pipeline import extract_record,VERSION

def load(path):
    if path.suffix.lower()=='.jsonl':
        for no,line in enumerate(path.read_text('utf-8-sig').splitlines(),1):
            if line.strip():yield no,json.loads(line)
    else:
        value=json.loads(path.read_text('utf-8-sig'))
        if isinstance(value,list):records=value
        elif isinstance(value,dict) and isinstance(value.get('pages'),list):
            meta={k:v for k,v in value.items() if k!='pages'};records=[dict(meta,**p) for p in value['pages']]
        elif isinstance(value,dict) and isinstance(value.get('records'),list):records=value['records']
        else:records=[value]
        yield from enumerate(records,1)

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--input',required=True,help='JSON/JSONL file, or directory containing pages.jsonl')
    p.add_argument('--output-dir',required=True,help='New directory; existing output is never overwritten')
    p.add_argument('--symbol',help='Issuer symbol; not sufficient to attribute arbitrary news sentences')
    p.add_argument('--source-kind',choices=['annual_report','news','corporate_disclosure'],required=True)
    p.add_argument('--source-url');p.add_argument('--reporting-year',type=int)
    p.add_argument('--as-of',help='Explicit YYYY-MM-DD for future-effective classification')
    a=p.parse_args();src=Path(a.input);out=Path(a.output_dir)
    if out.exists():p.error('Output directory exists; choose another directory')
    paths=sorted(src.rglob('pages.jsonl')) if src.is_dir() else [src]
    if not paths:raise ValueError('No pages.jsonl found')
    candidates={};rejected=[];records=0;unmatched=[]
    for path in paths:
        sidecar=path.parent/'source.json'
        metadata=json.loads(sidecar.read_text('utf-8-sig')) if sidecar.exists() else {}
        for no,record in load(path):
            if not isinstance(record,dict):raise ValueError(f'Expected object: {path}:{no}')
            record=dict(record)
            if not a.symbol and metadata.get('symbol'):record.setdefault('symbol',metadata['symbol'])
            if metadata.get('year'):record.setdefault('reporting_year',metadata['year'])
            if metadata.get('source_url'):record.setdefault('source_url',metadata['source_url'])
            if a.reporting_year is not None:record.setdefault('reporting_year',a.reporting_year)
            if a.as_of:record.setdefault('as_of',a.as_of)
            # News title often contains the explicit appointment announcement.
            if 'title' in record and 'content' in record and not any(k in record for k in ('text','text_clean')):
                record['text']=str(record['title'])+'\n'+str(record['content'])
            result=extract_record(record,symbol=a.symbol,source_kind=a.source_kind,source_url=a.source_url)
            records+=1
            for row in result['candidates']:candidates[row['candidate_id']]=row
            rejected.extend(dict(input_file=str(path),input_record=no,**r) for r in result['quarantine'])
            if not result['candidates'] and not result['quarantine']:
                unmatched.append(dict(input_file=str(path),input_record=no,page=record.get('page',record.get('page_number'))))
    out.mkdir(parents=True)
    for name,rows in [('candidates.jsonl',list(candidates.values())),('quarantine.jsonl',rejected),('unmatched_records.jsonl',unmatched)]:
        (out/name).write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in rows),'utf-8')
    summary=dict(pipeline_version=VERSION,input_records=records,candidates=len(candidates),quarantined_units=len(rejected),
        records_without_supported_matches=len(unmatched),quarantine_reasons=dict(Counter(r['reason'] for r in rejected)),
        ai_calls=0,database_writes=0,network_calls=0,review_status='PENDING_NOT_HUMAN_VERIFIED')
    (out/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),'utf-8');print(json.dumps(summary,ensure_ascii=False))
if __name__=='__main__':main()
