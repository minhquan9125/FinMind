"""Resolve a frozen source from its registered membership and immutable payload."""

import asyncio
from copy import deepcopy
from datetime import datetime
from decimal import Decimal
from uuid import UUID, uuid5

import pytest

from src.documents.chunk_reconstruction import ReconstructionError
from src.documents.db_chunking import (
    SourceDocument, SourceRow, SourceSection, chunk_document, company_documents,
    index_documents, news_documents, price_documents,
)
from src.documents.reused_source import (
    financial_recipe, render_clean, restore_structure, semantic_hash, structure_recipe,
)
from src.documents.shared_source import envelope, normalize_document, resolve_shared_source


INDEX = "00000000-0000-4000-8000-000000000001"
CORPUS = "00000000-0000-4000-8000-000000000002"
PAYLOAD = "00000000-0000-4000-8000-000000000003"
MANIFEST = "a" * 64
URI = f"finmind:shared-source-release:{INDEX}"
NS = UUID("b77dbd7f-5d89-479d-90a3-421e5f0981ea")


class ReadConnection:
    def __init__(self):
        self.envelopes = {}
        self.registry = [dict(corpus_version_id=CORPUS, manifest_sha256=MANIFEST)]
        self.payloads = {}
        self.parameters = []

    async def fetch(self, sql, key):
        assert sql.lstrip().upper().startswith("SELECT")
        self.parameters.append(key)
        if "corpus_versions" in sql:
            assert key == UUID(INDEX)
            return self.registry
        if "WHERE source_uri=" in sql:
            return self.envelopes.get(key, [])
        assert "WHERE payload_id=" in sql
        return self.payloads.get(key, [])


def chunk_envelope(document):
    return dict(source_table=document.source_table, source_id=document.source_id,
                document_id=document.document_id, chunks=[item.to_dict() for item in chunk_document(document)])


def install_release(connection, member):
    root = dict(schema_version="finmind-shared-source-release-v1", index_version_id=INDEX,
                corpus_version_id=CORPUS, registered_manifest_sha256=MANIFEST, sources=[member])
    connection.envelopes[URI] = [envelope(URI, root)]
    return root


@pytest.fixture
def profile():
    return dict(company_id="public-company-fixture", symbol="ICT", company_name="CTIN",
                exchange="HOSE", industry_type="TECH", sector="Công nghệ", is_active=True)


@pytest.mark.parametrize("mode", ["normalized", "profile", "news", "stock", "index"])
def test_reconstructs_real_source_bytes_and_reuses_only_verified_cache(profile, mode):
    conn = ReadConnection()
    if mode in {"normalized", "profile"}:
        document = company_documents([profile])[0]
        recipe = {"fields": profile}
        member_mode = "profile-version-metadata"
        raw = None
    elif mode == "news":
        stamp = "2026-10-01T07:00:00+07:00"
        url = "https://example.test/ict-release"
        articles = [{"url": url, "title": "ICT công bố", "content": "Nội dung gốc của thông báo."}]
        raw = {"articles": articles}
        recipe = dict(source_id="public-article-fixture", url=url, source="cafef", title="ICT công bố",
                      published_at=stamp, symbols=["ICT"])
        member_mode = "existing-news-payload"
        document = news_documents([dict(article_id=recipe["source_id"], source="cafef",
            title=articles[0]["title"], content=articles[0]["content"], symbols=["ICT"], url=url,
            published_at=datetime.fromisoformat(stamp))])[0]
    else:
        day = "2026-10-01"
        bar = dict(trade_date=day, open=101, high=104, low=100, close=103, volume=30)
        raw = {"bars": [bar]}
        symbol = "ICT" if mode == "stock" else "VNINDEX"
        table = "price_bars" if mode == "stock" else "market_index_bars"
        key = str(uuid5(NS, f"price:{symbol}:{day}:False")) if mode == "stock" else f"{symbol}:{day}"
        recipe = dict(source_table=table, symbol=symbol, company_name="Fixture", dates=[day],
                      indicators={key: {"sma20": "102.50"}})
        member_mode = "existing-bars-payload"
        values = {**bar, "sma20": Decimal("102.50")}
        if mode == "stock":
            document = price_documents([dict(values, symbol=symbol, company_name="Fixture", price_id=key, price_scale=1000)])[0]
        else:
            document = index_documents([dict(values, index_symbol=symbol, index_name="Fixture")])[0]

    member = dict(source_table=document.source_table, source_id=document.source_id)
    if mode == "normalized":
        source_uri = "finmind:qa:versioned-profile"
        normalized = normalize_document(chunk_envelope(document), INDEX)
        record = envelope(source_uri, normalized)
        conn.envelopes[source_uri] = [record]
        member.update({key: record[key] for key in ("payload_id", "source_uri", "sha256")})
    else:
        member.update(mode=member_mode, recipe=recipe)
        if raw is not None:
            recipe["binding"] = dict(payload_id=PAYLOAD, stored_sha256="b" * 64, semantic_sha256=semantic_hash(raw))
            conn.payloads[UUID(PAYLOAD)] = [dict(sha256="b" * 64, payload=raw)]
    install_release(conn, member)
    chunks = chunk_document(document)
    cache = {}
    for chunk in chunks:
        text = asyncio.run(resolve_shared_source(conn, INDEX, chunk.locator, chunk.content_hash, cache))
        assert text == chunk.text
    read_count = len(conn.parameters)
    assert asyncio.run(resolve_shared_source(conn, INDEX, chunks[0].locator, chunks[0].content_hash, cache)) == chunks[0].text
    assert len(conn.parameters) == read_count


@pytest.mark.parametrize("fault,code", [
    ("missing root", "SHARED_SOURCE_MISSING"),
    ("wrong registry", "SHARED_SOURCE_RELEASE_MISMATCH"),
    ("bad root schema", "SHARED_SOURCE_CORRUPTED"),
    ("missing member", "SHARED_SOURCE_MISSING"),
    ("changed source index", "SHARED_SOURCE_RELEASE_MISMATCH"),
    ("changed normalized body", "HASH_MISMATCH"),
    ("duplicated locator", "SOURCE_CHANGED"),
    ("bad release membership hash", "SHARED_SOURCE_CORRUPTED"),
    ("missing raw payload", "SOURCE_MISSING"),
    ("changed raw payload", "SOURCE_CHANGED"),
])
def test_release_fails_closed_when_any_provenance_binding_breaks(profile, fault, code):
    document = company_documents([profile])[0]
    chunk = chunk_document(document)[0]
    conn = ReadConnection()
    source_uri = "finmind:qa:profile"
    payload = normalize_document(chunk_envelope(document), INDEX)
    if fault == "changed source index":
        payload["index_version_id"] = PAYLOAD
    if fault == "changed normalized body":
        payload["sections"][0]["body"] = "A" + payload["sections"][0]["body"][1:]
    if fault == "duplicated locator":
        payload["locators"].append(deepcopy(payload["locators"][0]))
    record = envelope(source_uri, payload)
    conn.envelopes[source_uri] = [record]
    member = dict(source_table=document.source_table, source_id=document.source_id, **{
        key: record[key] for key in ("source_uri", "payload_id", "sha256")
    })
    if fault == "bad release membership hash":
        member["sha256"] = "0" * 64
    if fault in {"missing raw payload", "changed raw payload"}:
        member.update(mode="existing-news-payload", recipe={"binding": dict(
            payload_id=PAYLOAD, stored_sha256="c" * 64, semantic_sha256=semantic_hash({"articles": []}))})
    if fault == "changed raw payload":
        conn.payloads[UUID(PAYLOAD)] = [dict(sha256="c" * 64, payload={"articles": [{"title": "Changed"}]})]
    root = install_release(conn, member)
    if fault == "missing root":
        conn.envelopes.clear()
    elif fault == "wrong registry":
        conn.registry[0]["manifest_sha256"] = "0" * 64
    elif fault == "bad root schema":
        conn.envelopes[URI] = [envelope(URI, {**root, "schema_version": "future"})]
    elif fault == "missing member":
        conn.envelopes[URI] = [envelope(URI, {**root, "sources": []})]
    with pytest.raises(ReconstructionError) as error:
        asyncio.run(resolve_shared_source(conn, INDEX, chunk.locator, chunk.content_hash, {}))
    assert error.value.code == code


def test_clean_recipe_rebuilds_the_exact_original_metric_and_rejects_missing_value():
    base = SourceDocument("financial_reports", "fixture-report", "FINANCIAL_STATEMENT", "Original",
        "ICT", "vi", [SourceSection("Kết quả kinh doanh", "Thu nhập ICT",
                                   [SourceRow("ob-1", "Doanh thu (NET_REVENUE): 0.01 triệu VND")])],
        {"chunker_version": "db-financial-v4", "period_code": "2026-Q2"})
    source = dict(observation_id="ob-1", symbol="ICT", period_code="2026-Q2", section="INCOME_STATEMENT",
                  code="NET_REVENUE", unit="VND", locator_json={"source_section": "income_statement", "source_field": "isa1"})
    payload = {"mã_chứng_khoán": "ICT", "báo_cáo_tài_chính": {"kết_quả_kinh_doanh": [{
        "kỳ_báo_cáo": "2026-Q2",
        "chỉ_tiêu": [{"trường_gốc": "isa1", "mã_chuẩn": "NET_REVENUE", "giá_trị": 12345}],
    }]}}
    spec = chunk_envelope(base)
    recipe = financial_recipe(spec, [source], {})
    restored = render_clean(payload, recipe)
    original_chunk, rendered_chunk = chunk_document(base)[0], chunk_document(restored)[0]
    assert original_chunk.content_hash == rendered_chunk.content_hash
    assert original_chunk.locator == rendered_chunk.locator
    assert restore_structure(restored, structure_recipe(spec)).sections == base.sections
    payload["báo_cáo_tài_chính"]["kết_quả_kinh_doanh"][0]["chỉ_tiêu"].clear()
    with pytest.raises(ReconstructionError) as error:
        render_clean(payload, recipe)
    assert error.value.code == "SOURCE_MISSING"
