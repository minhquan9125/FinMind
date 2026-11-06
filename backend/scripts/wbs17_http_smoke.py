"""Read-only HTTP probes on the running local app; no login or session writes."""
import argparse
import json
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request,urlopen
from backend.scripts.wbs17_workbook import load_workbook_suite


def request(url,body=None,invalid_token=False):
    headers={'Content-Type':'application/json'}
    if invalid_token:headers['Authorization']='Bearer wbs17-intentionally-invalid-test-token'
    req=Request(url,data=json.dumps(body).encode() if body is not None else None,headers=headers)
    try:
        with urlopen(req,timeout=180) as r:
            raw=r.read();status=r.status
    except HTTPError as e:raw=e.read();status=e.code
    try:payload=json.loads(raw)
    except (ValueError,UnicodeDecodeError):payload={'non_json_bytes':len(raw)}
    return {'url':url,'status':status,'payload':payload,
            'credential_variant':'invalid_synthetic_token' if invalid_token else 'anonymous'}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--workbook',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();a.output.mkdir(parents=True,exist_ok=False)
    suite=load_workbook_suite(a.workbook)
    c=next(c for c in suite['cases'] if c['case_id']=='TC_EDGE_24')
    results=[]
    def keep(r):
        results.append(r)
        with (a.output/'results.jsonl').open('a',encoding='utf-8') as f:f.write(json.dumps(r,ensure_ascii=False)+'\n')
        print(json.dumps({k:v for k,v in r.items() if k!='payload'}),flush=True)
    for url in ['http://127.0.0.1:8000/api/health','http://127.0.0.1:5173/',
                'http://127.0.0.1:5173/api/health']:
        keep(request(url))
    for invalid in [False,True]:
        r=request('http://127.0.0.1:8000/api/research/chat/sessions',invalid_token=invalid)
        r['check']='chat_auth_rejects';r['pass']=r['status'] in [401,403];keep(r)
    for invalid in [False,True]:
        r=request('http://127.0.0.1:8000/api/hybrid-router/run',{'question':c['question'],'context':{}},invalid)
        r.update(case_id='TC_EDGE_24',check='router_auth_rejects_before_retrieval',
                 passed=r['status'] in [401,403],question=c['question'])
        keep(r)
    checks=[r for r in results if r.get('case_id')=='TC_EDGE_24']
    summary={'case_id':'TC_EDGE_24','level':'RUNNING_LOCAL_APP_API_ONLY','ui_e2e':'NOT_RUN',
      'workbook_sha256':suite['workbook_sha256'],'variants':len(checks),
      'backend_verdict':'PASS_BACKEND' if all(r['passed'] for r in checks) else 'FAIL_BACKEND',
      'http_statuses':[r['status'] for r in checks],
      'limitation':'No valid low-privilege account tested; no claim about reverse proxy/deployed environment; browser host unavailable.'}
    (a.output/'summary.json').write_text(json.dumps(summary,indent=2),'utf-8')
    print(json.dumps(summary),flush=True)


if __name__=='__main__':main()
