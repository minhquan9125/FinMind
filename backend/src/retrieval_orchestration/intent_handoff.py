"""Prepare advisory evidence for review; never execute retrieval or trust a score.

Only CHECK_COSINE_POLICY permits forwarding the original, unchanged ranking to
04.2's scope/threshold gates. It is not SEARCH or an accepted intent. All other
statuses stop automatic routing; callers must implement validation explicitly.
"""
from .intent_routing import INTENT_ROUTES


def prepare_intent_review(ranking, resolution):
    result = dict(status='REJECT_CLASSIFICATION', reason='INVALID_HANDOFF_CONTRACT',
                  accepted_intent=None, proposed_intent=None, raw_top_intent=None,
                  route=None, confidence=None, runtime_enabled=False)
    contracts = {
        ('cosine-max-per-label-v1', 'COSINE_SIMILARITY_NOT_PROBABILITY'),
        ('intent-linear-v1', 'CLASSIFIER_PROBABILITY_UNCALIBRATED'),
    }
    if not isinstance(ranking, dict) or not isinstance(resolution, dict):
        return result
    policy, kind = ranking.get('ranking_policy'), ranking.get('score_type')
    if not isinstance(policy, str) or not isinstance(kind, str) or (policy, kind) not in contracts:
        return result
    if (resolution.get('ranking_policy') != 'intent-request-objectives-v5'
            or resolution.get('score_type') != 'DECISION_EVIDENCE_NO_CONFIDENCE'
            or 'confidence' not in resolution or resolution['confidence'] is not None
            or resolution.get('runtime_enabled') is not False):
        return result
    groups = ranking.get('groups')
    label = resolution.get('intent_label')
    unresolved, components = resolution.get('unresolved_requests'), resolution.get('component_labels')
    if (not isinstance(groups, list) or not groups or not isinstance(groups[0], dict)
            or not isinstance(label, str) or label not in INTENT_ROUTES
            or not isinstance(groups[0].get('intent_label'), str) or groups[0]['intent_label'] not in INTENT_ROUTES
            or not isinstance(unresolved, list) or any(not isinstance(text, str) for text in unresolved)
            or not isinstance(components, list)
            or any(not isinstance(c, str) or c not in INTENT_ROUTES for c in components)):
        return result
    raw_label = groups[0]['intent_label']
    result.update(status='NEED_VALIDATION', proposed_intent=label, raw_top_intent=raw_label)
    if unresolved:
        result['reason'] = 'UNRESOLVED_REQUEST_TARGET'
    elif label == 'MIXED' and len(set(components) - {'MIXED'}) < 2:
        result['reason'] = 'MIXED_COMPONENTS_UNVERIFIED'
    elif raw_label != label:
        result['reason'] = 'LABEL_DISAGREEMENT'
    elif kind == 'CLASSIFIER_PROBABILITY_UNCALIBRATED':
        result['reason'] = 'UNCALIBRATED_CLASSIFIER'
    else:
        result.update(status='CHECK_COSINE_POLICY', reason='ORIGINAL_BASELINE_POLICY_REQUIRED')
    return result
