"""Freeze/verify real consumer comparisons and advisory handoff, without I/O services."""
import argparse
from datetime import date
import difflib
import hashlib
import importlib.util
import json

from run_s5_intent_review2 import ROOT, BASE, OUT, raw_ranking
from run_s5_intent_reviewfix import read, write
from src.retrieval_orchestration.intent_routing import decide_intent_route
from src.retrieval_orchestration.intent_handoff import prepare_intent_review
from src.retrieval_orchestration.live_research import analyze_live


def compute():
    original_path = BASE / 'consumer-original.py'
    fixed_path = ROOT / 'backend/src/retrieval_orchestration/intent_routing.py'
    spec = importlib.util.spec_from_file_location('huyen_original', original_path)
    original = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(original)

    def ranking(label='NUMERIC', first=.71, second=.4):
        other = 'NEWS' if label != 'NEWS' else 'NUMERIC'
        return dict(ranking_policy='cosine-max-per-label-v1', score_type='COSINE_SIMILARITY_NOT_PROBABILITY',
                    groups=[dict(intent_label=label, score=first), dict(intent_label=other, score=second)])

    missing = []
    for keys in [('ranking_policy',), ('score_type',), ('ranking_policy', 'score_type')]:
        raw = ranking()
        for key in keys: del raw[key]
        before = original.decide_intent_route(raw, company_ticker='FPT')
        after = decide_intent_route(raw, company_ticker='FPT')
        assert before['decision'] == 'SEARCH'
        assert after['decision'] == 'REJECT_CLASSIFICATION' and after['need_fallback'] is False
        assert after['route'] is None and after['fallback_payload'] is None
        missing.append(dict(missing=list(keys), before=before, after=after))
    comparisons, intentional = [], 0
    for label in ['NUMERIC', 'REPORT_CONTENT', 'NEWS', 'PERSON_ROLE', 'ENTITY_RELATION', 'MIXED', 'TREND']:
        for first, second in [(.9, .4), (.65, .57), (.68, .64), (.6, .4), (.9, .85)]:
            raw = ranking(label, first, second)
            before = original.decide_intent_route(raw, company_ticker='FPT')
            after = decide_intent_route(raw, company_ticker='FPT')
            if label == 'MIXED' and before['decision'] == 'SEARCH':
                assert after['reason_code'] == 'MIXED_COMPONENTS_UNVERIFIED' and after['route'] is None
                intentional += 1
            else:
                assert before == after
            comparisons.append(dict(label=label, scores=[first, second], before=before['decision'], after=after['decision'], reason=after['reason_code']))
    price = analyze_live('Giá cổ phiếu FPT hôm nay bao nhiêu?', today=date(2026, 11, 12))
    assert price['decision'] == 'MARKET_LOOKUP' and price['scope']['source_type'] == 'PRICE'
    assert price['scope']['metric_code'] == 'LAST_PRICE'
    handoffs = []
    for row in read(OUT / 'results.json')['review2_probes']:
        handoff = prepare_intent_review(raw_ranking(row), row['resolution'])
        assert handoff['status'] == 'NEED_VALIDATION' and handoff['accepted_intent'] is None and handoff['route'] is None
        handoffs.append(dict(id=row['id'], proposed_final_label=row['final_label'], handoff=handoff))
    target = next(r for r in handoffs if r['id'] == 'R2-01')
    assert target['proposed_final_label'] == 'NUMERIC'
    assert target['handoff']['reason'] == 'UNRESOLVED_REQUEST_TARGET'
    patch = ''.join(difflib.unified_diff(original_path.read_text(encoding='utf-8').splitlines(True),
                  fixed_path.read_text(encoding='utf-8').splitlines(True),
                  fromfile='a/backend/src/retrieval_orchestration/intent_routing.py',
                  tofile='b/backend/src/retrieval_orchestration/intent_routing.py', n=0))
    watched = [original_path, fixed_path, ROOT / 'backend/src/retrieval_orchestration/intent_handoff.py',
               ROOT / 'backend/src/retrieval_orchestration/live_research.py',
               ROOT / 'backend/tests/test_s5_intent_consumer_contract.py',
               ROOT / 'backend/tests/test_s5_intent_handoff.py', OUT / 'results.json',
               BASE / 'consumer-source.json', ROOT / 'backend/scripts/check_s5_intent_handoff.py']
    def digest(path):
        data = path.read_bytes()
        if path.suffix == '.py': data = data.replace(b'\r\n', b'\n')
        return hashlib.sha256(data).hexdigest()
    proof = dict(status='PASS', python_source_hash_newlines='CANONICAL_LF',
                 source_hashes={p.relative_to(ROOT).as_posix(): digest(p) for p in watched},
                 missing_metadata=missing, valid_cosine_comparisons=comparisons,
                 unchanged_valid_cosine=35-intentional, intentional_mixed_deferrals=intentional,
                 current_price_resolution=price, advisory_handoffs=handoffs,
                 patch_sha256=hashlib.sha256(patch.encode('utf-8')).hexdigest(),
                 patch_apply_requires='git apply --unidiff-zero; verify exact original source first',
                 huyen_remote_branch_modified=False, runtime_registered=False,
                 no_claim_that_deferral_is_correct_label_or_route=True)
    return proof, patch


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--verify', action='store_true')
    args = parser.parse_args()
    proof, patch = compute()
    target, patch_path = BASE / 'integration-final-checks.json', BASE / 'consumer-fix.patch'
    if args.verify:
        assert read(target) == proof
        assert patch_path.read_text(encoding='utf-8') == patch
    else:
        if target.exists(): raise FileExistsError('Use --verify for the frozen handoff')
        if patch_path.exists(): assert patch_path.read_text(encoding='utf-8') == patch
        write(target, proof)
        patch_path.write_text(patch, encoding='utf-8', newline='\n')
    print(json.dumps(dict(status='PASS', metadata_missing_rejected=3, unchanged_cosine=proof['unchanged_valid_cosine'],
                         intentional_mixed_deferrals=proof['intentional_mixed_deferrals'],
                         advisory_handoffs=32, price_source='PRICE', runtime_registered=False), indent=2))


if __name__ == '__main__':
    main()
