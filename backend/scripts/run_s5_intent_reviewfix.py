"""Frozen V4 regression + review probes; no refit, router calls or thresholding."""
import argparse
import hashlib
import json
from pathlib import Path
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'backend'))
from src.retrieval_orchestration.intent_request_review import requests, resolve_objectives
from src.retrieval_orchestration.intent_scoring import classifier_probabilities, rankings
from run_s5_intent_consensus import stats

PARENT = ROOT / 'outputs/s5_intent_composition_20261112'
SCORER = ROOT / 'outputs/s5_intent_scorer_20261112'
PROBES = [
    ('NUMERIC', 'Doanh thu mảng AI và dịch vụ cloud của FPT năm 2025 là bao nhiêu?'),
    ('NUMERIC', 'Cho biết doanh thu cloud và AI của FPT năm 2025 là bao nhiêu?'),
    ('NUMERIC', 'Doanh thu AI và cloud của doanh nghiệp ABC là bao nhiêu?'),
    ('PERSON_ROLE', 'Chủ tịch HĐQT của FPT là ai?'),
    ('PERSON_ROLE', 'Chu tich HDQT cua ABC la ai?'),
    ('PERSON_ROLE', 'Ông Nguyễn Văn A giữ chức gì tại FPT?'),
    ('PERSON_ROLE', 'CEO của FPT là ai?'),
    ('PERSON_ROLE', 'Ai là CEO của ABC?'),
    ('PERSON_ROLE', 'Who is the CEO of ABC?'),
    ('NEWS', 'Tìm bài tin về việc bổ nhiệm CEO FPT.'),
    ('REPORT_CONTENT', 'Trích nguyên văn hàng chức vụ CEO trong BCTN.'),
    ('NUMERIC', 'Lương CEO của FPT năm 2025 là bao nhiêu?'),
    ('REPORT_CONTENT', 'BCTN mô tả chiến lược phát triển AI và cloud ra sao?'),
    ('MIXED', 'Doanh thu mảng AI của FPT năm 2025 là bao nhiêu và tìm bài tin FPT ký hợp đồng cloud.'),
    ('MIXED', 'AI giữ chức Chủ tịch? BCTN mô tả chính sách nhân sự ra sao?'),
]


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8', newline='\n')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def saved_vectors():
    sources = [
        (ROOT / 'outputs/s5_intent_experiment_20261111/run01/embedded-texts.json',
         ROOT / 'outputs/s5_intent_experiment_20261111/run01/experiment-vectors.npy'),
        (PARENT / 'new-texts.json', PARENT / 'new-vectors.npy'),
        (PARENT / 'new-check/texts.json', PARENT / 'new-check/vectors.npy'),
        (PARENT / 'final-check-v3-utf8/texts.json', PARENT / 'final-check-v3-utf8/vectors.npy'),
    ]
    lookup = {}
    for text_path, vector_path in sources:
        lookup.update(zip(read(text_path), np.load(vector_path, allow_pickle=False)))
    for text_path, vector_path in [('evaluation-cases.json', 'evaluation-vectors.npy')]:
        lookup.update(zip([r['text'] for r in read(SCORER / text_path)],
                          np.load(SCORER / vector_path, allow_pickle=False)))
    training = [json.loads(line) for line in (SCORER / 'training.jsonl').read_text(encoding='utf-8').splitlines()]
    lookup.update(zip([r['text'] for r in training], np.load(SCORER / 'training-vectors.npy', allow_pickle=False)))
    return lookup, sources


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--cache-from', type=Path, help='Reuse prior review text vectors, never decisions/labels')
    args = parser.parse_args()
    out = args.out
    if out.exists():
        raise FileExistsError('Keep earlier attempts; choose a new output directory')
    old = read(PARENT / 'objectives-v3/results.json')
    old['previous_final_check'] = read(PARENT / 'final-check-v3-utf8/results.json')
    cases = [dict(row, evaluation_set=group) for group, rows in old.items() for row in rows]
    probes = [dict(id=f'REVIEW-{i:02}', question=q, gold=label, evaluation_set='review_probes')
              for i, (label, q) in enumerate(PROBES, 1)]
    cases += probes
    spans = [requests(row['question']) for row in cases]
    lookup, caches = saved_vectors()
    if args.cache_from:
        cached = args.cache_from.resolve()
        pair = (cached / 'new-texts.json', cached / 'new-vectors.npy')
        lookup.update(zip(read(pair[0]), np.load(pair[1], allow_pickle=False)))
        caches.append(pair)
    needed = sorted(({row['question'] for row in cases} | {q for group in spans for q in group}) - lookup.keys())
    fit = ROOT / read(SCORER / 'fit-location.json')['output']
    metadata = read(SCORER / 'method.json')
    labels = read(fit / 'summary.json')['labels']
    parameters = np.load(fit / 'parameters.npz', allow_pickle=False)
    watched = [Path(__file__), ROOT / 'backend/src/retrieval_orchestration/intent_request_review.py',
               ROOT / 'backend/src/retrieval_orchestration/intent_composition.py',
               ROOT / 'backend/src/retrieval_orchestration/intent_request_objectives.py',
               ROOT / 'backend/src/retrieval_orchestration/intent_request_consensus.py',
               ROOT / 'docs/sprint5/intent-labels.v1.json', ROOT / 'docs/sprint5/S5-WBS04.1-reviewfix-plan.md',
               fit / 'parameters.npz', PARENT / 'objectives-v3/results.json',
               PARENT / 'final-check-v3-utf8/results.json']
    watched += [p for pair in caches for p in pair]
    watched += [SCORER / name for name in ['evaluation-cases.json', 'evaluation-vectors.npy', 'training.jsonl', 'training-vectors.npy']]
    hashes = {p.relative_to(ROOT).as_posix(): sha(p) for p in watched}
    out.mkdir(parents=True)
    write(out / 'method.json', dict(status='FROZEN_BEFORE_EVALUATION', source_hashes=hashes,
          model=metadata['model'], parameters_unchanged=True, no_fit=True, regression_rows=278,
          review_probes_are_known_failure_driven=True, blind_test=False, runtime_enabled=False, confidence=None))
    write(out / 'cases.json', cases)
    write(out / 'parts.json', spans)
    write(out / 'new-texts.json', needed)
    if needed:
        from src.documents.embeddings import get_embedding_service
        encoder = get_embedding_service()
        assert (encoder.model_name, encoder.revision) == (metadata['model']['name'], metadata['model']['revision'])
        print(f'Embedding {len(needed)} new texts; preserving classifier and gold.', flush=True)
        values = np.asarray(encoder.embed_texts(needed), dtype=np.float32)
        assert values.shape == (len(needed), 1024) and np.isfinite(values).all()
        np.save(out / 'new-vectors.npy', values, allow_pickle=False)
        lookup.update(zip(needed, values))
    results = {}
    changes = {}
    for case, texts in zip(cases, spans):
        question, group = case['question'], case['evaluation_set']
        base_ranking = case.get('base_ranking')
        if base_ranking:
            base = np.asarray([next(g['score'] for g in base_ranking['groups'] if g['intent_label'] == label)
                               for label in labels])
        else:
            base = classifier_probabilities(np.stack([lookup[question]]), parameters['coefficients'], parameters['intercepts'])[0]
            base_ranking = rankings([question], [base], labels, 'intent-linear-v1',
                'CLASSIFIER_PROBABILITY_UNCALIBRATED', metadata['model'])[0]
        component = classifier_probabilities(np.stack([lookup[q] for q in texts]), parameters['coefficients'], parameters['intercepts']) if texts != [question] else []
        resolution = resolve_objectives(base, component, labels, texts)
        row = dict(id=case['id'], question=question, gold=case['gold'], parts=texts,
                   resolution=resolution, final_label=resolution['intent_label'],
                   base_ranking=base_ranking, component_probabilities=np.asarray(component).tolist(),
                   prior_v3_label=case.get('final_label'))
        results.setdefault(group, []).append(row)
        if group != 'review_probes':
            transition = changes.setdefault(group, dict(fixed=[], regressed=[]))
            if case['gold']:
                before, after = case['final_label'] == case['gold'], row['final_label'] == case['gold']
                if not before and after: transition['fixed'].append(case['id'])
                if before and not after: transition['regressed'].append(case['id'])
    for name, digest in hashes.items():
        assert sha(ROOT / name) == digest, 'Source changed: ' + name
    summary = dict(status='COMPLETED_OFFLINE_REVIEW_FIX', metrics={g: stats(rows, labels) for g, rows in results.items()},
                   changes_against_v3=changes, passes_no_regression_gate=not any(v['regressed'] for v in changes.values()),
                   confidence=None, calibrated=False, router_integrated=False)
    write(out / 'results.json', results)
    write(out / 'summary.json', summary)
    print(json.dumps(dict(correct={g: v['correct'] for g, v in summary['metrics'].items()},
                         changes=changes, passes_gate=summary['passes_no_regression_gate']), indent=2))


if __name__ == '__main__':
    main()
