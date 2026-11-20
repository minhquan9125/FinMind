"""Reproduce v2 fixes without refitting; optionally encode fixed review probes."""
import argparse
import importlib.util
import json
from pathlib import Path
import re
import sys
from types import ModuleType

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'backend'))
from src.retrieval_orchestration.intent_v2_classifier import IntentClassifier
from src.retrieval_orchestration.intent_v2_dataset import read_rows
from src.retrieval_orchestration.intent_matching import summarize_evaluation
from build_s5_intent_v2 import CACHE, OUT, sha, write
from evaluate_s5_intent_v2 import FrozenEncoder, summarize_resolution
from prepare_s5_intent_v2 import unaccented

FIX = CACHE.parent / 'fix1'


def _baseline():
    frozen = json.loads((FIX / 'before.json').read_text())
    for name, digest in frozen['immutable_inputs'].items():
        if sha(ROOT / name) != digest:
            raise ValueError('MODEL_OR_DATA_CHANGED: ' + name)
    for name, digest in frozen['source_hashes'].items():
        if sha(FIX / 'before-sources' / name) != digest:
            raise ValueError('BASELINE_SOURCE_CHANGED: ' + name)
    package = 'src.retrieval_orchestration'
    path = FIX / 'before-sources/backend/src/retrieval_orchestration/intent_v2_rules.py'
    spec = importlib.util.spec_from_file_location(package + '._rules_before_r2', path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    path = path.with_name('intent_v2_classifier.py')
    source = path.read_text(encoding='utf-8')
    original_import = 'from .intent_v2_rules import '
    if source.count(original_import) != 1:
        raise ValueError('UNEXPECTED_BASELINE_IMPORT')
    # Import substitution exists only in RAM; persisted baseline bytes stay intact.
    source = source.replace(original_import, 'from ._rules_before_r2 import ')
    module = ModuleType(package + '._classifier_before_r2')
    module.__package__, module.__file__ = package, str(path)
    exec(compile(source, str(path), 'exec'), module.__dict__)
    return module.IntentClassifier


def _valid(row, result):
    expected = row['component_intents'] if row['intent_label'] == 'MIXED' else []
    restricted = row['intent_label'] == 'OUT_OF_SCOPE' or 'OUT_OF_SCOPE' in expected
    return (result['intent_label'] == row['intent_label']
        and set(result['component_labels']) == set(expected)
        and len(result['component_labels']) == len(expected)
        and result['contains_restricted_component'] == restricted
        and (row.get('expected_status') is None or row['expected_status'] == result['status'])
        and result['status'] in {'PROPOSED', 'NEEDS_CONTEXT'})


def audit(output):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    before_class = _baseline()
    sources = [Path(__file__), ROOT / 'backend/scripts/evaluate_s5_intent_v2.py']
    sources += [ROOT / 'backend/src/retrieval_orchestration' / n for n in
                ['intent_v2_rules.py', 'intent_v2_classifier.py', 'intent_library.py',
                 'intent_matching.py', 'intent_scoring.py']]
    hashes = {p.relative_to(ROOT).as_posix(): sha(p) for p in sources}
    model = json.loads((OUT / 'library/manifest.json').read_text())['model']
    sets = [('library', CACHE / 'library.jsonl', CACHE / 'library-vectors.npy'),
            ('development', CACHE / 'development.jsonl', CACHE / 'development-vectors.npy'),
            ('regression', FIX.parent / 'legacy-regression/cases.json',
             FIX.parent / 'legacy-regression/query-vectors.npy')]
    data_hashes = {p.relative_to(ROOT).as_posix(): sha(p) for _, a, b in sets for p in [a, b]}
    write(output / 'method.json', dict(status='FROZEN_BEFORE_AUDIT', source_hashes=hashes,
        data_hashes=data_hashes, baseline_sha256=sha(FIX / 'before.json'),
        artifact_manifest_sha256=sha(OUT / 'manifest.json'), no_fit=True,
        blind_acceptance=False, no_runtime_latency_measurement=True,
        status_annotation='CONVERSATION/greeting subtype is standalone PROPOSED; other rows unchanged.',
        metamorphic_method='CONTROLLED_ENCODER_REUSES_ORIGINAL_VECTOR; RULE_CHECK_ONLY'))
    for path in sources:
        target = output / 'source-snapshot' / path.relative_to(ROOT)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(path.read_bytes())
    metrics, changes, failures, meta_failures = {}, [], [], []
    meta_count = 0
    for name, rows_path, vectors_path in sets:
        rows = (json.loads(rows_path.read_text(encoding='utf-8')) if rows_path.suffix == '.json'
                else read_rows(rows_path))
        rows = [dict(r, expected_status='PROPOSED')
                if r['intent_label'] == 'CONVERSATION' and r.get('subtype') == 'greeting'
                else r for r in rows]
        values = np.load(vectors_path, allow_pickle=False)
        encoder = FrozenEncoder(rows, values, model)
        before, after = before_class.load(OUT, encoder), IntentClassifier.load(OUT, encoder)
        records, resolutions, raw, cosine = [], [], [], []
        for row in rows:
            old, new = before.classify(row['text']), after.classify(row['text'])
            if old['base_ranking'] != new['base_ranking']:
                raise ValueError('RAW_CLASSIFIER_SCORE_CHANGED: ' + row['id'])
            previous, current = old['resolution'], new['resolution']
            before_ok, after_ok = _valid(row, previous), _valid(row, current)
            changed = any(previous[k] != current[k] for k in
                          ['intent_label', 'component_labels', 'status', 'contains_restricted_component'])
            record = dict(id=row['id'], question=row['text'], gold=row['intent_label'],
                gold_components=row['component_intents'], expected_status=row.get('expected_status'),
                before=previous, after=current,
                base_ranking=new['base_ranking'], raw_scores_unchanged=True)
            records.append(record)
            if changed:
                changes.append(dict(evaluation_set=name, **record))
            if not after_ok:
                failures.append(dict(evaluation_set=name, id=row['id']))
            if before_ok and not after_ok:
                raise ValueError('REGRESSION: ' + row['id'])
            resolutions.append(current)
            raw.append(new['base_ranking'])
            cosine.append(new['reference_ranking'])
        (output / (name + '-cases.jsonl')).write_text(
            ''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in records), encoding='utf-8', newline='\n')
        predicted = [dict(groups=[dict(intent_label=r['intent_label'])]) for r in resolutions]
        metrics[name] = dict(cases=len(rows), resolution=summarize_evaluation(rows, predicted, after.manifest['labels']),
            detailed=summarize_resolution(rows, resolutions),
            base_ranking=summarize_evaluation(rows, raw, after.manifest['labels']),
            cosine=summarize_evaluation(rows, cosine, after.manifest['labels']))
        transforms = [('ascii', unaccented), ('polite', lambda s: 'Vui lòng: ' + s),
            ('greeting', lambda s: 'Xin chào, ' + s),
            ('ticker', lambda s: re.sub(r'\b(?:FPT|HPG|VCB|BID|SSI|VNM|ACB|REE|DGC|MWG|PNJ|GMD|TCB)\b',
                                      'ZZZ', s, flags=re.IGNORECASE))]
        probes, vectors = [], []
        for row, vector in zip(rows, values):
            for transform, function in transforms:
                text = function(row['text'])
                if text != row['text']:
                    probes.append(dict(row, text=text, transform=transform))
                    vectors.append(vector)
        controlled = IntentClassifier.load(OUT, FrozenEncoder(probes, vectors, model))
        for probe in probes:
            meta_count += 1
            result = controlled.classify(probe['text'])['resolution']
            if not _valid(probe, result):
                meta_failures.append(dict(evaluation_set=name, id=probe['id'], transform=probe['transform'],
                    question=probe['text'], gold=probe['intent_label'], gold_components=probe['component_intents'], actual=result))
    for name, digest in {**hashes, **data_hashes}.items():
        if sha(ROOT / name) != digest:
            raise ValueError('SOURCE_OR_DATA_CHANGED_DURING_AUDIT: ' + name)
    write(output / 'changes.json', changes)
    write(output / 'metamorphic-failures.json', meta_failures)
    summary = dict(status='PASS' if not failures and not meta_failures else 'FAIL',
        metrics=metrics, known_failure_ids=failures, regressions=0, raw_scores_preserved=True,
        controlled_metamorphic_cases=meta_count, controlled_metamorphic_failures=len(meta_failures),
        model_and_training_data_unchanged=True, blind_acceptance_available=False)
    write(output / 'summary.json', summary)
    print(json.dumps(dict(status=summary['status'],
        correct={n: m['detailed']['complete_classification_correct_count'] for n, m in metrics.items()},
        controlled_metamorphic_cases=meta_count, meta_failures=len(meta_failures), failures=failures), indent=2))
    return summary['status'] == 'PASS'


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=FIX / 'audit')
    raise SystemExit(0 if audit(parser.parse_args().output) else 1)
