"""Bounded source recovery before answer generation, never after a source error."""
import asyncio
import copy
import re

from .retrieval_flow.intent import _fold
from ..documents.chunk_reconstruction import ReconstructionError


_STOP = set(('ai la co khong theo trong nam bao nhieu nao gi cua cho toi minh hay '
             'ngan hang cong ty tap doan thong tin noi dung ve duoc nhung cac mot '
             'nay do the thi xin biet xem giup voi tu den va khi moi hieu').split())


def recovery_timed_out(pack):
    return any(t.get('status')=='TIMEOUT' or t.get('reason')=='FALLBACK_TIMEOUT'
        for t in pack.get('retrieval_trace',[]))


def topical_match(question, items, companies=()):
    """Recall heuristic only. Citation/claim validation remains authoritative."""
    stop = _STOP | {s.lower() for s in companies}
    terms = {w for w in re.findall(r'[a-z]+', _fold(question)) if len(w)>1 and w not in stop}
    if not terms:
        return False
    for item in items:
        # Headers repeat the company/source and are not evidence of relevance.
        body = item.get('passage', '').partition('\n')[2]
        words = set(re.findall(r'[a-z]+', _fold(body)))
        if len(terms & words) >= min(3, len(terms)):
            return True
    return False


async def recover_content(retrieve, question, scope, *, fallback_timeout=20):
    """At most two source lookups, one generation downstream, same frozen index.

    Only CONTENT (unspecified source) may cross source types. Other requests
    stay on their original source, company, dates and accounting scope.
    """
    if scope.get('source_type') != 'CONTENT':
        return await retrieve(question, copy.deepcopy(scope))
    norm = _fold(question)
    first = 'BCTN' if re.search(r'\b(?:chien luoc|rui ro|co cau|hoat dong kinh doanh|ben vung)\b', norm) else 'NEWS'
    order = [first, 'NEWS' if first == 'BCTN' else 'BCTN']
    primary = await retrieve(question, {**copy.deepcopy(scope), 'source_type': first})
    trace = [{'source': first, 'reason': 'PRIMARY', 'items': len(primary['items'])}]
    if topical_match(question, primary['items'], scope.get('companies', [])):
        return {**primary, 'retrieval_trace': trace}
    try:
        secondary = await asyncio.wait_for(
            retrieve(question, {**copy.deepcopy(scope), 'source_type': order[1]}), fallback_timeout)
    except TimeoutError:
        return {**primary, 'retrieval_trace': trace + [{'source': order[1], 'reason': 'FALLBACK_TIMEOUT'}]}
    if (primary['corpus_version_id'], primary['data_version']) != (secondary['corpus_version_id'], secondary['data_version']):
        raise ReconstructionError('CONTENT_CORPUS_CHANGED', 'Serving corpus changed during recovery')
    trace.append({'source': order[1], 'reason': 'LOW_TOPICAL_RECALL', 'items': len(secondary['items'])})
    items = {}
    # Supplemental source first: unrelated primary candidates must not crowd it out.
    for item in [*secondary['items'], *primary['items']]:
        eid = item['evidence_id']
        if eid in items and any(items[eid].get(k)!=item.get(k) for k in (
                'chunk_id','source_id','source_type','source_sha256','content_sha256','locator','passage')):
            raise ReconstructionError('CONTENT_EVIDENCE_CHANGED', 'Conflicting source bindings')
        items[eid] = item
    return {**primary, 'items': list(items.values())[:10], 'retrieval_trace': trace,
            'retrieval_backend': primary.get('retrieval_backend', '') + '_recovery'}
