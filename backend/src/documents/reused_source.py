"""Rebuild financial sources from existing clean payloads plus versioned metadata."""
import json
from dataclasses import replace
from decimal import Decimal

from .db_chunking import SourceDocument,SourceSection,SourceRow,format_value
from .chunk_reconstruction import ReconstructionError,reconstruct_document_chunk
from .corpus_manifest import sha256
from ..financial.exact_json import loads,dumps
import hashlib
from datetime import datetime
import uuid


def semantic_hash(payload):
    return hashlib.sha256(dumps(payload).encode('utf-8')).hexdigest()


def financial_recipe(document,rows,approved):
    """Only labels/headers/unit rules/IDs; no numeric source values or chunk text."""
    by_obs={str(r['observation_id']):r for r in rows};sections={}
    for chunk in document['chunks']:
        loc=chunk['locator'];meta=loc['reconstruction'];header,_,body=chunk['text'].partition('\n')
        lines=body.split('\n')
        if len(lines)!=len(loc['row_keys']):raise ValueError('MULTILINE_FINANCIAL_REVIEW_REQUIRED')
        section=sections.setdefault(meta['section_index'],dict(label=loc['section'],header=header,rows=[]))
        for key,line in zip(loc['row_keys'],lines):
            row=by_obs[key];code=row['code'];marker=f' ({code}): '
            if marker not in line:raise ValueError('METRIC_LABEL_PARSE_FAILED')
            name=line.split(marker,1)[0]
            decision=approved.get((row['symbol'],row['period_code'],row['section'].lower(),code))
            section['rows'].append(dict(observation_id=key,code=code,name=name,
                clean_section=row['locator_json']['source_section'],source_field=row['locator_json']['source_field'],
                unit=decision['unit'] if decision else row['unit'],
                mapping_status=decision['status'] if decision else 'UNVERIFIED',
                mapping_rule_id=decision.get('mapping_rule_id') if decision else None))
    first=rows[0]
    return dict(schema_version='clean-payload-render-recipe-v1',source_table='financial_reports',
        source_id=document['source_id'],symbol=first['symbol'],period_code=first['period_code'],
        renderer='db-financial-v4',sections=[sections[k] for k in sorted(sections)])


def render_clean(payload,recipe):
    if payload['mã_chứng_khoán']!=recipe['symbol']:
        raise ReconstructionError('SOURCE_MISMATCH','Clean payload company differs')
    from_sections={'balance_sheet':'bảng_cân_đối_kế_toán','income_statement':'kết_quả_kinh_doanh',
                   'cash_flow_statement':'lưu_chuyển_tiền_tệ','ratios':'chỉ_số_tài_chính'}
    # Use payload's actual section names; explicit mapping must match cleaner schema.
    values={}
    for section,name in from_sections.items():
        for report in payload['báo_cáo_tài_chính'].get(name,[]):
            if report['kỳ_báo_cáo']!=recipe['period_code']:continue
            for metric in report['chỉ_tiêu']:
                key=(section,metric['trường_gốc'],metric['mã_chuẩn'])
                if key in values:raise ReconstructionError('SOURCE_CHANGED','Duplicate source metric')
                values[key]=metric['giá_trị']
    sections=[]
    for section in recipe['sections']:
        rows=[]
        for row in section['rows']:
            key=(row['clean_section'],row['source_field'],row['code'])
            if key not in values:raise ReconstructionError('SOURCE_MISSING','Metric missing from original payload')
            value=Decimal(str(values[key]))
            if not value.is_finite():raise ReconstructionError('SOURCE_CHANGED','Nonfinite source value')
            rows.append(SourceRow(row['observation_id'],f"{row['name']} ({row['code']}): {format_value(value,row['unit'])}"))
        sections.append(SourceSection(section['label'],section['header'],rows))
    return SourceDocument(source_table='financial_reports',source_id=recipe['source_id'],
        doc_type='FINANCIAL_STATEMENT',title='Versioned clean report',symbol=recipe['symbol'],language='vi',
        sections=sections,meta={'chunker_version':recipe['renderer'],'period_code':recipe['period_code']})


def restore_structure(live,recipe):
    """Pin section order and membership; never copy frozen numeric/body values."""
    sections=[]
    for saved in recipe['sections']:
        matches=[s for s in live.sections if s.label==saved['label']]
        if len(matches)!=1:raise ReconstructionError('SOURCE_CHANGED','Source section absent or ambiguous')
        now={r.key:r for r in matches[0].rows}
        if any(k not in now for k in saved['row_keys']):raise ReconstructionError('SOURCE_MISSING','Source row absent')
        sections.append(SourceSection(saved['label'],saved['header'],[now[k] for k in saved['row_keys']]))
    return replace(live,sections=sections)


def structure_recipe(document):
    groups={}
    for chunk in document['chunks']:
        loc=chunk['locator'];i=loc['reconstruction']['section_index']
        sec=groups.setdefault(i,dict(label=loc['section'],header=chunk['text'].split('\n',1)[0],row_keys=[]))
        sec['row_keys'].extend(loc['row_keys'])
    return dict(sections=[groups[k] for k in sorted(groups)])


async def read_pinned_payload(conn,binding):
    rows=await conn.fetch('SELECT payload_id::text,sha256,payload FROM public.raw_payloads WHERE payload_id=$1',
                          __import__('uuid').UUID(binding['payload_id']))
    if len(rows)!=1:raise ReconstructionError('SOURCE_MISSING','Historical raw payload missing')
    row=rows[0];payload=loads(row['payload']) if isinstance(row['payload'],str) else row['payload']
    if row['sha256'].strip()!=binding['stored_sha256'] or semantic_hash(payload)!=binding['semantic_sha256']:
        raise ReconstructionError('SOURCE_CHANGED','Historical payload was modified')
    return payload


def render_news(payload,recipe):
    from .db_chunking import news_documents
    articles=payload if isinstance(payload,list) else payload.get('articles',[])
    matches=[a for a in articles if a.get('url')==recipe['url']]
    if len(matches)!=1:raise ReconstructionError('SOURCE_CHANGED','Historical article absent or ambiguous')
    article=matches[0];published=recipe.get('published_at',article.get('published_at'))
    if published:published=datetime.fromisoformat(published.replace('Z','+00:00'))
    docs=news_documents([dict(article_id=recipe['source_id'],source=recipe['source'],
        title=recipe.get('title',article['title']),content=article.get('content'),published_at=published,
        symbols=recipe['symbols'],url=recipe['url'])],max_words=130)
    if len(docs)!=1:raise ReconstructionError('SOURCE_MISSING','Historical article has no content')
    return docs[0]


def render_bars(payload,recipe):
    from .db_chunking import price_documents,index_documents
    ns=uuid.UUID('b77dbd7f-5d89-479d-90a3-421e5f0981ea');rows=[]
    bars=payload if isinstance(payload,list) else payload['bars']
    for bar in bars:
        day=str(bar.get('trade_date',bar.get('date')))[:10]
        if day not in recipe['dates']:continue
        is_index=recipe['source_table']=='market_index_bars'
        key=f'{recipe["symbol"]}:{day}' if is_index else str(uuid.uuid5(ns,f'price:{recipe["symbol"]}:{day}:False'))
        ind=recipe['indicators'].get(key,{})
        row=dict(trade_date=day,**{k:bar[k] for k in ('open','high','low','close','volume')},
            **{k:None if ind.get(k) is None else Decimal(str(ind[k])) for k in ('sma20','sma50','rsi14')})
        if is_index:row.update(index_symbol=recipe['symbol'],index_name=recipe['company_name'])
        else:row.update(symbol=recipe['symbol'],company_name=recipe['company_name'],price_id=key,price_scale=1000)
        rows.append(row)
    if len(rows)!=len(set(recipe['dates'])):raise ReconstructionError('SOURCE_CHANGED','Historical bar membership differs')
    docs=(index_documents if recipe['source_table']=='market_index_bars' else price_documents)(rows)
    if len(docs)!=1:raise ReconstructionError('SOURCE_MISSING','No historical bar source')
    return docs[0]


def expand_financial_recipe(recipe,definitions,payload):
    recipe=json.loads(json.dumps(recipe));industry=payload['ngành']
    ns=uuid.UUID('b77dbd7f-5d89-479d-90a3-421e5f0981ea')
    section_codes={'balance_sheet':'BALANCE_SHEET','income_statement':'INCOME_STATEMENT',
                   'cash_flow_statement':'CASH_FLOW','ratios':'RATIO'}
    for section in recipe['sections']:
        expanded=[]
        for key in section['row_definitions']:
            row=dict(definitions[key]);part=section_codes[row['clean_section']]
            metric=uuid.uuid5(ns,f'metric:{industry}:{part}:{row["code"]}')
            row['observation_id']=str(uuid.uuid5(ns,f'observation:{recipe["source_id"]}:{metric}'))
            expanded.append(row)
        section['rows']=expanded
    return recipe


def render_profile(recipe):
    from .db_chunking import company_documents
    docs=company_documents([recipe['fields']])
    if len(docs)!=1:raise ReconstructionError('SOURCE_MISSING','Profile version missing')
    return docs[0]
