"""One later-check after candidate selection; never chooses or tunes a candidate."""
import hashlib
import json
from pathlib import Path
import sys

import numpy as np

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'backend'))
from src.documents.embeddings import get_embedding_service
from src.retrieval_orchestration.intent_library import IntentLibrary,load_library
from src.retrieval_orchestration.intent_matching import IntentMatcher
from src.retrieval_orchestration.intent_experiment import transitions
from run_s5_intent_experiment import measure,write

RUN=ROOT/'outputs/s5_intent_additive_20261112'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    output=RUN/'later-check'
    if output.exists():
        raise FileExistsError('LATER_CHECK_ALREADY_ATTEMPTED: '+str(output))
    selection_path=RUN/'selection.json'
    selection_hash=sha(selection_path)
    selection=json.loads(selection_path.read_text())
    if (sha(RUN/'method.json')!=selection['method_sha256']
            or sha(RUN/'results.json')!=selection['results_sha256']):
        raise ValueError('UNFROZEN_SELECTION')
    for name,digest in json.loads((RUN/'method.json').read_text())['input_hashes'].items():
        if sha(ROOT/name)!=digest:
            raise ValueError('SELECTION_SOURCE_CHANGED: '+name)
    selected_dir=RUN/selection['selected']['name']
    manifest_path=selected_dir/'manifest.json'
    if sha(manifest_path)!=selection['candidate_manifest_sha256']:
        raise ValueError('CANDIDATE_CHANGED')
    metadata=json.loads(manifest_path.read_text())
    for name,digest in metadata['files'].items():
        if sha(selected_dir/name)!=digest:
            raise ValueError('CANDIDATE_PAYLOAD_CHANGED')
    original_dir=ROOT/'outputs/s5_wbs033_20261110/intent-library-v1'
    if sha(original_dir/'manifest.json')!=selection['original_manifest_sha256']:
        raise ValueError('ORIGINAL_CHANGED')
    original=load_library(original_dir)
    rows=tuple(json.loads(line) for line in (selected_dir/'library.jsonl').read_text(encoding='utf-8').splitlines())
    values=np.load(selected_dir/'vectors.npy',allow_pickle=False)
    if (values.shape!=(len(rows),1024) or not np.isfinite(values).all()
            or not np.allclose(np.linalg.norm(values,axis=1),1,atol=1e-4,rtol=0)
            or rows[:len(original.rows)]!=original.rows
            or values[:len(original.rows)].tobytes()!=original.vectors.tobytes()):
        raise ValueError('INVALID_ADDITIVE_CANDIDATE')
    candidate=IntentLibrary(rows,values,metadata)
    # The selection and complete candidate have been checked before first read of later-check.
    later_path=ROOT/'docs/sprint5/intent-experiment-v2/later-check-UNSCORED.jsonl'
    raw=later_path.read_bytes()
    if hashlib.sha256(raw).hexdigest()!=selection['later_file_sha256']:
        raise ValueError('LATER_INPUT_CHANGED')
    cases=[json.loads(line) for line in raw.decode('utf-8').splitlines()]
    if len(cases)!=28 or {r['text'].casefold() for r in rows}&{r['text'].casefold() for r in cases}:
        raise ValueError('LATER_COUNT_OR_TRAIN_OVERLAP')
    output.mkdir()
    (output/'input.jsonl').write_bytes(raw)
    write(output/'attempt.json',dict(status='STARTED_NOT_YET_COMPLETED',selection_sha256=selection_hash,
          selected=selection['selected'],script_sha256=sha(Path(__file__)),
          later_sha256=selection['later_file_sha256'],model=original.manifest['model'],
          threshold=.65,gap=.08,payload_groups=3,independent_blind_test=False))
    encoder=get_embedding_service()
    matchers={name:IntentMatcher(library,encoder) for name,library in [('original',original),('selected',candidate)]}
    print('Encoding 28 later-check questions once; candidate selection is frozen.',flush=True)
    queries=np.asarray(encoder.embed_texts([r['text'] for r in cases]),dtype=np.float32)
    if queries.shape!=(28,1024) or not np.isfinite(queries).all():
        raise ValueError('INVALID_QUERY_VECTORS')
    np.save(output/'query-vectors.npy',queries,allow_pickle=False)
    results={name:measure(cases,[matcher._rank(case['text'],vector,7,5) for case,vector in zip(cases,queries)])
             for name,matcher in matchers.items()}
    if (sha(selection_path)!=selection_hash or sha(manifest_path)!=selection['candidate_manifest_sha256']
            or sha(later_path)!=selection['later_file_sha256']):
        raise ValueError('FROZEN_INPUT_CHANGED_DURING_CHECK')
    for name,digest in metadata['files'].items():
        if sha(selected_dir/name)!=digest:
            raise ValueError('CANDIDATE_PAYLOAD_CHANGED')
    load_library(original_dir)
    write(output/'results.json',results)
    summary=dict(status='COMPLETED_ONE_LATER_CHECK_NOT_PRODUCTION_APPROVAL',selected=selection['selected'],
                 independent_blind_test=False,selection_sha256=selection_hash,
                 metrics={name:r['metrics'] for name,r in results.items()},
                 transitions=transitions(results['original']['cases'],results['selected']['cases']),
                 official_library_unchanged=True,threshold_unchanged=True)
    write(output/'summary.json',summary)
    print(json.dumps(summary,ensure_ascii=False,indent=2))


if __name__=='__main__':
    main()
