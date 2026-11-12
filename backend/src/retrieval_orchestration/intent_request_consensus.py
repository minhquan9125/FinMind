"""Decision evidence only: preserve classifier scores and never claim confidence."""
import numpy as np


def resolve(base,parts,labels):
    base=np.asarray(base,dtype=np.float64)
    values=np.asarray(parts,dtype=np.float64)
    if base.shape!=(len(labels),) or not np.isfinite(base).all() or 'MIXED' not in labels:
        raise ValueError('INVALID_BASE_SCORES')
    order=sorted(range(len(labels)),key=lambda i:(-base[i],labels[i]))
    label=labels[order[0]]
    reason='WHOLE_QUERY_UNCHANGED'
    components=[]
    if values.size:
        if values.ndim!=2 or values.shape[1]!=len(labels) or not np.isfinite(values).all():
            raise ValueError('INVALID_COMPONENT_SCORES')
        best=[min(range(len(labels)),key=lambda j:(-row[j],labels[j])) for row in values]
        if len(best)==1:
            label=labels[best[0]]
            reason='SINGLE_PRIMARY_REQUEST_AFTER_SUPPORT_REMOVAL'
        elif label!='MIXED':
            for i,a in enumerate(best):
                for b in best[i+1:]:
                    if a!=b and labels[a]!='MIXED' and labels[b]!='MIXED' and {a,b}==set(order[:2]):
                        label='MIXED'
                        reason='TWO_REQUESTS_SUPPORTED_BY_WHOLE_QUESTION'
                        components=[labels[a],labels[b]]
                        break
                if components: break
    return dict(intent_label=label,confidence=None,reason=reason,component_labels=components,
                ranking_policy='intent-request-consensus-v1',score_type='DECISION_EVIDENCE_NO_CONFIDENCE',runtime_enabled=False)
