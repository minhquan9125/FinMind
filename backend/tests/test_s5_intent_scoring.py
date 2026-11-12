"""Grouped fitting and score-contract guards for the offline scorer experiment."""
import numpy as np
import pytest
from src.retrieval_orchestration.intent_scoring import family_weights, family_folds, centroid_vectors, classifier_probabilities, baseline_policy


def samples():
    return [dict(id=f'{label}{family}{variant}',intent_label=label,family_id=f'{label}-{family}',split='LIBRARY')
            for label in ['A','B'] for family in range(4) for variant in range(family+1)]


def test_family_weights_give_equal_total_weight_to_each_family_and_label():
    rows=samples()
    weights=family_weights(rows)
    assert weights.sum()==pytest.approx(len(rows))
    assert len({round(sum(w for r,w in zip(rows,weights) if r['family_id']==f),9)
                for f in {r['family_id'] for r in rows}})==1


def test_all_variants_stay_in_one_fold_with_all_classes_present():
    rows=samples()
    fold=family_folds(rows,4)
    for family in {r['family_id'] for r in rows}:
        assert len({fold[i] for i,r in enumerate(rows) if r['family_id']==family})==1
    for k in range(4):
        assert {r['intent_label'] for i,r in enumerate(rows) if fold[i]==k}=={'A','B'}


def test_reject_evaluation_rows_during_training_preparation():
    with pytest.raises(ValueError,match='LIBRARY_ONLY'):
        family_weights([dict(id='test',family_id='f',intent_label='A',split='TEST')])


def test_reject_family_with_conflicting_labels():
    rows=[dict(id='a',family_id='f',intent_label='A',split='LIBRARY'),dict(id='b',family_id='f',intent_label='B',split='LIBRARY')]
    with pytest.raises(ValueError,match='FAMILY_LABEL_CONFLICT'):
        family_folds(rows,2)


def test_centroid_gives_each_family_equal_weight_not_each_variant():
    rows=[dict(id=str(i),intent_label='A',family_id=f,split='LIBRARY') for i,f in enumerate(['x','x','x','y'])]
    labels,centers=centroid_vectors(rows,np.array([[1,0],[1,0],[1,0],[0,1]]))
    assert labels==['A']
    assert np.allclose(centers[0],np.array([1,1])/np.sqrt(2))


def test_softmax_is_stable_and_matches_hand_calculation():
    result=classifier_probabilities(np.array([[1.,0.]]),np.array([[1000.,0.],[999.,0.]]),np.zeros(2))
    assert np.isfinite(result).all() and result.sum()==pytest.approx(1)
    assert result[0,0]==pytest.approx(1/(1+np.exp(-1)))


@pytest.mark.parametrize('policy,score_type',[('linear-v1','CLASSIFIER_PROBABILITY_UNCALIBRATED'),('centroid-v1','COSINE_SIMILARITY_NOT_PROBABILITY')])
def test_legacy_threshold_rejects_classifier_and_centroid(policy,score_type):
    with pytest.raises(ValueError,match='UNSUPPORTED_SCORE_CONTRACT'):
        baseline_policy(dict(ranking_policy=policy,score_type=score_type,groups=[]))


def test_legacy_policy_uses_baseline_only():
    result=baseline_policy(dict(ranking_policy='cosine-max-per-label-v1',score_type='COSINE_SIMILARITY_NOT_PROBABILITY',
        groups=[dict(intent_label='PERSON_ROLE',score=.8),dict(intent_label='NUMERIC',score=.6)]))
    assert result=='GRAPH'


def test_minimal_known_probe_without_family_can_be_reported(monkeypatch):
    from pathlib import Path
    import importlib
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[1]/'scripts'))
    experiment=importlib.import_module('run_s5_intent_scorer')
    result=experiment.report([dict(id='known-1',text='find news',intent_label='NEWS')],
        [dict(ranking_policy='intent-linear-v1',score_type='CLASSIFIER_PROBABILITY_UNCALIBRATED',
              groups=[dict(intent_label='NEWS',score=.8),dict(intent_label='NUMERIC',score=.2)])],['NEWS','NUMERIC'])
    assert result['metrics']['hits']=={'1':1,'3':1,'5':1}
    assert result['cases'][0]['family_id']=='known-1'
