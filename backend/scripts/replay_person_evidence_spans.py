"""Offline diagnostic only; captured evidence is never a live approval receipt."""
import asyncio,copy,json
from collections import Counter
from pathlib import Path
from src.graph_review.engine import IdentityRegistry,ReviewEngine
from src.graph_review.models import VerifiedSource,digest
from src.person_role.evidence_spans import person_spans

ROOT=Path(__file__).resolve().parents[2]
BASE=ROOT/'outputs/person-neo4j-publish-20261103/intake'

async def main():
    candidates=json.loads((BASE/'candidates.json').read_text('utf-8'))
    registry=IdentityRegistry(json.loads((BASE/'registry-used.json').read_text('utf-8')))
    sources={}
    for raw in candidates:
        for ev in raw['evidence']:
            source=VerifiedSource(**{k:v for k,v in ev.items() if k!='quote'},text=ev['quote'],verification_mode='FIXTURE')
            old=sources.setdefault(source.chunk_id,source)
            if old.text!=source.text:raise ValueError('Captured chunk conflict')
    names=[raw['object' if raw['relation_type'] in ('APPOINTS','DISMISSES') else 'subject']['canonical_name'] for raw in candidates]
    class Reader:
        async def resolve(self,evidence):return sources[evidence.chunk_id]
    revised=[]
    for raw in candidates:
        value=copy.deepcopy(raw);value['evidence']=[]
        name=raw['object' if raw['relation_type'] in ('APPOINTS','DISMISSES') else 'subject']['canonical_name']
        for ev in raw['evidence']:
            for span in person_spans(ev['quote'],name,names):
                assert ev['quote'][span['start']:span['end']]==span['quote']
                value['evidence'].append(dict(ev,quote=span['quote']))
            header=ev['quote'].splitlines()[0]
            if 'Snapshot ' in header:value['evidence'].append(dict(ev,quote=header))
        value['candidate_id']='offline-v2:'+digest(value)
        revised.append(value)
    results=await ReviewEngine(Reader(),registry).evaluate_batch(revised)
    old=json.loads((BASE/'evaluations.json').read_text('utf-8'))
    changes=[dict(origin_extraction_id=r['extractor_metadata']['origin_extraction_id'],before=a['status'],after=b.status,
                  before_reasons=a['reasons'],after_reasons=b.reasons) for r,a,b in zip(revised,old,results)]
    summary=dict(mode='OFFLINE_FIXTURE_NOT_LIVE_VERIFIED_NO_DB_WRITES',counts=dict(Counter(r.status for r in results)),
                 recovered_from_rejection=sum(c['before']=='REJECTED' and c['after']=='PENDING' for c in changes),
                 regressions=sum(c['before']!='REJECTED' and c['after']=='REJECTED' for c in changes),changes=changes)
    out=BASE.parent/'intake-v2';out.mkdir(exist_ok=True)
    (out/'offline-span-diagnostic.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),'utf-8')
    print(json.dumps({k:v for k,v in summary.items() if k!='changes'}))

if __name__=='__main__':asyncio.run(main())
