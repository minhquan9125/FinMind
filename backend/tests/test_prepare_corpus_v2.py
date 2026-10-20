"""A content snapshot must not masquerade as an ingested vector corpus."""
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'scripts'))
from prepare_corpus_v2 import freeze_documents
from src.documents.db_chunking import company_documents, financial_documents
from src.documents.corpus_manifest import sha256


def documents():
    company = company_documents([{'company_id': 'company-fpt', 'symbol': 'FPT',
                                  'company_name': 'FPT', 'industry_type': 'TECH'}])[0]
    financial = financial_documents([{'report_id': 'report-fpt', 'symbol': 'FPT',
        'company_name': 'FPT', 'period_code': '2026-Q2', 'statement_scope': 'UNKNOWN',
        'section': 'BALANCE_SHEET', 'code': 'TOTAL_ASSETS', 'canonical_name': 'Tổng tài sản',
        'observation_id': 'observation-fpt', 'value': 123, 'unit': 'SOURCE_NATIVE'}])[0]
    return [company, financial]


def test_content_freeze_is_deterministic_and_not_vector_ready():
    docs = documents()
    result = freeze_documents(docs)
    assert result == freeze_documents(list(reversed(docs)))
    assert result['manifest_sha256'] == sha256(result['manifest'])
    assert not result['benchmark_ready']
    assert not result['database_registered']
    assert not result['database_writes']
    assert not result['embedding_calls']
    assert result['manifest']['schema_version'] != 'finmind-corpus-v1'
    assert result['manifest']['chunk_count'] == 2
    for doc in result['manifest']['documents']:
        for chunk in doc['chunks']:
            assert chunk['source_chunk_id']
            assert 'chunk_id' not in chunk  # Do not claim an unassigned text_chunks PK.
    financial = next(d for d in result['manifest']['documents'] if d['doc_type'] == 'FINANCIAL_STATEMENT')
    assert 'đơn vị chưa xác minh' in financial['chunks'][0]['text']


def test_duplicate_document_is_rejected():
    doc = documents()[0]
    with pytest.raises(ValueError, match='Duplicate source document'):
        freeze_documents([doc, doc])
