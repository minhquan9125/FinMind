"""Verify frozen selection and reconstruct additive/later rankings without model loading."""
from collections import Counter
import hashlib
import json
from pathlib import Path
import sys

import numpy as np

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'backend'))
from src.retrieval_orchestration.intent_additive import selection_key


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def main():
    run=ROOT/'outputs/s5_intent_additive_20261112'
    method,selection=read(run/'method.json'),read(run/'selection.json')
    for name,digest in method['input_hashes'].items():
        assert sha(ROOT/name)==digest,name
    assert sha(run/'method.json')==selection['method_sha256']
    assert sha(run/'results.json')==selection['results_sha256']
    assert min(selection['candidates'],key=selection_key)==selection['selected']
    source=ROOT/'outputs/s5_wbs033_20261110/intent-library-v1'
    rows=[json.loads(line) for line in (source/'library.jsonl').read_text(encoding='utf-8').splitlines()]
    vectors=np.load(source/'vectors.npy',allow_pickle=False)
    libraries={'original':(rows,vectors)}
    for name in ['add_all','add_focused']:
        directory=run/name
        metadata=read(directory/'manifest.json')
        for file,digest in metadata['files'].items():
            assert sha(directory/file)==digest
        extra_rows=[json.loads(line) for line in (directory/'library.jsonl').read_text(encoding='utf-8').splitlines()]
        extra_vectors=np.load(directory/'vectors.npy',allow_pickle=False)
        assert extra_rows[:90]==rows and extra_vectors[:90].tobytes()==vectors.tobytes()
        assert extra_vectors.shape==(len(extra_rows),1024)
        assert np.isfinite(extra_vectors).all() and np.allclose(np.linalg.norm(extra_vectors,axis=1),1,atol=1e-4,rtol=0)
        libraries[name]=(extra_rows,extra_vectors)
    selected=selection['selected']['name']
    assert sha(run/selected/'manifest.json')==selection['candidate_manifest_sha256']
    cache=ROOT/'outputs/s5_intent_experiment_20261111/run01'
    texts=read(cache/'embedded-texts.json')
    lookup=dict(zip(texts,np.load(cache/'experiment-vectors.npy',allow_pickle=False)))
    results=read(run/'results.json')
    tasks=[(name,subset,value,lookup) for name,variant in results.items() for subset,value in variant.items() if subset!='regression_transitions']
    later=run/'later-check'
    later_summary=read(later/'summary.json')
    assert sha(run/'selection.json')==later_summary['selection_sha256']
    assert sha(later/'input.jsonl')==selection['later_file_sha256']
    cases=[json.loads(line) for line in (later/'input.jsonl').read_text(encoding='utf-8').splitlines()]
    queries=np.load(later/'query-vectors.npy',allow_pickle=False)
    assert queries.shape==(28,1024) and np.isfinite(queries).all()
    assert np.allclose(np.linalg.norm(queries,axis=1),1,atol=1e-4,rtol=0)
    later_lookup=dict(zip([c['text'] for c in cases],queries))
    later_results=read(later/'results.json')
    tasks += [(name if name=='original' else selected,'later',value,later_lookup) for name,value in later_results.items()]
    maximum=count=0
    route=lambda label:'GRAPH' if label in ['PERSON_ROLE','ENTITY_RELATION'] else ('BOTH' if label=='MIXED' else 'VECTOR')
    for name,subset,value,query_lookup in tasks:
        lib_rows,matrix=libraries[name]
        matrix=matrix.astype(np.float64)
        norms=np.linalg.norm(matrix,axis=1)
        hits=Counter()
        accepted=wrong=0
        for record in value['cases']:
            query=query_lookup[record['ranking']['question']].astype(np.float64)
            scores=np.einsum('ij,j->i',matrix,query)/(norms*np.linalg.norm(query))
            best={}
            for row,score in zip(lib_rows,scores):
                label=row['intent_label']
                best[label]=max(best.get(label,-2),float(score))
            ordered=sorted(best,key=lambda label:(-best[label],label))
            assert ordered==[g['intent_label'] for g in record['ranking']['groups']],record['id']
            for group in record['ranking']['groups']:
                maximum=max(maximum,abs(best[group['intent_label']]-group['score']))
            if record['gold']:
                rank=ordered.index(record['gold'])+1
                assert rank==record['gold_rank']
                for k in [1,3,5]: hits[str(k)]+=rank<=k
                if best[ordered[0]]>=.65 and best[ordered[0]]-best[ordered[1]]>=.08:
                    accepted+=1
                    wrong+=route(ordered[0])!=route(record['gold'])
            count+=1
        assert dict(hits)==value['metrics']['hits']
        assert accepted==value['metrics']['accepted'] and wrong==value['metrics']['accepted_wrong_route']
        assert value['metrics']['fallback']==value['metrics']['labeled']-accepted
    assert maximum<1e-10
    assert results['original']['regression']['metrics']['hits']=={'1':22,'3':41,'5':46}
    proof=dict(status='PASS',rankings_recomputed=count,max_score_difference=maximum,
               original_rows_and_vector_bytes_preserved=True,selection_frozen_before_later_check=True,
               original_source_hashes_unchanged=True,later_questions=28,independent_blind_test=False)
    (run/'audit.json').write_text(json.dumps(proof,indent=2)+'\n',encoding='utf-8',newline='\n')
    print(json.dumps(proof,indent=2))


if __name__=='__main__':
    main()
