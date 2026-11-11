"""Recalculate experimental cosine rankings from saved real vectors; no model needed."""
from collections import Counter
import hashlib
import json
from pathlib import Path
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'backend'))
from src.retrieval_orchestration.intent_experiment import mask_tickers


def main():
    out=ROOT/'outputs/s5_intent_experiment_20261111/run01'
    method=json.loads((out/'method.json').read_text())
    results=json.loads((out/'results.json').read_text(encoding='utf-8'))
    summary=json.loads((out/'summary.json').read_text(encoding='utf-8'))
    for name,checksum in method['input_hashes'].items():
        assert hashlib.sha256((ROOT/name).read_bytes()).hexdigest()==checksum,name
    texts=json.loads((out/'embedded-texts.json').read_text(encoding='utf-8'))
    vectors=np.load(out/'experiment-vectors.npy',allow_pickle=False)
    assert vectors.shape==(len(texts),1024) and np.isfinite(vectors).all()
    assert np.allclose(np.linalg.norm(vectors,axis=1),1,atol=1e-4,rtol=0)
    lookup=dict(zip(texts,vectors.astype(np.float64)))
    source=ROOT/'outputs/s5_wbs033_20261110/intent-library-v1'
    original=[json.loads(s) for s in (source/'library.jsonl').read_text(encoding='utf-8').splitlines()]
    balanced=[json.loads(s) for s in (ROOT/'docs/sprint5/intent-experiment-v2/library-draft.jsonl').read_text(encoding='utf-8').splitlines()]
    old_vectors=np.load(source/'vectors.npy',allow_pickle=False).astype(np.float64)
    count=0
    maximum=0
    for name,variant in results.items():
        masked=name.endswith('_masked')
        transform=mask_tickers if masked else lambda s:s
        rows=original if name.startswith('original') else balanced
        matrix=old_vectors if name=='original' else np.stack([lookup[transform(r['text'])] for r in rows])
        norms=np.linalg.norm(matrix,axis=1)
        for set_name in ['development','regression','known_diagnostic']:
            records=variant[set_name]['cases']
            hits=Counter()
            accepted=wrong=0
            for record in records:
                query=lookup[record['ranking']['question']]
                scores=np.einsum('ij,j->i',matrix,query)/(norms*np.linalg.norm(query))
                best={}
                for row,score in zip(rows,scores):
                    best[row['intent_label']]=max(best.get(row['intent_label'],-2),float(score))
                ordered=sorted(best,key=lambda label:(-best[label],label))
                assert ordered==[g['intent_label'] for g in record['ranking']['groups']]
                for group in record['ranking']['groups']:
                    maximum=max(maximum,abs(group['score']-best[group['intent_label']]))
                assert maximum<1e-10
                if record['gold']:
                    rank=ordered.index(record['gold'])+1
                    assert rank==record['gold_rank']
                    for k in [1,3,5]:
                        hits[str(k)]+=rank<=k
                    gap=best[ordered[0]]-best[ordered[1]]
                    if best[ordered[0]]>=.65 and gap>=.08:
                        accepted+=1
                        route=lambda label: 'GRAPH' if label in ['PERSON_ROLE','ENTITY_RELATION'] else ('BOTH' if label=='MIXED' else 'VECTOR')
                        wrong+=route(ordered[0])!=route(record['gold'])
                count+=1
            assert dict(hits)==summary['metrics'][name][set_name]['hits']
            metrics=summary['metrics'][name][set_name]
            assert accepted==metrics['accepted'] and wrong==metrics['accepted_wrong_route']
            assert metrics['fallback']==metrics['labeled']-accepted
    baseline=summary['metrics']['original']['regression']['hits']
    assert baseline=={'1':22,'3':41,'5':46},baseline
    proof=dict(status='PASS',rankings_recomputed=count,max_score_difference=maximum,
               baseline_counts_reproduced=baseline,source_hashes_unchanged=True,
               later_check_scored=False,model_inference_rerun=False,
               report='Independent raw dot/norm cosine calculation from saved real-model vectors.')
    (out/'audit.json').write_text(json.dumps(proof,indent=2)+'\n',encoding='utf-8',newline='\n')
    print(json.dumps(proof,indent=2))


if __name__=='__main__':
    main()
