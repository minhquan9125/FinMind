"""A bounded union of independently verified DB/feed evidence packs.

The child versions remain intact: a price snapshot is never relabeled as a DB
chunk, nor assigned the news corpus ID. Nested bundles are not accepted.
"""
from copy import deepcopy
import hashlib
import json
import uuid
from .citations import CitationError


def _digest(packs):
    return hashlib.sha256(json.dumps(packs,sort_keys=True,ensure_ascii=False,separators=(',',':'),
                                    allow_nan=False).encode()).hexdigest()


def _union(packs):
    from .citations import prepare_evidence
    if not isinstance(packs,list) or not 1<=len(packs)<=3:
        raise CitationError('INVALID_EVIDENCE')
    result={}
    for pack in packs:
        if not isinstance(pack,dict) or pack.get('schema_version') not in ('1.1','1.2'):
            raise CitationError('INVALID_EVIDENCE')
        for eid,item in prepare_evidence(pack).items():
            if eid in result and result[eid]!=item:
                raise CitationError('INVALID_EVIDENCE')
            result[eid]=item
    if not 1<=len(result)<=30:
        raise CitationError('INVALID_EVIDENCE')
    return result


def bundle_packs(packs):
    items=_union(packs)
    return dict(schema_version='1.3',query_id=str(uuid.uuid4()),
        data_version=dict(kind='SOURCE_BUNDLE',id=_digest(packs)),
        evidence_packs=deepcopy(packs),items=list(items.values()),retrieval_backend='stored_news_and_market_data')


def prepare_bundle(pack):
    try:
        uuid.UUID(pack['query_id'])
        children=pack['evidence_packs']
        items=_union(children)
        if pack.get('data_version')!=dict(kind='SOURCE_BUNDLE',id=_digest(children)) or pack.get('items')!=list(items.values()):
            raise CitationError('INVALID_EVIDENCE')
        return items
    except (KeyError,TypeError,ValueError,AttributeError):
        raise CitationError('INVALID_EVIDENCE') from None
