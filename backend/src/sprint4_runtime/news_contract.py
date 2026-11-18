"""Contract 2.3 adds database NEWS locators without inventing PDF pages.

The original locator is exchanged verbatim so WBS06 can independently replay
and compare it. Schema validation is never treated as source verification.
"""
from copy import deepcopy
from hashlib import sha256
from urllib.parse import urlsplit
from jsonschema import Draft202012Validator, FormatChecker
from ..graph_temporal import extended_validator

VERSION = '2.3.0'


def news_schema(base):
    schema = deepcopy(extended_validator(base).schema)
    schema['properties']['schema_version'] = {'const': VERSION}
    uuid = deepcopy(base['$defs']['db_chunk']['properties']['chunk_id'])
    digest = {'type': 'string', 'pattern': '^[a-f0-9]{64}$'}
    offsets = {k: {'type': 'integer', 'minimum': 0} for k in (
        'section_index', 'row_start', 'row_end', 'char_start', 'char_end', 'chunk_index')}
    reconstruction = dict(type='object', properties={**offsets,
        'schema_version': {'const': 'source-locator-v2'},
        'chunker_version': {'type': 'string', 'minLength': 1},
        'document_id': uuid, 'source_chunk_id': uuid,
        'content_hash': digest, 'source_view_sha256': digest},
        required=[*offsets, 'schema_version', 'chunker_version', 'document_id',
                  'source_chunk_id', 'content_hash', 'source_view_sha256'])
    schema['$defs']['news_locator'] = dict(type='object', properties={
        'source_table': {'const': 'news_articles'}, 'doc_type': {'const': 'NEWS'},
        'source_id': uuid, 'url': {'type': 'string', 'format': 'uri'},
        'reconstruction': reconstruction}, required=[
            'source_table', 'source_id', 'doc_type', 'url', 'reconstruction'],
        # Neither a fake page nor a PDF locator can enter this profile.
        allOf=[{'not': {'required': [key]}} for key in ('page', 'bbox', 'block_id', 'kind')])
    chunk = deepcopy(base['$defs']['db_chunk'])
    chunk['properties']['locator'] = {'$ref': '#/$defs/news_locator'}
    schema['$defs']['news_chunk'] = chunk
    schema['$defs']['chunk']['oneOf'].append({'$ref': '#/$defs/news_chunk'})
    return schema


def is_news_locator(locator):
    return isinstance(locator, dict) and locator.get('source_table') == 'news_articles' and locator.get('doc_type') == 'NEWS'


def validate_news_chunk(chunk, schema):
    checker = Draft202012Validator({'$ref': '#/$defs/news_chunk', '$defs': schema['$defs']}, format_checker=FormatChecker())
    error = next(checker.iter_errors(chunk), None)
    if error:
        raise ValueError('NEWS chunk schema: ' + error.message[:180])
    loc = chunk['locator']; meta = loc['reconstruction']
    url = urlsplit(loc['url'])
    if url.scheme not in ('http', 'https') or not url.netloc or url.username or url.password:
        raise ValueError('NEWS source URL')
    # reconstruction.document_id identifies the immutable source snapshot. A
    # corpus release may give the bound document another ID; the live reader
    # validates that binding. Do not rewrite the original locator to match it.
    if meta['char_end'] <= meta['char_start'] or meta['row_end'] <= meta['row_start']:
        raise ValueError('NEWS source span order')
    if not chunk['text'].strip() or sha256(chunk['text'].encode()).hexdigest() != meta['content_hash']:
        raise ValueError('NEWS chunk content hash')
    return chunk
