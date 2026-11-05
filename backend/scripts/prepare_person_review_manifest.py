"""Parse the supplied human-review report; never grant application approval.

This is an audit manifest, not a publishable contract or a canonical-ID registry.
"""
import argparse,hashlib,json,re,uuid
from pathlib import Path

HEADER=re.compile(r'^### (APPROVED|REJECTED) — (\d+)\. ([0-9a-f-]{36})\s*$',re.M)

def parse_report(text):
    headers=list(HEADER.finditer(text));records=[]
    for i,header in enumerate(headers):
        body=text[header.end():headers[i+1].start() if i+1<len(headers) else len(text)]
        # The trailing report conclusion is outside the final reviewed record.
        body=body.split('\n## Kiểm chứng và việc cần sửa',1)[0].strip()
        quote='\n'.join(line[2:] for line in body.splitlines() if line.startswith('> '))
        fact=re.search(r'\*\*Bản kiểm:\*\* (.+?) → (.+?) · `([A-Z_]+)` · (.+)',body)
        if not fact or not quote:raise ValueError('Reviewed record missing fact/quote: '+header[3])
        source=re.search(r'\*\*Nguồn:\*\* (https?://\S+) · document_id `([^`]+)` · trang PDF `([^`]+)`',body)
        digest=re.search(r'\*\*Hash section/trang đã kiểm:\*\* `([0-9a-f]{64})`',body)
        if not source or not digest:raise ValueError('Reviewed record missing source binding: '+header[3])
        page=None if source[3]=='None' else int(source[3])
        if page is not None and page<1:raise ValueError('Invalid PDF page')
        uuid.UUID(header[3]);uuid.UUID(source[2])
        records.append(dict(extraction_id=header[3],ordinal=int(header[2]),report_decision=header[1],
            subject=fact[1],object=fact[2],relation_type=fact[3],position=fact[4].strip().rstrip('.'),
            quote=quote,document_id=source[2],pdf_page=page,source_url=source[1],
            source_view_sha256=digest[1],review_body_sha256=hashlib.sha256(body.encode()).hexdigest()))
    ids=[record['extraction_id'] for record in records]
    if not records or len(set(ids))!=len(ids):raise ValueError('Missing or duplicate review IDs')
    if [record['ordinal'] for record in records]!=list(range(1,len(records)+1)):
        raise ValueError('Review ordinals are not contiguous')
    return dict(schema_version='source-review-manifest-1.0',publication_status='NOT_PUBLISHABLE_WITHOUT_SOURCE_IDENTITY_TEMPORAL_AND_REVIEW_VALIDATION',
        records=records,counts={decision:sum(r['report_decision']==decision for r in records) for decision in ('APPROVED','REJECTED')})

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--input',type=Path,required=True);parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();data=args.input.read_bytes();result=parse_report(data.decode('utf-8-sig'))
    result['report_sha256']=hashlib.sha256(data).hexdigest()
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(result,ensure_ascii=False,indent=2),'utf-8')
    print(json.dumps(dict(counts=result['counts'],database_writes=0,publication_status=result['publication_status'])))
