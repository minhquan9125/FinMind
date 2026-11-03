"""Independent source replay, pinned to corpus/index/document/chunk versions."""
from __future__ import annotations

import hashlib
import json
from typing import Protocol
import uuid

from .models import Evidence, SourceProblem, VerifiedSource


class SourceReader(Protocol):
    async def resolve(self, evidence: Evidence) -> VerifiedSource: ...


def compare_source(ref: Evidence, source: VerifiedSource) -> None:
    if not source.active:
        raise SourceProblem("ERR_SOURCE_SUPERSEDED")
    for name in ("document_id", "chunk_id", "corpus_id", "index_version_id"):
        if getattr(ref, name) != getattr(source, name):
            raise SourceProblem("ERR_SOURCE_VERSION_MISMATCH")
    if ref.document_version != source.document_version or ref.source_sha256 != source.source_sha256:
        raise SourceProblem("ERR_SOURCE_VERSION_MISMATCH")
    actual = hashlib.sha256(source.text.encode("utf-8")).hexdigest()
    if actual != source.content_hash or ref.content_hash != actual:
        raise SourceProblem("ERR_SOURCE_HASH_MISMATCH")
    if ref.locator != source.locator:
        raise SourceProblem("ERR_LOCATOR_MISMATCH")
    if not ref.quote.strip() or ref.quote not in source.text:
        raise SourceProblem("ERR_EVIDENCE_UNGROUNDED")


class FixtureSourceReader:
    """Independent fixture sources. Never authorizes a real graph write."""
    def __init__(self, sources: list[VerifiedSource]):
        self.sources = {(s.document_id, s.chunk_id): s for s in sources}

    async def resolve(self, evidence: Evidence) -> VerifiedSource:
        source = self.sources.get((evidence.document_id, evidence.chunk_id))
        if source is None:
            raise SourceProblem("ERR_LOCATOR_ORPHAN")
        # A fixture file cannot promote itself by claiming verification_mode=LIVE.
        from dataclasses import replace
        return replace(source, verification_mode="FIXTURE")


class PostgresSourceReader:
    def __init__(self, connection):
        self.connection = connection
        self.cache = {}

    async def resolve(self, evidence: Evidence) -> VerifiedSource:
        return await self.read_current(evidence.chunk_id, evidence.corpus_id)

    async def read_current(self, chunk_id: str, corpus_id: str) -> VerifiedSource:
        key = ("wbs06-verified", str(chunk_id), str(corpus_id))
        if key not in self.cache:
            try:
                self.cache[key] = await self._read_current(chunk_id, corpus_id)
            except SourceProblem as exc:
                self.cache[key] = exc
        if isinstance(self.cache[key], SourceProblem):
            raise self.cache[key]
        return self.cache[key]

    async def _read_current(self, chunk_id: str, corpus_id: str) -> VerifiedSource:
        """Caller keeps the batch in one read-only repeatable-read transaction."""
        from types import SimpleNamespace
        evidence = SimpleNamespace(chunk_id=chunk_id, corpus_id=corpus_id)
        from ..documents.chunk_reconstruction import ReconstructionError
        from ..documents.annual_source_reader import read_annual_chunk
        from ..documents.shared_source import read_release_root
        from ..documents.repository import resolve_result_rows
        try:
            row = await self.connection.fetchrow("""
                SELECT t.*, d.doc_type, d.sha256 AS source_sha256, i.chunker_version,
                       cv.corpus_version_id::text AS corpus_id,
                       i.status AS index_status, cv.status AS corpus_status,
                       cd.document_hash
                FROM public.text_chunks t JOIN public.documents d USING(document_id)
                JOIN public.index_versions i USING(index_version_id)
                JOIN public.corpus_versions cv ON cv.index_version_id=i.index_version_id
                JOIN public.corpus_documents cd ON cd.document_id=d.document_id
                  AND cd.corpus_version_id=cv.corpus_version_id
                WHERE t.chunk_id=$1 AND cv.corpus_version_id=$2
            """, uuid.UUID(evidence.chunk_id), uuid.UUID(evidence.corpus_id))
            if row is None:
                raise SourceProblem("ERR_LOCATOR_ORPHAN")
            if row.get("superseded_at") is not None:
                raise SourceProblem("ERR_SOURCE_SUPERSEDED")
            if row["index_status"] != "ACTIVE" or row["corpus_status"] not in ("FROZEN", "ACTIVE"):
                raise SourceProblem("ERR_SOURCE_VERSION_INACTIVE")
            if not row["document_hash"] or row["document_hash"].strip() != row["source_sha256"].strip():
                raise SourceProblem("ERR_SOURCE_HASH_MISMATCH")
            if row["doc_type"] == "ANNUAL_REPORT":
                verified = await read_annual_chunk(self.connection, evidence.chunk_id, evidence.corpus_id, self.cache)
                locator = verified["locator"]
                root = await read_release_root(self.connection, verified["index_version_id"], self.cache)
                member = next((m for m in root["sources"] if m["source_table"] == locator["source_table"]
                               and m["source_id"] == locator["source_id"]), None)
                if member is None:
                    raise SourceProblem("ERR_LOCATOR_ORPHAN")
                meta = locator["reconstruction"]
                header, sep, _ = verified["chunk_text"].partition("\n")
                contract_locator = dict(kind="db_text_span", page=verified["pdf_page"],
                    section_index=meta["section_index"], char_start=meta["char_start"],
                    char_end=meta["char_end"], text_start=len(header)+len(sep),
                    offset_basis="normalized_section_body", offset_unit="unicode_codepoint",
                    content_hash=verified["content_hash"])
                # Annual document version is the pinned WHOLE snapshot SHA.
                # read_annual_chunk already checked the section's separate
                # source_view_sha256 during replay; it is not a document version.
                return VerifiedSource(verified["document_id"], member["sha256"],
                    evidence.chunk_id, evidence.corpus_id, verified["index_version_id"],
                    member["sha256"], verified["content_hash"], contract_locator, verified["chunk_text"])
            # Non-annual sources must also replay through their registered locator.
            rows = await resolve_result_rows(self.connection, [dict(row) | {'page': row.get('page_number')}])
            actual = rows[0]
            locator = actual["locator_json"]
            return VerifiedSource(str(row["document_id"]), row["source_sha256"].strip(),
                str(row["chunk_id"]), evidence.corpus_id, str(row["index_version_id"]),
                row["source_sha256"].strip(), row["content_hash"].strip(), locator, actual["text"])
        except SourceProblem:
            raise
        except ReconstructionError as exc:
            mapping = {"SOURCE_CHANGED": "ERR_SOURCE_SUPERSEDED", "HASH_MISMATCH": "ERR_SOURCE_HASH_MISMATCH",
                       "SOURCE_MISSING": "ERR_LOCATOR_ORPHAN", "CHUNK_NOT_IN_CORPUS": "ERR_LOCATOR_ORPHAN"}
            raise SourceProblem(mapping.get(exc.code, "ERR_LOCATOR_UNVERIFIED")) from None
        except (ValueError, TypeError, KeyError, StopIteration):
            raise SourceProblem("ERR_LOCATOR_UNVERIFIED") from None
