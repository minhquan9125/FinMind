"""Map all verified chunks of one BCTN to the handed-off DB contract."""

from .contracts import validate_envelope


def document_envelope(rows, corpus_version_id):
    """Build one 2.1.0 envelope using the verified whole-snapshot SHA256.

    The source reader has checked ``document_version`` against the immutable
    payload. Per-section hashes remain in document metadata for provenance.
    """
    if not rows:
        raise ValueError('No verified chunks')
    first = rows[0]
    document_id = first['document_id']
    version = first['document_version']
    source = first['source_binding']
    if version != source['source_sha256']:
        raise ValueError('Document version differs from verified source snapshot')
    index_id = first['index_version_id']
    document = {'source_kind': 'db', 'document_id': document_id,
                'document_version': version, 'source_uri': source['source_uri'],
                'source_sha256': source['source_sha256'], 'index_version_id': index_id,
                'title': first['title'], 'doc_type': first['doc_type'],
                'database_document_sha256': first['database_document_sha256'].strip()}
    if all(first.get(key) for key in ('company_id', 'issuer_symbol', 'issuer_company_name')):
        document.update(issuer_company_id=first['company_id'], issuer_symbol=first['issuer_symbol'],
                        issuer_company_name=first['issuer_company_name'])
    chunks = []
    sections = {}
    for row in rows:
        loc = row['locator_json']
        reconstruction = loc['reconstruction']
        if (row['document_id'] != document_id or row['index_version_id'] != index_id
                or row['source_binding'] != source
                or row['document_version'] != version
                or row['database_document_sha256'].strip() != document['database_document_sha256']):
            raise ValueError('Mixed document/source snapshot in one envelope')
        if 'issuer_company_id' in document and (row.get('company_id') != document['issuer_company_id']
                or row.get('issuer_symbol') != document['issuer_symbol']
                or row.get('issuer_company_name') != document['issuer_company_name']):
            raise ValueError('Mixed BCTN issuer in one envelope')
        section_index = reconstruction['section_index']
        section_hash = reconstruction['source_view_sha256']
        if section_index in sections and sections[section_index] != section_hash:
            raise ValueError('Conflicting source section hash')
        sections[section_index] = section_hash
        text = row['text']
        header, separator, body = text.partition('\n')
        if not separator or not header or not body:
            raise ValueError('Source chunk header/body missing')
        start, end = reconstruction['char_start'], reconstruction['char_end']
        if row['char_start'] != start or row['char_end'] != end:
            raise ValueError('DB and source locator offsets differ')
        page = loc.get('pdf_page') or row['page_number']
        if row['page_number'] is not None and page != row['page_number']:
            raise ValueError('Page number differs from locator')
        chunks.append({'document_id': document_id, 'document_version': version,
                       'chunk_id': row['chunk_id'], 'text': text,
                       'locator': {'kind': 'db_text_span', 'page': page,
                                   'section_index': section_index,
                                   'char_start': start, 'char_end': end,
                                   'text_start': len(header) + 1,
                                   'offset_basis': 'normalized_section_body',
                                   'offset_unit': 'unicode_codepoint',
                                   'content_hash': row['content_hash'].strip()}})
    document['source_sections'] = [{'section_index': index, 'source_view_sha256': sections[index]}
                                   for index in sorted(sections)]
    result = {'schema_version': '2.1.0', 'corpus_id': str(corpus_version_id),
              'dataset_version': index_id, 'documents': [document], 'chunks': chunks,
              'entities': [], 'mentions': [], 'relations': []}
    return validate_envelope(result)
