"""Persisted, independently replayed source quotes behind a graph answer."""
from copy import deepcopy
import hashlib
import uuid

from ...graph_review.models import Evidence


def prepare_graph_source_evidence(pack):
    from .citations import CitationError
    try:
        version = pack['data_version']['id']
        uuid.UUID(version)
        if pack['data_version']['kind'] != 'GRAPH' or not pack.get('query_id'): raise ValueError()
        items = pack['items']
        if not isinstance(items, list) or not 1 <= len(items) <= 100: raise ValueError()
        out = {}
        for item in items:
            uuid.UUID(item['evidence_id'])
            ref = Evidence.model_validate(item['source_ref'])
            if (item['evidence_id'] in out or item.get('source_type') != 'GRAPH_SOURCE'
                    or item.get('source_verified') is not True or item.get('graph_version_id') != version
                    or item['source_id'] != ref.document_id or item['chunk_id'] != ref.chunk_id
                    or item['source_sha256'] != ref.source_sha256 or item['locator'] != ref.locator
                    or item['passage'] != ref.quote or not 1 <= len(ref.quote) <= 12000
                    or hashlib.sha256(ref.quote.encode()).hexdigest() != item['content_sha256']):
                raise ValueError()
            out[item['evidence_id']] = deepcopy(item)
        return out
    except (KeyError, ValueError, TypeError, AttributeError):
        raise CitationError('INVALID_EVIDENCE') from None
