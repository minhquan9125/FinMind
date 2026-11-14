"""Build a lossless repair ledger for all 185 accepted source assertions."""
import json
from collections import Counter
from person_role_db import ROOT
from src.person_role.source_claim_repairs import repair_claim

OUT=ROOT/'outputs/person-all-185-20261104'

def main():
    audit=json.loads((OUT/'live-source-audit.json').read_text('utf-8'))
    names=list({r['object'] if r['relation_type'] in ('APPOINTS','DISMISSES') else r['subject'] for r in audit['records']})
    repaired=[repair_claim(r,names) for r in audit['records']]
    if len(repaired)!=185 or len({r['origin_extraction_id'] for r in repaired})!=185:raise ValueError('Every original record must be retained')
    sources={c['chunk_id']:c for r in audit['records'] for c in r['live_verified_chunks']}
    for row in repaired:
        for ref in row['evidence']:
            if sources[ref['chunk_id']]['text'][ref['quote_start']:ref['quote_end']]!=ref['quote']:raise ValueError('Quote changed')
    summary=dict(total=185,excluded=0,status_counts=dict(Counter(r['repair_status'] for r in repaired)),
        evidence_basis_counts=dict(Counter(r.get('evidence_basis','UNRESOLVED') for r in repaired)),
        database_writes=0,neo4j_writes=0)
    (OUT/'repairs.json').write_text(json.dumps(dict(summary=summary,records=repaired),ensure_ascii=False,indent=2),'utf-8')
    print(json.dumps(summary,ensure_ascii=False))

if __name__=='__main__':main()
