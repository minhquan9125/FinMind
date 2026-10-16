"""Hỏi đáp nhiều lượt trong terminal với dữ liệu fixture."""
import asyncio
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from retrieval_flow.conversation import ChatSession, render_response


def save_history(history: dict[str, Any], directory: Path | None = None) -> Path:
    """Lưu history dict ra JSON UTF-8 indent2, trả về đường dẫn file."""
    if directory is None:
        directory = Path(__file__).resolve().parent / 'chat_history'
    directory.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')
    unique_id = uuid.uuid4().hex
    filename = f'session_{timestamp}_{unique_id}.json'
    filepath = directory / filename
    payload = json.dumps(history, ensure_ascii=False, indent=2)
    with filepath.open('x', encoding='utf-8') as output:
        output.write(payload)
    return filepath


async def main(*, persist: bool = False, history_dir: Path | None = None) -> dict[str, Any]:
    """Chạy CLI hỏi đáp. persist=True để lưu lịch sử ra đĩa."""
    session = ChatSession()
    messages: list[dict[str, Any]] = []
    started_at = datetime.now(timezone.utc).isoformat()

    print('Tra cứu tài chính — dữ liệu giả lập, chưa có số liệu thật.')
    print('Nhập câu hỏi; /moi: bắt đầu lại; /json: xem kết quả kỹ thuật; exit: thoát.')

    try:
        while True:
            try:
                text = input('\nBạn: ').strip()
            except (EOFError, KeyboardInterrupt):
                break
            if not text:
                continue
            if text.lower() in ('exit', 'quit', 'thoat', 'thoát'):
                break
            if text.lower() == '/moi':
                messages.append({
                    'role': 'user',
                    'content': text,
                    'timestamp': datetime.now(timezone.utc).isoformat()
                })
                messages.append({
                    'role': 'assistant',
                    'content': 'Đã xóa ngữ cảnh, bắt đầu câu hỏi mới.',
                    'timestamp': datetime.now(timezone.utc).isoformat()
                })
                session.reset()
                print('Trợ lý: Đã xóa ngữ cảnh, bắt đầu câu hỏi mới.')
            elif text.lower() == '/json':
                result = session.last_result
                output = json.dumps(result, ensure_ascii=False, indent=2) if result else 'Chưa có kết quả trong phiên này.'
                print(output)
            else:
                messages.append({
                    'role': 'user',
                    'content': text,
                    'timestamp': datetime.now(timezone.utc).isoformat()
                })
                result = await session.ask(text)
                messages.append({
                    'role': 'assistant',
                    'content': render_response(result),
                    'timestamp': datetime.now(timezone.utc).isoformat(),
                    'result': result
                })
                print('Trợ lý: ' + render_response(result))
    finally:
        if persist and messages:
            saved_at = datetime.now(timezone.utc).isoformat()
            history = {
                'schema_version': '1.0',
                'session_id': session.session_id,
                'started_at': started_at,
                'saved_at': saved_at,
                'messages': messages
            }
            try:
                filepath = save_history(history, history_dir)
                print(f'\nĐã lưu lịch sử: {filepath}')
            except OSError as e:
                print(f'\nLỗi lưu lịch sử: {e}')

    return {
        'schema_version': '1.0',
        'session_id': session.session_id,
        'started_at': started_at,
        'saved_at': datetime.now(timezone.utc).isoformat(),
        'messages': messages
    }


if __name__ == '__main__':
    try:
        asyncio.run(main(persist=True))
    except KeyboardInterrupt:
        print('\nĐã thoát.')
