import numpy as np
import pytest

from src.retrieval_orchestration.intent_additive import append_library, selection_key
from src.retrieval_orchestration.intent_library import IntentLibrary


def base():
    return IntentLibrary((dict(id='old', text='old text', intent_label='NEWS', component_intents=[]),),
                         np.array([[1,0]],dtype=np.float32),
                         dict(model={'name':'TEST','revision':'a'*40}, library_version='old',
                              dataset_version='old-data', label_schema_version='labels'))


def test_append_preserves_old_rows_and_vector_bytes():
    old=base()
    result=append_library(old,[dict(id='new',text='new text',intent_label='PERSON_ROLE',component_intents=[])],
                          np.array([[0,1]],dtype=np.float32),'candidate')
    assert result.rows[0]==old.rows[0]
    assert result.vectors[:1].tobytes()==old.vectors.tobytes()
    assert result.vectors.shape==(2,2)
    assert result.manifest['status']=='EXPERIMENTAL_DRAFT'
    assert old.manifest['library_version']=='old'


def test_append_rejects_duplicate_ids():
    with pytest.raises(ValueError,match='DUPLICATE'):
        append_library(base(),[dict(id='old',text='another')],np.array([[0,1]],dtype=np.float32),'bad')


def test_append_rejects_non_unit_or_misaligned_vectors():
    with pytest.raises(ValueError,match='VECTOR'):
        append_library(base(),[dict(id='new',text='new')],np.array([[0,2]],dtype=np.float32),'bad')


def test_eligibility_beats_higher_development_score_when_selecting():
    safe=dict(eligible=True,wrong_regression=0,wrong_dev=0,regressed=0,dev_hits=40,regression_hits=25,rows=100,name='a')
    unsafe=dict(safe,eligible=False,dev_hits=84)
    assert selection_key(safe)<selection_key(unsafe)


def test_regression_is_penalized_before_development_hits():
    safer=dict(eligible=False,wrong_regression=0,wrong_dev=0,regressed=1,dev_hits=40,regression_hits=25,rows=100,name='a')
    riskier=dict(safer,regressed=2,dev_hits=84)
    assert selection_key(safer)<selection_key(riskier)
