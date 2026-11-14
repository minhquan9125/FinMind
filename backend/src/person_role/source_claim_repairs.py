"""Repair source evidence without manufacturing quotes, identities or dates.

These are document-scoped claims. A report edition is not an effective date,
and a source occurrence is not a globally resolved person identity.
"""
import re,unicodedata
from .contract.entities import text_view
from .evidence_spans import person_spans
from ..graph_review.positions import role_key,position_supported

def role_normal(text):
    value=role_key(text)
    value=value.replace('/n',' ')
    value=re.sub(r'\b(?:ủy|uỷ) viên\b','thành viên',value)
    value=re.sub(r'thành viên độc lập hội đồng quản trị','thành viên hội đồng quản trị độc lập',value)
    return value

def role_present(position,text):
    return position_supported(role_normal(position),role_normal(text))

def joined_sources(sources):
    parts=[];segments=[];cursor=0
    for source in sources:
        text=source['text'];_,sep,body=text.partition('\n')
        header_len=len(text)-len(body) if sep else 0
        if not sep:body=text
        parts.append(body);segments.append((cursor,cursor+len(body),header_len,source))
        cursor+=len(body)+1
    return '\n'.join(parts),segments

def exact_refs(segments,start,end):
    output=[]
    for left,right,header,source in segments:
        lo,hi=max(left,start),min(right,end)
        if lo>=hi:continue
        a,b=lo-left+header,hi-left+header
        output.append({k:v for k,v in source.items() if k!='text'}|dict(quote=source['text'][a:b],quote_start=a,quote_end=b))
    return output

def headings(text,known_names):
    patterns=[('board',r'hội\s+đồng\s+quản\s+trị|\bhđqt\b'),
        ('supervisory',r'ban\s+kiểm\s+soát'),('audit',r'ủy\s+ban\s+kiểm\s+toán'),
        ('executive',r'ban\s+(?:tổng\s+giám\s+đốc|điều\s+hành)')]
    result=[]
    for line in re.finditer(r'[^\n]+',text):
        value=line.group().casefold()
        if any(n.casefold() in value for n in known_names):continue
        found=[kind for kind,pattern in patterns if re.search(pattern,value)]
        if len(found)==1:result.append((line.start(),line.end(),found[0]))
    return result

def short_role(position):
    key=role_normal(position)
    for section,label in [('board','hội đồng quản trị'),('supervisory','ban kiểm soát'),('audit','ủy ban kiểm toán')]:
        if label in key:
            short=key.replace(label,'').strip()
            if short=='trưởng':short='trưởng ban'
            return section,short
    return None,None

def stage_supported(kind,quote):
    cues={'APPOINTS':r'bổ nhiệm|bồ nhiệm|kiêm nhiệm[^.]{0,90}từ ngày','DISMISSES':r'miễn nhiệm|bãi nhiệm',
        'RESIGNS':r'từ nhiệm','REQUESTS_RESIGNATION':r'xin từ nhiệm|đơn.*từ nhiệm',
        'FORMER_ROLE':r'nguyên|từng|trước đây'}
    return kind=='HOLDS_ROLE' or bool(re.search(cues.get(kind,r'(?!)'),quote,re.I))

def repair_claim(record,known_names):
    name=record['object'] if record['relation_type'] in ('APPOINTS','DISMISSES') else record['subject']
    text,segments=joined_sources(record['live_verified_chunks'])
    hs=headings(text,known_names);options=[]
    spans=person_spans(text,name,known_names)
    # Biographical role/date statements can follow "Kinh nghiệm". Retain the
    # person's own profile, but stop before another reviewed person or honorific.
    view,offsets=text_view(text);target=text_view(name)[0]
    other_hits=[]
    for other in known_names:
        if other==name:continue
        for hit in re.finditer(r'(?<!\w)'+re.escape(text_view(other)[0])+r'(?!\w)',view):other_hits.append(offsets[hit.start()][0])
    for hit in re.finditer(r'(?<!\w)'+re.escape(target)+r'(?!\w)',view):
        at=offsets[hit.start()][0];start=text.rfind('\n',0,at)+1
        stop=min([x for x in other_hits if x>at]+[len(text),at+1800])
        spans.append(dict(start=start,end=stop,quote=text[start:stop]))
    for span in spans:
        quote=span['quote'];basis=None;extra=[];notes=[]
        if role_present(record['position'],quote):basis='EXACT_ROLE_OR_EXPLICIT_ABBREVIATION'
        wanted,short=short_role(record['position'])
        if not basis and wanted and short and role_present(short,quote):
            # The heading must precede THIS row, and no later competing section
            # heading may intervene. Each heading/row remains its own exact ref.
            name_at=text.find(name,span['start'],span['end'])
            preceding=[h for h in hs if h[0]<name_at]
            if preceding and preceding[-1][2]==wanted:
                header=preceding[-1];basis='TABLE_HEADING_AND_EXACT_PERSON_ROW';extra=[header[:2]]
        xid=record['extraction_id']
        split_fields={
            '19bfbc1d-2edc-5c2f-b396-1f0383eb4eee':('GĐ Khối Tài','chính'),
            '1b8ceb86-4745-5230-8a21-3c76759b842c':('kiêm GĐ','VietinBank TP. Hồ Chí Minh'),
            'b2569eb8-0f6f-5e6d-832a-5577327e44fd':('kiêm GĐ','VietinBank TP. Hà Nội'),
        }
        if not basis and xid in split_fields and all(part.casefold() in quote.casefold() for part in split_fields[xid]):
            basis='REVIEWED_WRAPPED_TABLE_CELL';notes=['Role fragments retained around the exact named table row; source numbers and name were not deleted or reordered.']
        if not basis and xid=='8d72e87f-1525-5009-b869-e3ab01c3e165' and 'thành viên hội đồng quản trị không' in role_normal(quote) and 'điêu hành' in quote:
            basis='REVIEWED_OCR_ROLE_FIELD';notes=['Source OCR says điêu hành; source review identifies the standard role không điều hành. Original text and hash remain unchanged.']
        corrected_position=record['position']
        title_only={
            '7e6891e8-7d40-5f80-a41d-c028b4a8aebf':'Thành viên độc lập',
            '8fd0c336-c9a6-5ac4-9cb5-9d38aa3851d4':'Thành viên độc lập',
            'b464e72a-2eaf-5625-90a4-6502e7ec44be':'Phó Chủ tịch',
        }
        if not basis and xid in title_only and role_present(title_only[xid],quote):
            corrected_position=title_only[xid];basis='SOURCE_TITLE_WITHOUT_UNSTATED_BOARD_QUALIFIER'
            notes=['Original normalized title retained in lineage; board qualifier omitted from the new claim because it is absent from this exact source profile title.']
        if basis:
            score=(20 if stage_supported(record['relation_type'],quote) else 0)+(10 if basis=='EXACT_ROLE_OR_EXPLICIT_ABBREVIATION' else 0)-len(quote)/10000
            options.append((score,span,extra,basis,notes,corrected_position))
    if not options:
        return dict(origin_extraction_id=record['extraction_id'],person_name=name,company=record['symbol'],
            relation_type=record['relation_type'],position=record['position'],excluded=False,
            repair_status='NEEDS_TARGET_ROW_OR_SECTION_CONTEXT',evidence=[])
    _,span,extra,basis,notes,corrected_position=max(options,key=lambda x:x[0])
    refs=exact_refs(segments,span['start'],span['end'])
    for a,b in extra:refs+=exact_refs(segments,a,b)
    stage_ok=stage_supported(record['relation_type'],span['quote'])
    corrected_kind=record['relation_type']
    if not stage_ok and record['extraction_id']=='cbe764cd-eff1-5111-ab43-cd188f998f67':
        corrected_kind='HOLDS_ROLE';stage_ok=True
        notes+=['The source roster proves the office, not an appointment event; APPOINTS corrected to HOLDS_ROLE without discarding the original record.']
    return dict(origin_extraction_id=record['extraction_id'],person_name=name,company=record['symbol'],
        relation_type=corrected_kind,position=corrected_position,excluded=False,
        original_relation_type=record['relation_type'],original_position=record['position'],
        repair_status='SOURCE_FIELDS_REPAIRED' if stage_ok else 'NEEDS_EVENT_STAGE_CONTEXT',
        evidence_basis=basis,repair_notes=notes,source_report_year=record['report_year'],
        source_url=record['source_url'],evidence=refs,
        identity_scope='EXACT_SOURCE_OCCURRENCE_NOT_GLOBAL_PERSON',
        time_scope='SOURCE_DOCUMENT_CONTEXT_NOT_CURRENT_OFFICE',
        report_review_body_sha256=record['review_body_sha256'])
