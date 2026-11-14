"""Conversation processing shared by DB storage and offline fixture files."""
import asyncio
import copy
from datetime import datetime, timezone
import json

from .chat_types import ChatError, MAX_BYTES, MAX_MESSAGES, MAX_TEXT_LEN, now_iso
from .retrieval_flow.history import VIETNAM, restore_session


def validate_input(text, revision):
    if not isinstance(text, str): raise ChatError(422, 'Nội dung tin nhắn phải là chuỗi ký tự.')
    text = text.strip()
    if not 1 <= len(text) <= MAX_TEXT_LEN: raise ChatError(422, 'Tin nhắn phải có độ dài từ 1 đến 4000 ký tự.')
    if type(revision) is not int or revision < 0: raise ChatError(422, 'Revision phải là số nguyên không âm.')
    return text


def validate_size(doc):
    if len(doc.get('messages', [])) > MAX_MESSAGES:
        raise ChatError(422, 'Số lượng tin nhắn vượt quá giới hạn 2000.')
    if len(json.dumps(doc, ensure_ascii=False, allow_nan=False).encode('utf8')) > MAX_BYTES:
        raise ChatError(422, 'Kích thước phiên vượt quá 2 MiB.')


def new_document(owner, sid, source=None):
    now = now_iso()
    metadata = copy.deepcopy((source or {}).get('metadata', {}))
    if source: metadata['parent_session_id'] = source['session_id']
    return dict(schema_version='1.0', session_id=sid, owner=owner, revision=0,
                started_at=now, saved_at=now, messages=copy.deepcopy((source or {}).get('messages', [])), metadata=metadata)


def descriptor(doc):
    messages = [m for m in doc.get('messages', []) if m.get('role') == 'user' and not m.get('content', '').startswith('/')]
    preview = ''.join(c for c in messages[0]['content'] if c.isprintable())[:80] if messages else ''
    return dict(session_id=doc['session_id'], preview=preview, saved_at=doc['saved_at'], turns=len(messages))


async def summary(doc):
    if doc.get('metadata', {}).get('execution_mode') != 'LIVE':
        return (await restore_session(doc)).context_summary()
    from .live_research import METRIC_ALIASES
    scope = doc.get('metadata', {}).get('live_context', {})
    if not scope: return 'Nhập mã công ty, kỳ và chỉ tiêu hoặc chủ đề tin tức cần tra cứu.'
    return ' | '.join(filter(None, (
        'Công ty: '+', '.join(scope.get('companies', [])) if scope.get('companies') else '',
        'Kỳ: '+', '.join(scope.get('periods', [])) if scope.get('periods') else '',
        'Chỉ tiêu: '+METRIC_ALIASES.get(scope['metric_code'], (scope['metric_code'],))[0] if scope.get('metric_code') else '',
        'Nguồn: '+scope['source_type'] if scope.get('source_type') else '')))


async def snapshot(doc):
    return dict(session_id=doc['session_id'], revision=doc['revision'], messages=doc['messages'],
                context=await summary(doc), execution_mode=doc.get('metadata', {}).get('execution_mode', 'FIXTURE'))


async def append_turn(doc, text, engine):
    if len(doc['messages'])+2 > MAX_MESSAGES: raise ChatError(422, 'Số lượng tin nhắn vượt quá giới hạn 2000.')
    try:
        if engine is not None:
            from .live_research import render_live_response
            previous = None
            for message in reversed(doc['messages']):
                if message.get('role') == 'user' and message.get('content', '').strip().lower() in ('/moi', '/new'): break
                candidate = message.get('result') or {}
                if ((candidate.get('answering') or {}).get('status') == 'DRAFT_READY'
                        or (candidate.get('scope', {}).get('source_type') == 'NEWS'
                            and (candidate.get('evidence_pack') or {}).get('schema_version') == '1.2')):
                    previous = candidate
                    break
            result = await asyncio.wait_for(engine.answer(text, doc['session_id'], doc.get('metadata', {}).get('live_context', {}),
                previous_result=previous), engine.retrieval_timeout+engine.limits.read_timeout_seconds+5)
            content = render_live_response(result)
        else:
            from .retrieval_flow.conversation import render_response
            restored = await restore_session(doc)
            restored.session_id = doc['session_id']
            result = await asyncio.wait_for(restored.ask(text), 10)
            content = render_response(result)
    except (TimeoutError, OSError) as exc:
        raise ChatError(503, 'Xử lý tạm thời không thành công. Vui lòng thử lại.') from exc
    updated = copy.deepcopy(doc)
    now = datetime.now(timezone.utc)
    stamp = now.isoformat()
    updated.update(revision=doc['revision']+1, saved_at=stamp)
    updated['messages'].extend([
        dict(role='user', content=text, timestamp=stamp, reference_date=now.astimezone(VIETNAM).date().isoformat()),
        dict(role='assistant', content=content, timestamp=stamp, result=result)])
    if engine is not None:
        updated.setdefault('metadata', {}).update(execution_mode='LIVE', live_context=copy.deepcopy(result['scope']))
    validate_size(updated)
    return updated
