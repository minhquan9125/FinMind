"""WBS07 boundary: immutable candidates, optimistic admin review and audit.

Postgres works with the supplied Supabase schema. No migration is run here.
"""
from copy import deepcopy
from datetime import datetime, timezone
import json
import uuid

from .models import Candidate, ReviewResult, digest

NAMESPACE = uuid.UUID("49b56574-9791-44af-978a-f07713eb3f96")
MANUAL_WARNINGS = {"WARN_EVIDENCE_INSUFFICIENT", "WARN_CONFLICTING_SOURCES"}


class ReviewConflict(ValueError):
    pass


def require_role(actor, *roles):
    if not set(actor.roles).intersection(roles):
        raise PermissionError("Review role is not authorized")


def record_id(graph_id, candidate_id):
    return str(uuid.uuid5(NAMESPACE, json.dumps([str(graph_id), candidate_id])))


def transition(record, decision, fresh, actor, note, revision, evidence_confirmed=False):
    require_role(actor, "ADMINISTRATOR")
    if record["revision"] != revision:
        raise ReviewConflict("Review revision changed; reload first")
    if record["result"]["status"] == "REJECTED":
        raise ReviewConflict("REJECTED is terminal; submit a corrected extraction with a new identity")
    if decision not in {"APPROVED", "PENDING", "REJECTED"} or not note.strip():
        raise ValueError("Explicit decision and review note required")
    if fresh.candidate_sha256 != digest(record["candidate"]):
        raise ReviewConflict("Candidate changed during review")
    if decision == "APPROVED":
        if fresh.checks.get('conflicting_candidates'):
            raise ValueError("Resolve or reject conflicting peer candidates before approval")
        if not fresh.source_verified or fresh.verification_mode != "LIVE" or fresh.status == "REJECTED":
            raise ValueError("Current, live verified sources required")
        if fresh.status == "PENDING" and (not evidence_confirmed or not set(fresh.reasons) <= MANUAL_WARNINGS):
            raise ValueError("Resolve identity/time/claim warnings before approval; source errors cannot be overridden")
        result = fresh.model_copy(deep=True, update={"status": "APPROVED", "reasons": [],
            "checks": {**fresh.checks, "manual_evidence_confirmed": evidence_confirmed,
                       "overridden_warnings": fresh.reasons}})
    else:
        if decision == "PENDING" and fresh.status == "REJECTED":
            raise ValueError("Technical rejection cannot be downgraded to pending")
        result = fresh.model_copy(deep=True, update={"status": decision,
            "reasons": ["ERR_MANUAL_REJECTION" if decision == "REJECTED" else "WARN_MANUAL_REVIEW"]})
    audit = dict(actor_id=str(actor.user_id), decision=decision, note=note,
                 evidence_confirmed=evidence_confirmed, checked_at=datetime.now(timezone.utc).isoformat(),
                 evaluation=fresh.model_dump(mode="json"))
    return result, audit


class MemoryReviewStore:
    """Test-only persistence double, never a runtime fallback for Supabase."""
    def __init__(self):
        self.records, self.quarantine, self.audit = {}, {}, []

    async def save(self, raw, result, graph_id, actor, extraction_id=None):
        require_role(actor, "DATA_ENGINEER", "ADMINISTRATOR")
        if digest(raw) != result.candidate_sha256:
            raise ReviewConflict("Result is not bound to the candidate")
        if result.status != "REJECTED" and any(r["candidate"].get("candidate_id") == result.candidate_id
                and r["result"]["status"] == "REJECTED" for r in self.records.values()):
            raise ReviewConflict("Rejected candidate cannot be revived in another graph version")
        ident = record_id(graph_id, result.candidate_id)
        old = self.records.get(ident)
        if old:
            if digest(old["candidate"]) != digest(raw):
                raise ReviewConflict("Immutable candidate ID reused with changed content")
            return deepcopy(old)
        row = dict(review_id=ident, graph_version_id=str(graph_id), candidate=deepcopy(raw),
                   result=result.model_dump(mode="json"), revision=1)
        self.records[ident] = row
        if result.status != "APPROVED":
            self.quarantine[ident] = deepcopy(row)
        self.audit.append(dict(review_id=ident, actor_id=str(actor.user_id), decision=result.status, note="Initial evaluation"))
        return deepcopy(row)

    async def get(self, ident):
        return deepcopy(self.records.get(str(ident)))

    async def approved(self, graph_id):
        return [deepcopy(r) for r in self.records.values() if r["graph_version_id"] == str(graph_id)
                and r["result"]["status"] == "APPROVED"]

    async def active(self, graph_id):
        rejected={r['candidate'].get('candidate_id') for r in self.records.values() if r['result']['status']=='REJECTED'}
        return [deepcopy(r) for r in self.records.values() if r['graph_version_id']==str(graph_id)
                and r['result']['status']!='REJECTED' and r['candidate'].get('candidate_id') not in rejected]

    async def review(self, ident, decision, fresh, actor, note, revision, evidence_confirmed=False):
        row = self.records[str(ident)]
        if decision == "APPROVED" and any(r["candidate"].get("candidate_id") == fresh.candidate_id
                and r["result"]["status"] == "REJECTED" for r in self.records.values()):
            raise ReviewConflict("Rejected candidate cannot be revived in another graph version")
        result, audit = transition(row, decision, fresh, actor, note, revision, evidence_confirmed)
        row.update(result=result.model_dump(mode="json"), revision=revision+1)
        self.quarantine[str(ident)] = deepcopy(row)  # retain reviewed quarantine history
        self.audit.append(dict(review_id=str(ident), **audit))
        return deepcopy(row)


class PostgresReviewStore:
    def __init__(self, connection):
        self.c = connection

    @staticmethod
    def decode(row):
        if row is None:
            return None
        return dict(review_id=str(row["review_id"]), graph_version_id=str(row["graph_version_id"]),
                    candidate=json.loads(row["candidate"]) if isinstance(row["candidate"], str) else row["candidate"],
                    result=json.loads(row["evaluation"]) if isinstance(row["evaluation"], str) else row["evaluation"],
                    revision=row["revision"])

    async def get(self, ident, *, lock=False):
        row = await self.c.fetchrow("SELECT * FROM public.graph_review_results WHERE review_id=$1" +
                                   (" FOR UPDATE" if lock else ""), uuid.UUID(str(ident)))
        return self.decode(row)

    async def _quarantine(self, row, actor, extraction_id=None, *, update=False):
        result = row["result"]
        if update:
            # Reviewer has UPDATE permission only. An INSERT ... ON CONFLICT
            # still requires INSERT and may hit policies before conflict handling.
            changed=await self.c.execute('''UPDATE public.quarantine_records SET
                reason_code=$2,status=$3,reviewed_by=$4,reviewed_at=now(),
                reasons=$5::jsonb,evaluation_payload=$6::jsonb WHERE review_id=$1''',
                uuid.UUID(row['review_id']),next(iter(result['reasons']),None),result['status'],actor.user_id,
                json.dumps(result['reasons']),json.dumps(result,ensure_ascii=False))
            if changed!='UPDATE 1':raise ReviewConflict('Expected one existing quarantine review record')
            return
        sql = """INSERT INTO public.quarantine_records
            (record_id,extraction_id,entity_type,reason_code,status,reviewed_by,reviewed_at,
             review_id,reasons,candidate_payload,evaluation_payload)
            VALUES($1,$2,'GRAPH_RELATION',$3,$4,$5,now(),$1,$6::jsonb,$7::jsonb,$8::jsonb)
            ON CONFLICT(record_id) """ + ("""DO UPDATE SET reason_code=EXCLUDED.reason_code,
                status=EXCLUDED.status,reviewed_by=EXCLUDED.reviewed_by,reviewed_at=EXCLUDED.reviewed_at,
                reasons=EXCLUDED.reasons,evaluation_payload=EXCLUDED.evaluation_payload""" if update else "DO NOTHING")
        await self.c.execute(sql,
            uuid.UUID(row["review_id"]), uuid.UUID(str(extraction_id)) if extraction_id else None,
            next(iter(result["reasons"]), None), result["status"], actor.user_id,
            json.dumps(result["reasons"]), json.dumps(row["candidate"], ensure_ascii=False),
            json.dumps(result, ensure_ascii=False))

    async def save(self, raw, result, graph_id, actor, extraction_id=None):
        require_role(actor, "DATA_ENGINEER", "ADMINISTRATOR")
        if digest(raw) != result.candidate_sha256 or result.verification_mode == "FIXTURE":
            raise ValueError("Production persistence requires a bound, non-fixture result")
        ident = record_id(graph_id, result.candidate_id)
        async with self.c.transaction():
            created = await self.c.fetchval("""INSERT INTO public.graph_review_results
                (review_id,graph_version_id,candidate_id,candidate_sha256,candidate,status,reasons,evaluation,created_by)
                VALUES($1,$2,$3,$4,$5::jsonb,$6,$7::jsonb,$8::jsonb,$9) ON CONFLICT DO NOTHING RETURNING review_id""",
                uuid.UUID(ident), uuid.UUID(str(graph_id)), result.candidate_id, result.candidate_sha256,
                json.dumps(raw, ensure_ascii=False), result.status, json.dumps(result.reasons),
                result.model_dump_json(), actor.user_id)
            row = await self.get(ident, lock=True)
            if row is None or digest(row["candidate"]) != result.candidate_sha256:
                raise ReviewConflict("Immutable candidate ID reused with changed content")
            if created:
                await self.c.execute("""INSERT INTO public.graph_review_audit
                    (review_id,actor_id,decision,note,evidence_confirmed,source_evaluation)
                    VALUES($1,$2,$3,'Initial rule evaluation',false,$4::jsonb)""",
                    uuid.UUID(ident), actor.user_id, result.status, result.model_dump_json())
            # Re-running an extractor never overwrites a human/terminal decision.
            if row["result"]["status"] != "APPROVED":
                await self._quarantine(row, actor, extraction_id)
            return row

    async def review(self, ident, decision, fresh, actor, note, revision, evidence_confirmed=False):
        async with self.c.transaction():
            row = await self.get(ident, lock=True)
            if row is None:
                raise KeyError("Review record not found")
            result, audit = transition(row, decision, fresh, actor, note, revision, evidence_confirmed)
            await self.c.execute("""UPDATE public.graph_review_results SET status=$2,reasons=$3::jsonb,
                evaluation=$4::jsonb,revision=revision+1,reviewed_by=$5,reviewed_at=now()
                WHERE review_id=$1 AND revision=$6""", uuid.UUID(str(ident)), result.status,
                json.dumps(result.reasons), result.model_dump_json(), actor.user_id, revision)
            await self.c.execute("""INSERT INTO public.graph_review_audit
                (review_id,actor_id,decision,note,evidence_confirmed,source_evaluation)
                VALUES($1,$2,$3,$4,$5,$6::jsonb)""", uuid.UUID(str(ident)), actor.user_id,
                decision, note, evidence_confirmed, fresh.model_dump_json())
            updated = await self.get(ident)
            await self._quarantine(updated, actor, update=True)
            return updated

    async def approved(self, graph_id):
        rows = await self.c.fetch("SELECT * FROM public.graph_review_results WHERE graph_version_id=$1 AND status='APPROVED'",
                                  uuid.UUID(str(graph_id)))
        return [self.decode(row) for row in rows]

    async def active(self, graph_id):
        rows = await self.c.fetch("""SELECT r.* FROM public.graph_review_results r
            WHERE r.graph_version_id=$1 AND r.status<>'REJECTED' AND NOT EXISTS(
                SELECT FROM public.graph_review_results rejected
                WHERE rejected.candidate_id=r.candidate_id AND rejected.status='REJECTED')""",
                                  uuid.UUID(str(graph_id)))
        return [self.decode(row) for row in rows]


async def evaluate_with_peers(store, engine, graph_id, candidate):
    peers = [r['candidate'] for r in await store.active(graph_id)
             if r['candidate']['candidate_id'] != candidate['candidate_id']]
    return (await engine.evaluate_batch([*peers, candidate]))[-1]


async def approved_records(store, engine, graph_id):
    """Revalidate on export/read: a stored APPROVED label cannot bless stale sources."""
    output = []
    rows = await store.active(graph_id)
    results = await engine.evaluate_batch([r['candidate'] for r in rows])
    for row, fresh in zip(rows, results):
        if row['result']['status'] != 'APPROVED':
            continue
        old = ReviewResult.model_validate(row["result"])
        if fresh.candidate_sha256 != old.candidate_sha256 or fresh.verification_mode != "LIVE" or not fresh.source_verified:
            continue
        manual = (old.checks.get("manual_evidence_confirmed") is True and fresh.status == "PENDING"
                  and set(fresh.reasons) <= MANUAL_WARNINGS
                  and not fresh.checks.get('conflicting_candidates')
                  and old.checks.get("registry_sha256") == fresh.checks.get("registry_sha256"))
        if fresh.status == "APPROVED" or manual:
            output.append(row)
    return output
