"""Independent decision reconstruction for development v2 and the new check."""
import hashlib
import json
from pathlib import Path

import numpy as np

ROOT=Path(__file__).resolve().parents[2]
PARENT=ROOT/'outputs/s5_intent_composition_20261112'


def read(path): return json.loads(path.read_text(encoding='utf-8'))


def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()


def expected_label(base,parts,labels):
    whole=sorted(range(len(labels)),key=lambda i:(-base[i],labels[i]))
    if not parts: return labels[whole[0]]
    top=[sorted(range(len(labels)),key=lambda i:(-p[i],labels[i]))[0] for p in parts]
    if len(top)==1: return labels[top[0]]
    if labels[whole[0]]=='MIXED': return 'MIXED'
    pairs=[(a,b) for a in top for b in top if a!=b and labels[a]!='MIXED' and labels[b]!='MIXED']
    return 'MIXED' if any({a,b}==set(whole[:2]) for a,b in pairs) else labels[whole[0]]


def main():
    run=PARENT/'consensus-v2'
    for name,digest in read(run/'method.json')['source_hashes'].items(): assert sha(ROOT/name)==digest,name
    head=read(PARENT/'results.json')
    labels=sorted(head['linear']['development']['metrics']['per_label'])
    raw=np.asarray(read(PARENT/'raw-probabilities.json'))
    cases,traces=read(PARENT/'cases.json'),read(PARENT/'traces.json')
    decisions=read(run/'results.json')
    summary=read(run/'summary.json')
    count=0
    for dataset,rows in decisions.items():
        original={r['id']:r for r in head['linear'][dataset]['cases']}
        indices=[i for i,r in enumerate(cases) if r['evaluation_set']==dataset]
        hits=0
        for i,row in zip(indices,rows):
            expected=expected_label(raw[i],traces[i]['component_probabilities'],labels)
            assert expected==row['final_label']==row['resolution']['intent_label']
            assert row['resolution']['confidence'] is None
            assert row['base_ranking']==original[row['id']]['ranking']
            hits+=bool(row['gold'] and row['gold']==expected)
            count+=1
        assert hits==summary['metrics'][dataset]['correct']
    new=PARENT/'new-check'
    new_method=read(new/'method.json')
    for name,digest in new_method['source_hashes'].items(): assert sha(ROOT/name)==digest,name
    scorer=ROOT/'outputs/s5_intent_scorer_20261112'
    fit=ROOT/read(scorer/'fit-location.json')['output']
    params=np.load(fit/'parameters.npz',allow_pickle=False)
    texts=read(new/'texts.json')
    vectors=np.load(new/'vectors.npy',allow_pickle=False)
    assert vectors.shape==(len(texts),1024) and np.isfinite(vectors).all()
    assert np.allclose(np.linalg.norm(vectors,axis=1),1,atol=1e-4,rtol=0)
    lookup=dict(zip(texts,vectors.astype(np.float64)))
    def prob(text):
        logits=np.einsum('ij,j->i',params['coefficients'],lookup[text])+params['intercepts']
        out=np.exp(logits-logits.max()); return out/out.sum()
    old=ROOT/'outputs/s5_wbs033_20261110/intent-library-v1'
    old_rows=[json.loads(line) for line in (old/'library.jsonl').read_text(encoding='utf-8').splitlines()]
    old_vectors=np.load(old/'vectors.npy',allow_pickle=False).astype(np.float64)
    correct={'original':0,'linear':0,'consensus':0}
    maximum=0
    for row in read(new/'results.json'):
        base=prob(row['question'])
        component=[] if row['parts']==[row['question']] else [prob(q) for q in row['parts']]
        expected=expected_label(base,[p.tolist() for p in component],labels)
        assert expected==row['final_label'] and row['resolution']['confidence'] is None
        q=lookup[row['question']]
        cosines=np.einsum('ij,j->i',old_vectors,q)/(np.linalg.norm(old_vectors,axis=1)*np.linalg.norm(q))
        best={label:max(cosines[j] for j,r in enumerate(old_rows) if r['intent_label']==label) for label in labels}
        ordered=sorted(labels,key=lambda label:(-best[label],label))
        assert ordered==[g['intent_label'] for g in row['original_ranking']['groups']]
        for g in row['base_ranking']['groups']:
            maximum=max(maximum,abs(base[labels.index(g['intent_label'])]-g['score']))
        correct['original']+=ordered[0]==row['gold']
        correct['linear']+=labels[int(base.argmax())]==row['gold']
        correct['consensus']+=expected==row['gold']
        count+=1
    assert maximum<1e-10
    new_summary=read(new/'summary.json')
    assert correct=={name:m['correct'] for name,m in new_summary['metrics'].items()}
    proof=dict(status='PASS',decisions_recomputed=count,raw_classifier_rankings_preserved=True,
        new_check_correct=correct,max_probability_difference=maximum,
        confidence_not_fabricated=True,legacy_threshold_not_applied=True,
        frozen_sources_unchanged=True,no_training=True)
    (run/'audit.json').write_text(json.dumps(proof,indent=2)+'\n',encoding='utf-8',newline='\n')
    print(json.dumps(proof,indent=2))


if __name__=='__main__': main()
