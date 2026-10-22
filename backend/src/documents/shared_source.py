"""Versioned normalized sources in existing raw_payloads; SELECT-only runtime."""
import hashlib
import json
import uuid

from .corpus_manifest import sha256
from .chunk_reconstruction import ReconstructionError,_metadata

NS=uuid.UUID('b77dbd7f-5d89-479d-90a3-421e5f0981ea')


def identity(uri,digest):
    return str(uuid.uuid5(NS,f'shared-source:{uri}:{digest}'))


def envelope(uri,payload):
    digest=sha256(payload)
    return dict(payload_id=identity(uri,digest),source_uri=uri,sha256=digest,payload=payload)


def normalize_document(document,index_id):
    """Collapse repeated chunk headers into source sections. Keep locators, not chunk text."""
    sections={};locators=[]
    for chunk in sorted(document['chunks'],key=lambda c:c['chunk_index']):
        loc,meta=_metadata(chunk['locator'])
        if loc['source_table']!=document['source_table'] or loc['source_id']!=document['source_id']:
            raise ValueError('SOURCE_IDENTITY_MISMATCH')
        header,sep,body=chunk['text'].partition('\n')
        if not sep:raise ValueError('SECTION_HEADER_MISSING')
        if hashlib.sha256(chunk['text'].encode()).hexdigest()!=chunk['content_hash']:
            raise ValueError('CHUNK_HASH_MISMATCH')
        section=sections.setdefault(meta['section_index'],dict(section_index=meta['section_index'],
            label=loc['section'],header=header,body='',source_view_sha256=meta['source_view_sha256']))
        if section['header']!=header or section['source_view_sha256']!=meta['source_view_sha256']:
            raise ValueError('SECTION_VERSION_MISMATCH')
        if meta['char_start']!=len(section['body']) or meta['char_end']-meta['char_start']!=len(body):
            raise ValueError('SECTION_SPAN_MISMATCH')
        section['body']+=body+'\n'
        locators.append(loc)
    for section in sections.values():section['body']=section['body'][:-1]
    return dict(schema_version='finmind-normalized-source-v1',index_version_id=str(index_id),
        source_table=document['source_table'],source_id=document['source_id'],
        document_id=document['document_id'],sections=list(sections.values()),locators=locators)


def resolve_source(payload,locator,expected_hash):
    loc,meta=_metadata(locator)
    if payload.get('schema_version')!='finmind-normalized-source-v1':raise ValueError('INVALID_SOURCE_SCHEMA')
    if (payload['source_table'],payload['source_id'],payload['document_id'])!=(loc['source_table'],loc['source_id'],meta['document_id']):
        raise ReconstructionError('SOURCE_MISMATCH','Versioned source identity differs')
    matches=[saved for saved in payload['locators'] if saved==loc]
    if len(matches)!=1:raise ReconstructionError('SOURCE_CHANGED','Locator does not belong to this source version')
    sections=[s for s in payload['sections'] if s['section_index']==meta['section_index']]
    if len(sections)!=1:raise ReconstructionError('SOURCE_CHANGED','Missing source section')
    section=sections[0]
    if section['source_view_sha256']!=meta['source_view_sha256']:
        raise ReconstructionError('SOURCE_CHANGED','Source section version differs')
    if not 0<=meta['char_start']<=meta['char_end']<=len(section['body']):
        raise ReconstructionError('INVALID_LOCATOR','Source character span is invalid')
    body=section['body'][meta['char_start']:meta['char_end']]
    text=section['header']+'\n'+body
    if meta['content_hash']!=expected_hash.strip() or hashlib.sha256(text.encode()).hexdigest()!=expected_hash.strip():
        raise ReconstructionError('HASH_MISMATCH','Shared source differs from indexed text')
    return text


async def read_envelope(conn,uri,expected=None):
    rows=await conn.fetch('SELECT payload_id::text,source_uri,sha256,payload FROM public.raw_payloads WHERE source_uri=$1',uri)
    if len(rows)!=1:raise ReconstructionError('SHARED_SOURCE_MISSING','Expected one immutable shared source')
    row=dict(rows[0]);payload=json.loads(row['payload']) if isinstance(row['payload'],str) else row['payload']
    digest=sha256(payload)
    if row['sha256'].strip()!=digest or row['payload_id']!=identity(uri,digest):
        raise ReconstructionError('SHARED_SOURCE_CORRUPTED','Shared payload checksum/identity mismatch')
    if expected and any(row[k]!=expected[k] for k in ('payload_id','source_uri','sha256')):
        raise ReconstructionError('SHARED_SOURCE_CORRUPTED','Source differs from release membership')
    return payload


async def resolve_shared_source(conn,index_id,locator,expected_hash,cache):
    try:
        return await _resolve_shared_source(conn,index_id,locator,expected_hash,cache)
    except ReconstructionError:
        raise
    except (KeyError,ValueError,TypeError,AttributeError) as exc:
        raise ReconstructionError('SHARED_SOURCE_CORRUPTED','Invalid shared source structure') from exc


async def _resolve_shared_source(conn,index_id,locator,expected_hash,cache):
    index_id=str(uuid.UUID(str(index_id)))
    root=await read_release_root(conn,index_id,cache)
    return await _resolve_member(conn,index_id,root,locator,expected_hash,cache)


async def read_release_root(conn,index_id,cache):
    index_id=str(uuid.UUID(str(index_id)))
    root_key=('shared-root',index_id)
    if root_key not in cache:
        uri=f'finmind:shared-source-release:{index_id}'
        root=await read_envelope(conn,uri)
        if root.get('schema_version')!='finmind-shared-source-release-v1' or root.get('index_version_id')!=index_id:
            raise ReconstructionError('SHARED_SOURCE_CORRUPTED','Release binding mismatch')
        regs=await conn.fetch('''SELECT corpus_version_id::text,manifest_sha256 FROM public.corpus_versions
            WHERE index_version_id=$1''',uuid.UUID(index_id))
        if len(regs)!=1 or regs[0]['corpus_version_id']!=root['corpus_version_id'] or regs[0]['manifest_sha256'].strip()!=root['registered_manifest_sha256']:
            raise ReconstructionError('SHARED_SOURCE_RELEASE_MISMATCH','Registered corpus does not match source release')
        cache[root_key]=root
    return cache[root_key]


async def _resolve_member(conn,index_id,root,locator,expected_hash,cache):
    members=[m for m in root['sources'] if m['source_table']==locator['source_table'] and m['source_id']==locator['source_id']]
    if len(members)!=1:raise ReconstructionError('SHARED_SOURCE_MISSING','Source not in pinned release')
    member=members[0]
    if member.get('mode')=='profile-version-metadata':
        from .reused_source import render_profile
        from .chunk_reconstruction import reconstruct_document_chunk
        return reconstruct_document_chunk(render_profile(member['recipe']),locator,expected_hash).text
    if member.get('mode') in ('existing-clean-payload','existing-news-payload','existing-bars-payload'):
        from .reused_source import read_pinned_payload,render_clean,render_news,render_bars
        from .chunk_reconstruction import reconstruct_document_chunk
        key=('reused-document',index_id,member['source_table'],member['source_id'])
        if key not in cache:
            binding=member['recipe']['binding']
            raw_key=('reused-raw',binding['payload_id'],binding['semantic_sha256'])
            if raw_key not in cache:cache[raw_key]=await read_pinned_payload(conn,binding)
            renderer={'existing-clean-payload':render_clean,'existing-news-payload':render_news,
                      'existing-bars-payload':render_bars}[member['mode']]
            recipe=member['recipe']
            if recipe.get('schema_version')=='clean-payload-render-recipe-compact-v1':
                from .reused_source import expand_financial_recipe
                recipe=expand_financial_recipe(recipe,root['financial_definitions'],cache[raw_key])
            cache[key]=renderer(cache[raw_key],recipe)
        return reconstruct_document_chunk(cache[key],locator,expected_hash).text
    key=('shared-document',member['payload_id'])
    if key not in cache:
        payload=await read_envelope(conn,member['source_uri'],member)
        if payload.get('index_version_id')!=index_id:raise ReconstructionError('SHARED_SOURCE_RELEASE_MISMATCH','Wrong source index')
        cache[key]=payload
    return resolve_source(cache[key],locator,expected_hash)


async def shared_price_rows(conn,scope,symbol,start_date=None,end_date=None):
    """Numeric reads use historical bars, never the overwritten live price values."""
    from .reused_source import read_pinned_payload
    from .corpus_scope import price_value_hash,CorpusScopeError
    from datetime import date
    from decimal import Decimal
    root=await read_release_root(conn,scope.index_version_id,{})
    members=[m for m in root['sources'] if m['source_table']=='price_bars' and m['source_id']==symbol.upper()]
    if not members:return []
    if len(members)!=1 or members[0]['mode']!='existing-bars-payload':
        raise ReconstructionError('SHARED_SOURCE_CORRUPTED','Historical price recipe ambiguous')
    recipe=members[0]['recipe'];payload=await read_pinned_payload(conn,recipe['binding'])
    bars=payload if isinstance(payload,list) else payload['bars'];by_day={str(b.get('trade_date',b.get('date')))[:10]:b for b in bars}
    rows=await conn.fetch('''SELECT cp.price_id::text,cp.value_hash,p.company_id::text,p.trade_date,p.is_adjusted
        FROM public.corpus_prices cp JOIN public.price_bars p USING(price_id)
        JOIN public.companies c ON c.company_id=p.company_id WHERE cp.corpus_version_id=$1 AND c.symbol=$2
        ORDER BY p.trade_date,p.price_id''',uuid.UUID(scope.corpus_version_id),symbol.upper())
    if {str(r['trade_date']) for r in rows}!=set(recipe['dates']):
        raise CorpusScopeError('CORPUS_PRICE_MEMBERSHIP_MISMATCH','Stored price members differ from historical source')
    result=[]
    for row in rows:
        bar=by_day.get(str(row['trade_date']))
        if bar is None:raise ReconstructionError('SOURCE_MISSING','Historical price date missing')
        item=dict(row,price_scale=1000,**{k:None if bar.get(k) is None else Decimal(str(bar[k])) for k in ('open','high','low','close','volume')})
        item.update({k:None if recipe['indicators'].get(row['price_id'],{}).get(k) is None else Decimal(recipe['indicators'][row['price_id']][k]) for k in ('sma20','sma50','rsi14')})
        if price_value_hash(item)!=row['value_hash'].strip():raise CorpusScopeError('CORPUS_PRICE_CHANGED','Historical price hash differs')
        if (start_date is None or row['trade_date']>=start_date) and (end_date is None or row['trade_date']<=end_date):result.append(item)
    return result
