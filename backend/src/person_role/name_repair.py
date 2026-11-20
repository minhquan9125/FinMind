"""Repair Person spans using an explicitly checked source roster.

Never edits source text/hash or merges identities solely because names match.
Unknown Person proposals are excluded instead of guessed.
"""
from copy import deepcopy
import re
from .contract.entities import normalize
from .contract.contracts import validate_envelope


def repair_person_names(envelope, checked_names):
    validate_envelope(envelope)
    result=deepcopy(envelope)
    raw=deepcopy(envelope)
    raw.update(entities=[],mentions=[],relations=[])
    proposals=[]
    allowed=set()
    for c in raw['chunks']:
        for name in checked_names:
            for match in re.finditer(r'(?<!\w)'+re.escape(name)+r'(?!\w)',c['text']):
                span=(c['document_id'],c['chunk_id'],match.start(),match.end())
                allowed.add(span)
                proposals.append(dict(document_id=span[0],chunk_id=span[1],entity_type='Person',start=span[2],end=span[3]))
    normalized=normalize(raw['chunks'],proposals=proposals)
    types={e['entity_id']:e['entity_type'] for e in normalized['entities']}
    good_mentions=[m for m in normalized['mentions'] if types[m['entity_id']]=='Person'
                   and (m['document_id'],m['chunk_id'],m['start'],m['end']) in allowed]
    good_entities={e['entity_id']:e for e in normalized['entities'] if e['entity_type']=='Person'}
    old_types={e['entity_id']:e['entity_type'] for e in envelope['entities']}
    by_span={(m['document_id'],m['chunk_id'],m['start'],m['end']):m for m in good_mentions}
    entity_map={};mention_map={};changes=[]
    for m in envelope['mentions']:
        if old_types[m['entity_id']]!='Person':continue
        span=(m['document_id'],m['chunk_id'],m['start'],m['end'])
        replacement=by_span.get(span)
        if replacement is None:
            matches=[n for n in good_mentions if (n['document_id'],n['chunk_id'])==span[:2]
                     and m['start']<=n['start']<n['end']<=m['end']]
            # A glued two-person span is discarded, never assigned to one person.
            replacement=matches[0] if len(matches)==1 else None
        if replacement:
            entity_map.setdefault(m['entity_id'],set()).add(replacement['entity_id'])
            mention_map[m['mention_id']]=replacement['mention_id']
        if not replacement or m['raw_name']!=replacement['raw_name']:
            changes.append(dict(old_name=m['raw_name'],old_mention_id=m['mention_id'],
                                new_name=replacement['raw_name'] if replacement else None,
                                action='CORRECT_SPAN' if replacement else 'EXCLUDE_UNVERIFIED_OR_MERGED_NAME'))
    for relation in result['relations']:
        for key in ('subject_id','object_id'):
            old=relation[key]
            if old_types[old]!='Person':continue
            targets=entity_map.get(old,set())
            if len(targets)!=1:
                raise ValueError('Cannot safely remap relation person endpoint: '+relation['relation_id'])
            relation[key]=next(iter(targets))
        a=relation['attributes']
        for key in ('person_mention_id',):
            if key in a:
                if a[key] not in mention_map:raise ValueError('Unrepairable person mention reference')
                a[key]=mention_map[a[key]]
        if 'person_mention_ids' in a:
            a['person_mention_ids']=sorted({mention_map[mid] for mid in a['person_mention_ids']})
    retained=[e for e in result['entities'] if e['entity_type']!='Person']
    used={m['entity_id'] for m in good_mentions}
    # Preserve an existing entity when its identity and span were already correct.
    old_entities={e['entity_id']:e for e in result['entities']}
    retained.extend(deepcopy(old_entities.get(eid,good_entities[eid])) for eid in sorted(used))
    result['entities']=retained
    result['mentions']=[m for m in result['mentions'] if old_types[m['entity_id']]!='Person']+good_mentions
    validate_envelope(result)
    if result['chunks']!=envelope['chunks'] or result['documents']!=envelope['documents']:
        raise ValueError('Source changed during name repair')
    return result,dict(changes=changes,person_mentions=len(good_mentions),
                       identities_merged=False,source_text_changed=False)
