"""Deterministic person/position extraction. Standard library only; no AI calls.

Input is crawler text or explicit table rows, not PDF pixels. Ambiguous layout
and identity stay in quarantine. Rule matches are not human-approved facts.
"""
import hashlib
import json
import re
from datetime import date

VERSION='person-role-rules-v1'
ROLES=[
 ('DEPUTY_BOARD_CHAIR',r'phó\s+chủ\s+tịch(?:\s+thứ\s+nhất)?\s+(?:hđqt|hội\s+đồng\s+quản\s+trị)'),
 ('BOARD_CHAIR',r'chủ\s+tịch\s+(?:hđqt|hội\s+đồng\s+quản\s+trị)'),
 ('BOARD_MEMBER',r'(?:thành\s+viên|ủy\s+viên|uỷ\s+viên|tv)\s+(?:độc\s+lập\s+)?(?:hđqt|hội\s+đồng\s+quản\s+trị)(?:\s+độc\s+lập)?'),
 ('DEPUTY_SUPERVISORY_HEAD',r'phó\s+trưởng\s+(?:ban\s+kiểm\s+soát|bks)'),
 ('SUPERVISORY_HEAD',r'trưởng\s+(?:ban\s+kiểm\s+soát|bks)'),
 ('SUPERVISORY_MEMBER',r'(?:thành\s+viên|tv)\s+(?:chuyên\s+trách\s+)?(?:ban\s+kiểm\s+soát|bks)'),
 ('DEPUTY_CEO',r'phó\s+(?:tổng\s+giám\s+đốc|tgđ|tgd)'),
 ('CEO',r'tổng\s+giám\s+đốc|\btgđ\b|\btgd\b'),
 ('CHIEF_ACCOUNTANT',r'kế\s+toán\s+trưởng'),
 ('CFO',r'giám\s+đốc\s+tài\s+chính(?:\s+tập\s+đoàn)?'),
 ('AUDIT_CHAIR',r'chủ\s+tịch\s+ủy\s+ban\s+kiểm\s+toán'),
 ('AUDIT_MEMBER',r'thành\s+viên\s+ủy\s+ban\s+kiểm\s+toán'),
 ('EXECUTIVE_MEMBER',r'thành\s+viên\s+ban\s+điều\s+hành'),
]
ROLE=re.compile('|'.join(f'(?P<R{i}>{p})' for i,(_,p) in enumerate(ROLES)),re.I)
HONORIFIC=re.compile(r'\b(?:ông|bà)\s+',re.I)
WORD=re.compile(r'[^\W\d_]+(?:[-’\'][^\W\d_]+)*',re.UNICODE)
STOP={'chủ','phó','tổng','giám','kế','thành','ủy','uỷ','trưởng','ông','bà','công','ngân','được','giữ','là','tv','hđqt','tgđ','tgd'}
EVENTS=[('RESIGNATION_REQUESTED',r'xin\s+từ\s+nhiệm|đơn\s+(?:xin\s+)?từ\s+nhiệm'),
 ('NOMINATED',r'đề\s+cử|ứng\s+cử'),('DISMISSED',r'miễn\s+nhiệm|bãi\s+nhiệm'),
 ('RESIGNED',r'từ\s+nhiệm|từ\s+chức'),('APPOINTED',r'bổ\s+nhiệm|được\s+bầu')]
DATE=re.compile(r'\b(\d{1,2})[/.\-](\d{1,2})[/.\-](\d{4})\b|\b(\d{1,2})\s+tháng\s+(\d{1,2})\s+năm\s+(\d{4})\b',re.I)
TABLE_HEADING=re.compile(r'danh\s+sách|hội\s+đồng\s+quản\s+trị|hđqt|ban\s+kiểm\s+soát|ban\s+điều\s+hành|ban\s+tổng\s+giám\s+đốc|kế\s+toán\s+trưởng|thu\s+nhập|thù\s+lao|thành\s+viên\s+và\s+cơ\s+cấu',re.I)

def sha(text):return hashlib.sha256(text.encode('utf-8')).hexdigest()
def stable(value):return sha(json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':')))
def name_spans(text):
    found=[]
    for h in HONORIFIC.finditer(text):
        words=[];end=h.end()
        for w in WORD.finditer(text,h.end()):
            token=w.group()
            if text[end:w.start()].strip() or not token[0].isupper() or token.casefold() in STOP:break
            words.append(w);end=w.end()
            if len(words)>8:break
        if 2<=len(words)<=8:found.append((words[0].start(),words[-1].end()))
    return found

def dates(text,offset):
    result=[]
    for m in DATE.finditer(text):
        parts=m.groups()[:3] if m.group(1) else m.groups()[3:]
        try:d=date(*reversed(tuple(map(int,parts)))).isoformat()
        except ValueError:d=None
        prefix=text[max(0,m.start()-55):m.start()]
        meaning='EFFECTIVE' if re.search(r'(?:hiệu\s+lực\s+)?(?:kể\s+)?từ\s+(?:ngày\s+)?$',prefix,re.I) else 'MENTIONED_DATE'
        if re.search(r'quyết\s+định|nghị\s+quyết',prefix,re.I) and not re.search(r'hiệu\s+lực|kể\s+từ',prefix,re.I):meaning='DECISION_DATE'
        result.append(dict(raw=m.group(),value=d,meaning=meaning,start=offset+m.start(),end=offset+m.end()))
    return result

def extract_record(record,*,symbol=None,source_kind=None,source_url=None):
    """Returns rule candidates plus quarantine, with offsets on unchanged text.

    Structured rows: text is exactly ``person + ' | ' + position + ' | ' + event``.
    Use organization_verified=true only when the crawler has already identified
    the row's company (not merely a ticker mentioned somewhere in the article).
    """
    symbol=record.get('symbol') or symbol
    kind=record.get('source_kind') or source_kind or 'unknown'
    url=record.get('source_url') or record.get('url') or source_url
    structured=bool(record.get('person') and record.get('position'))
    text=(' | '.join([record['person'],record['position'],record.get('event','')]) if structured else
          record.get('text_clean',record.get('text',record.get('content',''))))
    if not isinstance(text,str):raise ValueError('Expected text string')
    digest=sha(text)
    expected_hash=record.get('content_hash') or record.get('clean_text_sha256')
    if expected_hash and expected_hash!=digest:raise ValueError('Input content_hash mismatch')
    page=record.get('page',record.get('page_number'))
    if page is not None and (type(page) is not int or page<1):raise ValueError('Physical PDF page must be positive or absent')
    sourceid=str(record.get('document_id') or record.get('source_id') or record.get('source_pdf_sha256') or url or digest)
    base=dict(pipeline_version=VERSION,document_id=sourceid,source_url=url,source_kind=kind,
              pdf_page=page,content_hash=digest,pdf_sha256=record.get('source_pdf_sha256'),reporting_year=record.get('reporting_year'),published_at=record.get('published_at'))
    output=[];quarantine=[]
    def reject(reason,start,end):
        quarantine.append(dict(**base,reason=reason,start=start,end=end,quote=text[start:end]))
    if record.get('layout_uncertain') or any('READING_ORDER' in str(flag) or 'COLUMN' in str(flag) for flag in record.get('blocked_reasons',[])):
        reject('UNRESOLVED_LAYOUT',0,len(text));return dict(candidates=[],quarantine=quarantine)
    units=[(0,len(text))] if structured else [(m.start(),m.end()) for m in re.finditer(r'[^\n;]+',text)]
    if structured and not ROLE.search(record['position']):
        reject('UNSUPPORTED_POSITION',0,len(text));return dict(candidates=[],quarantine=quarantine)
    for start,end in units:
        quote=text[start:end];matches=list(ROLE.finditer(quote))
        if not matches:continue
        if structured:
            person=record['person'].strip();ps=len(record['person'])-len(record['person'].lstrip());pe=ps+len(person)
            if not re.fullmatch(r'[^\W\d_]+(?:[-’\'][^\W\d_]+)*(?:\s+[^\W\d_]+(?:[-’\'][^\W\d_]+)*){1,7}',person):
                reject('INVALID_STRUCTURED_NAME',start,end);continue
            if any(token.casefold() in STOP for token in person.split()):
                reject('TITLE_OR_HONORIFIC_INSIDE_STRUCTURED_NAME',start,end);continue
        else:
            people=name_spans(quote)
            if len(people)!=1:
                reject('NO_UNIQUE_PERSON_IN_ROW',start,end);continue
            ps,pe=people[0];person=quote[ps:pe]
        if not symbol:
            reject('MISSING_COMPANY',start,end);continue
        # A configured issuer is enough only for annual-report tables/rows.
        # For news, a crawler must supply a checked per-row organization or an
        # explicit company alias in this same sentence. Other company forms are
        # conservatively rejected rather than assigned the article's ticker.
        aliases=record.get('company_aliases',[])+[symbol]
        explicit=any(re.search(r'(?<!\w)'+re.escape(a)+r'(?!\w)',quote,re.I) for a in aliases if a)
        table=kind=='annual_report' and (structured or bool(TABLE_HEADING.search(text[max(0,start-300):end])))
        checked=record.get('organization_verified') is True
        if kind=='annual_report' and not checked and re.search(r'công\s+ty|ngân\s+hàng|tập\s+đoàn',quote,re.I):
            reject('ROW_CONTAINS_ORGANIZATION_REQUIRES_EXPLICIT_ROW_BINDING',start,end);continue
        if kind!='annual_report' and not checked:
            if not explicit or re.search(r'công\s+ty|ngân\s+hàng|tập\s+đoàn',quote,re.I):
                reject('NEWS_COMPANY_ATTRIBUTION_REQUIRES_STRUCTURED_ROW',start,end);continue
        if not (explicit or table or checked):
            reject('COMPANY_CONTEXT_UNVERIFIED',start,end);continue
        if not structured and (matches[0].start()<pe or len(quote[pe:matches[0].start()])>45):
            reject('PERSON_ROLE_ALIGNMENT_UNCERTAIN',start,end);continue
        if not structured and re.search(r'\d',quote[pe:matches[0].start()]):
            reject('DATE_OR_NUMBERS_BETWEEN_PERSON_AND_ROLE',start,end);continue
        if len(matches)>1 and any(not re.fullmatch(r'\s*(?:/|kiêm|và|\|)\s*',quote[a.end():b.start()],re.I) for a,b in zip(matches,matches[1:])):
            reject('NON_ADJACENT_ROLES_OR_MIXED_TABLE',start,end);continue
        if re.search(r'\bkhông\b|\bchưa\b|\bnếu\b|dự\s+kiến|\bsẽ\b',quote,re.I):
            reject('NEGATED_OR_CONDITIONAL',start,end);continue
        if re.search(r'từng\s+giữ|trước\s+đây|quá\s+trình\s+công\s+tác',quote,re.I):
            reject('HISTORICAL_BIOGRAPHY_REQUIRES_TIMELINE',start,end);continue
        events=[(stage,m) for stage,pattern in EVENTS if (m:=re.search(pattern,quote,re.I))]
        if any(stage=='RESIGNATION_REQUESTED' for stage,m in events):events=[e for e in events if e[0]!='RESIGNED']
        if len(events)>1:
            reject('MULTIPLE_EVENTS_IN_ROW',start,end);continue
        if len(matches)>1 and events:
            reject('COMPOUND_ROLE_EVENT_SCOPE_UNCLEAR',start,end);continue
        stage=events[0][0] if events else 'ROLE_AT_SOURCE_TIME'
        mentions=dates(quote,start)
        effective=[d['value'] for d in mentions if d['meaning']=='EFFECTIVE' and d['value']]
        if len(set(effective))>1 or any(d['value'] is None for d in mentions):
            reject('INVALID_OR_AMBIGUOUS_DATE',start,end);continue
        if record.get('as_of'):
            asof=date.fromisoformat(record['as_of'])
            if stage=='APPOINTED' and effective and date.fromisoformat(effective[0])>asof:stage='APPOINTED_FUTURE'
        relation={'APPOINTED':'APPOINTS','APPOINTED_FUTURE':'APPOINTS','DISMISSED':'DISMISSES',
                  'RESIGNED':'RESIGNS','RESIGNATION_REQUESTED':'REQUESTS_RESIGNATION','NOMINATED':'NOMINATED',
                  'ROLE_AT_SOURCE_TIME':'HOLDS_ROLE'}[stage]
        for m in matches:
            role=m.group();code=ROLES[int(m.lastgroup[1:])][0]
            identity=[VERSION,sourceid,page,digest,start+ps,start+m.start(),symbol,code,stage]
            output.append(dict(**base,candidate_id='rule:'+stable(identity),name=person,
                name_span=dict(start=start+ps,end=start+pe),position_raw=role,position_code=code,
                position_span=dict(start=start+m.start(),end=start+m.end()),symbol=symbol,stage=stage,
                relation_type=relation,subject=symbol if relation in ('APPOINTS','DISMISSES') else person,
                object=person if relation in ('APPOINTS','DISMISSES') else symbol,
                date_mentions=mentions,effective_date=effective[0] if effective else None,
                organization_basis='CRAWLER_VERIFIED_ROW' if checked else 'ISSUER_TABLE_CONTEXT' if table else 'EXPLICIT_ALIAS_IN_SENTENCE',
                validation_status='RULE_MATCHED',review_status='PENDING',current_employment_confirmed=False,
                evidence=dict(start=start,end=end,quote=quote),source_text=text))
    return dict(candidates=output,quarantine=quarantine)
