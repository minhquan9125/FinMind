"""Offline scorer candidates; no production router imports this module."""
from collections import defaultdict
import numpy as np
from .intent_experiment import policy_observation


def _families(rows):
    families=defaultdict(list)
    for i,row in enumerate(rows):
        if row['split']!='LIBRARY':
            raise ValueError('LIBRARY_ONLY')
        families[row['family_id']].append(i)
    if not families:
        raise ValueError('EMPTY_TRAINING_ROWS')
    for indices in families.values():
        if len({rows[i]['intent_label'] for i in indices})!=1:
            raise ValueError('FAMILY_LABEL_CONFLICT')
    return families


def family_weights(rows):
    families=_families(rows)
    by_label=defaultdict(list)
    for family,indices in families.items():
        by_label[rows[indices[0]]['intent_label']].append(family)
    weights=np.empty(len(rows),dtype=np.float64)
    for label,names in by_label.items():
        for name in names:
            indices=families[name]
            weights[indices]=len(rows)/(len(by_label)*len(names)*len(indices))
    return weights


def family_folds(rows,n_folds=4):
    families=_families(rows)
    by_label=defaultdict(list)
    for family,indices in families.items():
        by_label[rows[indices[0]]['intent_label']].append(family)
    if type(n_folds) is not int or n_folds<2 or any(len(names)<n_folds for names in by_label.values()):
        raise ValueError('NOT_ENOUGH_FAMILIES_PER_LABEL')
    folds=np.empty(len(rows),dtype=int)
    for names in by_label.values():
        for i,name in enumerate(sorted(names)):
            folds[families[name]]=i%n_folds
    return folds


def normalized(values):
    values=np.asarray(values,dtype=np.float64)
    if values.ndim!=2 or not np.isfinite(values).all():
        raise ValueError('INVALID_VECTORS')
    norms=np.linalg.norm(values,axis=1,keepdims=True)
    if not np.isfinite(norms).all() or (norms<=0).any():
        raise ValueError('INVALID_VECTOR_NORM')
    return values/norms


def centroid_vectors(rows,values):
    families=_families(rows)
    values=normalized(values)
    if len(rows)!=len(values):
        raise ValueError('ROW_VECTOR_ALIGNMENT')
    by_label=defaultdict(list)
    for indices in families.values():
        center=normalized(values[indices].mean(axis=0,keepdims=True))[0]
        by_label[rows[indices[0]]['intent_label']].append(center)
    labels=sorted(by_label)
    return labels,normalized(np.stack([np.mean(by_label[label],axis=0) for label in labels]))


def classifier_probabilities(values,coefficients,intercepts):
    logits=np.asarray(values,dtype=np.float64)@np.asarray(coefficients,dtype=np.float64).T+intercepts
    if logits.ndim!=2 or not np.isfinite(logits).all():
        raise ValueError('INVALID_LOGITS')
    exponential=np.exp(logits-logits.max(axis=1,keepdims=True))
    return exponential/exponential.sum(axis=1,keepdims=True)


def rankings(questions,scores,labels,policy,score_type,model):
    scores=np.asarray(scores,dtype=np.float64)
    if scores.shape!=(len(questions),len(labels)) or not np.isfinite(scores).all():
        raise ValueError('INVALID_SCORE_MATRIX')
    result=[]
    for question,values in zip(questions,scores):
        order=sorted(range(len(labels)),key=lambda i:(-values[i],labels[i]))
        result.append(dict(question=question,ranking_policy=policy,score_type=score_type,
            model=dict(name=model['name'],revision=model['revision']),runtime_enabled=False,
            groups=[dict(rank=j+1,intent_label=labels[i],score=float(values[i])) for j,i in enumerate(order)]))
    return result


def baseline_policy(ranking):
    if (ranking['ranking_policy']!='cosine-max-per-label-v1'
            or ranking['score_type']!='COSINE_SIMILARITY_NOT_PROBABILITY'):
        raise ValueError('UNSUPPORTED_SCORE_CONTRACT')
    first,second=ranking['groups'][:2]
    return policy_observation(first['intent_label'],first['score'],first['score']-second['score'])
