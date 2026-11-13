"""Record each web-chat turn in queries / query_companies / answers. Best-effort: never blocks the reply."""
import logging
import uuid

logger = logging.getLogger(__name__)


async def _write(conn, user_id, question, result, latency_ms):
    scope = result.get('scope') or {}
    answering = result.get('answering') or {}
    manifest = answering.get('manifest') or {}
    query_id = uuid.uuid4()
    status = answering.get('status') or result.get('status')
    reason = answering.get('reason_code') or result.get('reason_code')
    async with conn.transaction():
        await conn.execute(
            "INSERT INTO queries(query_id, user_id, question_text, question_type, language, trace_id, created_at) "
            "VALUES ($1, $2, $3, $4, 'vi', $5, now())",
            query_id, uuid.UUID(str(user_id)), question, scope.get('source_type'), result.get('request_id'))
        await conn.execute(
            "INSERT INTO query_companies(query_id, company_id) "
            "SELECT $1, company_id FROM companies WHERE symbol = ANY($2::text[]) ON CONFLICT DO NOTHING",
            query_id, [c for c in scope.get('companies') or [] if isinstance(c, str)])
        if reason:  # answers.reason_code references the catalog; new codes are registered on first use
            await conn.execute(
                "INSERT INTO reason_codes(code, is_active) VALUES ($1, true) ON CONFLICT (code) DO NOTHING", reason)
        await conn.execute(
            "INSERT INTO answers(answer_id, query_id, attempt, answer_text, status, reason_code, model_name, "
            "prompt_version, latency_ms, created_at) VALUES ($1, $2, 1, $3, $4, $5, $6, $7, $8, now())",
            uuid.uuid4(), query_id, answering.get('draft') or answering.get('message') or result.get('message'),
            status, reason, manifest.get('model_returned'), manifest.get('prompt_version'), latency_ms)
    return str(query_id)


async def record_turn(pool, *, user_id, question, result, latency_ms):
    """Return the new query_id, or None when logging failed (a warning is logged; the chat is unaffected)."""
    try:
        if hasattr(pool, 'acquire'):
            async with pool.acquire() as conn:
                return await _write(conn, user_id, question, result or {}, latency_ms)
        return await _write(pool, user_id, question, result or {}, latency_ms)
    except Exception:
        logger.warning('chat_trace_failed')
        return None
