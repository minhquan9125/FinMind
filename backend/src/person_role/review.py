"""Evidence-bound review worksheet, distinct from contract graph relations.

Works on pageless sources too, without inventing a physical PDF page or an
entity ID. OCR row attribution and document-company context remain unverified.
"""
from datetime import date
import hashlib
import json
import re
from .extractor import ROLE, POSITIONS

HONORIFIC = re.compile(r'\b(?:ông|bà)\s+', re.I)
WORD = re.compile(r'[^\W\d_]+', re.UNICODE)
STOP = {'Ông', 'Bà', 'Chủ', 'Phó', 'Tổng', 'Giám', 'Kế', 'Thành', 'Trưởng', 'Chức', 'Từ', 'Bổ', 'Miễn', 'Người', 'Công', 'Ngày'}
EVENTS = (
    ('RESIGNATION_REQUESTED', r'(?:đơn\s+(?:xin\s+)?)?(?:xin\s+từ\s+nhiệm|xin\s+thôi|xin\s+từ\s+chức)|đơn\s+từ\s+nhiệm'),
    ('NOMINATED', r'đề\s+cử|ứng\s+cử'),
    ('RESIGNED', r'từ\s+nhiệm|từ\s+chức'),
    ('DISMISSED', r'miễn\s+nhiệm|bãi\s+nhiệm'),
    ('APPOINTED', r'bổ\s+nhiệm|được\s+bầu'),
)
EVENT_PATTERN = re.compile('|'.join(f'(?P<E{i}>{p})' for i, (_, p) in enumerate(EVENTS)), re.I)
DATE_PATTERN = re.compile(r'\b(\d{1,2})[/.\-](\d{1,2})[/.\-](\d{4})\b|\b(\d{1,2})\s+tháng\s+(\d{1,2})\s+năm\s+(\d{4})\b', re.I)


def names(text):
    """Propose spans only: these are not verified person entities."""
    result=[]
    for prefix in HONORIFIC.finditer(text):
        tokens=[]
        previous=prefix.end()
        for word in WORD.finditer(text, prefix.end()):
            token=word.group()
            if text[previous:word.start()].strip() or not token[0].isupper() or token in STOP:
                break
            tokens.append(word)
            previous=word.end()
            if len(tokens)==6:
                break
        if len(tokens)>=2:
            result.append((tokens[0].start(), tokens[-1].end()))
    return result


def _review_source_first(text, source):
    """Produce manual-review items from unchanged, hash-checked chunk text."""
    if hashlib.sha256(text.encode()).hexdigest()!=source['content_hash']:
        raise ValueError('Review source hash mismatch')
    people=names(text)
    items=[]
    for i, (start,end) in enumerate(people):
        # Do not transfer another person's trailing event to this person.
        right=people[i+1][0] if i+1<len(people) else len(text)
        tail=text[end:min(right,end+220)]
        roles=list(ROLE.finditer(tail))
        left=max(people[i-1][1] if i else 0, start-65)
        prefix=text[left:start]
        before_roles=list(ROLE.finditer(prefix))
        before=bool(before_roles and re.fullmatch(r'\s+của\s+(?:ông|bà)\s+',prefix[before_roles[-1].end():],re.I))
        if before:
            role=before_roles[-1]
            role_start=left+role.start()
            role_end=left+role.end()
            nearby=tail
        elif roles:
            role=roles[0]
            gap=tail[:role.start()]
            if len(gap)>45 or re.search(r'\d|[.;]|\b(?:Năm|Mua|Công ty)\b',gap):
                continue
            role_start=end+role.start()
            role_end=end+role.end()
            nearby=tail[role.end():]
        else:
            continue
        # Only an immediately adjacent event may be attributed to this row.
        # Numbers/another title/another sentence between title and event break
        # the association instead of assigning the next row's dismissal.
        tail_events=list(EVENT_PATTERN.finditer(nearby))
        tail_events=[m for m in tail_events if re.fullmatch(r'[\s(,:\-–—]*',nearby[:m.start()])]
        prefix_events=list(EVENT_PATTERN.finditer(prefix))
        if not before:
            prefix_events=[m for m in prefix_events if re.fullmatch(r'\s*(?:(?:ông|bà)\s*)?',prefix[m.end():],re.I)]
        # A preceding event may govern a list of people; record as uncertain,
        # never turn a nearest-person heuristic into a graph assertion.
        event=tail_events[0] if tail_events else prefix_events[-1] if prefix_events else None
        stage=EVENTS[int(event.lastgroup[1:])][0] if event else 'ROLE_AT_SOURCE_TIME'
        evidence_start=left if prefix_events and not tail_events else start
        evidence_end=end+len(tail)
        quote=text[evidence_start:evidence_end]
        assertion='UNCERTAIN'
        if re.search(r'\bkhông\b|\bchưa\b', quote, re.I):
            assertion='NEGATED_OR_UNCERTAIN'
        elif re.search(r'\bnếu\b|\bsẽ\b|dự\s+kiến|đề\s+nghị', quote, re.I):
            assertion='CONDITIONAL_OR_PLANNED'
        dates=[]
        for m in DATE_PATTERN.finditer(quote):
            parts=m.groups()[:3] if m.group(1) else m.groups()[3:]
            try:
                d, mo, y=map(int,parts)
                value=date(y,mo,d).isoformat()
            except ValueError:
                value=None
            dates.append(dict(raw=m.group(), proposed_date=value,
                              start=evidence_start+m.start(), end=evidence_start+m.end(),
                              meaning='UNVERIFIED_NOT_AUTOMATIC_EFFECTIVE_DATE'))
        # No canonical person/company ID is minted by this stage.
        identity=[source['corpus_version_id'],source['index_version_id'],source['chunk_id'],start,end,role_start,stage]
        rid='review:'+hashlib.sha256(json.dumps(identity,ensure_ascii=False).encode()).hexdigest()
        items.append(dict(review_item_id=rid, review_status='PENDING', publish_allowed=False,
            person_raw=text[start:end], person_span=dict(start=start,end=end), person_canonical_id=None,
            position_raw=role.group(), position_code=POSITIONS[int(role.lastgroup[1:])][0],
            position_span=dict(start=role_start,end=role_end),
            proposed_stage=stage, assertion_status=assertion,
            event_cue=event.group() if event else None,
            event_attribution='NEEDS_ROW_AND_SENTENCE_REVIEW' if event else 'ROLE_LIST_ONLY',
            organization_context=source.get('locator_json',{}).get('symbol'),
            organization_canonical_id=None, organization_link_verified=False,
            date_mentions=dates,
            limitations=['NOT_A_CONTRACT_RELATION','ORGANIZATION_LINK_UNVERIFIED']+
                        (['MULTIPLE_POSITIONS_IN_WINDOW'] if len(roles)>1 else [])+
                        (['MULTIPLE_EVENTS_IN_WINDOW'] if len(tail_events)>1 else []),
            evidence=dict(document_id=source['document_id'],chunk_id=source['chunk_id'],
                          content_hash=source['content_hash'],page=source.get('page_number'),
                          locator=source.get('locator_json'),start=evidence_start,end=evidence_end,quote=quote)))
    return items


def review_source(text, source):
    """Keep each explicitly connected position as its own review candidate.

    A slash/kiêm is evidence of a shared person, not permission to attach the
    following company's title or to propagate a dismissal across positions.
    """
    from copy import deepcopy
    result=[]
    for first in _review_source_first(text, source):
        ev=first['evidence']
        positions=[(first['position_span']['start'],first['position_span']['end'],
                    first['position_raw'],first['position_code'])]
        cursor=positions[0][1]
        for match in ROLE.finditer(text,cursor,ev['end']):
            gap=text[cursor:match.start()]
            if not re.fullmatch(r'\s*(?:/|kiêm|và|–|-)\s*',gap,re.I):
                break
            positions.append((match.start(),match.end(),match.group(),POSITIONS[int(match.lastgroup[1:])][0]))
            cursor=match.end()
        for index,(start,end,raw,code) in enumerate(positions):
            item=deepcopy(first)
            item.update(position_raw=raw,position_code=code,position_span=dict(start=start,end=end))
            # Event cues belong to the adjacent position only. For a compound
            # title followed by one event, scope is ambiguous for earlier roles.
            limit=positions[index+1][0] if index+1<len(positions) else ev['end']
            suffix=text[end:limit]
            adjacent=[m for m in EVENT_PATTERN.finditer(suffix)
                      if re.fullmatch(r'[\s(,:\-–—]*',suffix[:m.start()])]
            if len(positions)>1:
                preceding=EVENT_PATTERN.search(text[ev['start']:first['person_span']['start']])
                item['proposed_stage']=EVENTS[int(adjacent[0].lastgroup[1:])][0] if adjacent else first['proposed_stage'] if preceding else 'ROLE_AT_SOURCE_TIME'
                item['event_cue']=adjacent[0].group() if adjacent else first['event_cue'] if preceding else None
                item['event_attribution']='NEEDS_ROW_AND_SENTENCE_REVIEW' if adjacent else 'ROLE_LIST_ONLY'
                item['date_mentions']=[d for d in first['date_mentions'] if end<=d['start']<limit]
                if any(EVENT_PATTERN.search(text[p[1]:ev['end']]) for p in positions):
                    item['limitations']=list(dict.fromkeys(item['limitations']+['COMPOUND_ROLE_EVENT_SCOPE_REQUIRES_REVIEW']))
            identity=[source['corpus_version_id'],source['index_version_id'],source['chunk_id'],
                      first['person_span'],start,end,item['proposed_stage']]
            item['review_item_id']='review:'+hashlib.sha256(json.dumps(identity,ensure_ascii=False,sort_keys=True).encode()).hexdigest()
            result.append(item)
    return result


def build_review_envelope(envelope, items, registry=None):
    """Package uncertain BCTN candidates for review, never as approved edges.

    Organization comes only from a mention in the document header and is marked
    unverified for this role. Person/entity IDs still come from WBS02 normalize.
    Nomination/resignation events remain in the worksheet, not coerced to a
    different contract relation type.
    """
    from copy import deepcopy
    from .contract.contracts import validate_envelope
    from .contract.entities import normalize
    from .extractor import scoped_registry
    validate_envelope(envelope)
    if any(envelope[k] for k in ('entities','mentions','relations')):
        raise ValueError('Review packaging requires unnormalized envelope')
    chunks={(c['document_id'],c['chunk_id']):c for c in envelope['chunks']}
    proposals=[]
    accepted=[]
    for item in items:
        if item['proposed_stage'] not in ('APPOINTED','DISMISSED','ROLE_AT_SOURCE_TIME'):
            continue
        ev=item['evidence'];chunk=chunks.get((ev['document_id'],ev['chunk_id']))
        if not chunk or hashlib.sha256(chunk['text'].encode()).hexdigest()!=ev['content_hash']:
            raise ValueError('Review item source mismatch')
        text=chunk['text'];ps=item['person_span'];rs=item['position_span']
        if (text[ps['start']:ps['end']]!=item['person_raw'] or
            text[rs['start']:rs['end']]!=item['position_raw'] or text[ev['start']:ev['end']]!=ev['quote']):
            raise ValueError('Review item spans mismatch')
        symbol=item.get('organization_context')
        header_end=chunk['locator'].get('text_start',0)
        matches=list(re.finditer(r'(?<!\w)'+re.escape(symbol)+r'(?!\w)',text[:header_end])) if symbol else []
        if len(matches)!=1:
            continue
        company_span=matches[0].span()
        for kind,span in [('Person',(ps['start'],ps['end'])),('Company',company_span)]:
            proposals.append(dict(document_id=chunk['document_id'],chunk_id=chunk['chunk_id'],
                                  entity_type=kind,start=span[0],end=span[1]))
        accepted.append((item,company_span))
    safe_registry,excluded=scoped_registry(registry)
    result=deepcopy(envelope)
    result.update(normalize(result['chunks'],safe_registry,proposals))
    relations={}
    for item,company_span in accepted:
        ev=item['evidence'];ps=item['person_span']
        def mentioned(span,kind):
            es={e['entity_id']:e for e in result['entities']}
            found=[m for m in result['mentions'] if m['document_id']==ev['document_id'] and m['chunk_id']==ev['chunk_id']
                   and (m['start'],m['end'])==span and es[m['entity_id']]['entity_type']==kind]
            if len(found)!=1:raise ValueError('Review mention not unique')
            return found[0]
        person=mentioned((ps['start'],ps['end']),'Person');company=mentioned(company_span,'Company')
        kind={'APPOINTED':'APPOINTS','DISMISSED':'DISMISSES','ROLE_AT_SOURCE_TIME':'HOLDS_ROLE'}[item['proposed_stage']]
        subject,target=(person,company) if kind=='HOLDS_ROLE' else (company,person)
        rid='rel:'+hashlib.sha256(json.dumps([envelope['corpus_id'],envelope['dataset_version'],item['review_item_id']],ensure_ascii=False).encode()).hexdigest()
        relations[rid]=dict(relation_id=rid,relation_type=kind,subject_id=subject['entity_id'],object_id=target['entity_id'],
            attributes=dict(position=item['position_raw'],position_code=item['position_code'],assertion_status='UNCERTAIN',
                proposed_stage=item['proposed_stage'],organization_link_verified=False,
                organization_basis='DOCUMENT_HEADER_CONTEXT_ONLY_REQUIRES_REVIEW',
                person_mention_id=person['mention_id'],company_mention_id=company['mention_id'],
                review_item_id=item['review_item_id'],limitations=item['limitations'],
                date_mentions=item['date_mentions'],evidence_start=ev['start'],evidence_end=ev['end']),
            temporal=dict(as_of=None,valid_from=None,valid_to=None),
            evidence=[dict(document_id=ev['document_id'],chunk_id=ev['chunk_id'],quote=ev['quote'])],
            review=dict(status='PENDING',reviewer=None,reviewed_at=None))
    result['relations']=[relations[k] for k in sorted(relations)]
    # The upstream resolver also emits automatic Person proposals in addition
    # to our precise spans. Exclude its title-swallowing/glued proposals before
    # export so repaired files are not re-contaminated on the next run.
    from .name_repair import repair_person_names
    proposed_names=sorted({c['text'][s:e] for c in result['chunks'] for s,e in names(c['text'])})
    result,name_audit=repair_person_names(result,proposed_names)
    validate_envelope(result)
    return result,dict(registry_aliases_excluded=excluded,review_only_candidates=len(relations),
                       name_span_cleanup=name_audit,publish_allowed=False)
