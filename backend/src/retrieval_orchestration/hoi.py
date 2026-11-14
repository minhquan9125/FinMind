"""Terminal fixture chat with validated history selection and continuation."""
import asyncio
import copy
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from retrieval_flow.conversation import ChatSession, render_response
from retrieval_flow.history import list_histories, load_history, restore_session

HELP = ('/lichsu: danh sách phiên | /mo 1 hoặc /mo ten_file.json: tiếp tục phiên\n'
        '/tomtat: thông tin đang hỏi | /moi: bắt đầu lại | /json: kết quả kỹ thuật\n'
        '/help: trợ giúp | exit: lưu và thoát')


def save_history(history: dict[str, Any], directory: Path | None = None) -> Path:
    directory = directory if directory is not None else Path(__file__).resolve().parent / 'chat_history'
    directory.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')
    target = directory / f'session_{timestamp}_{uuid.uuid4().hex}.json'
    payload = json.dumps(history, ensure_ascii=False, indent=2)
    with target.open('x', encoding='utf-8') as output:
        output.write(payload)
    return target


async def main(*, persist: bool = False, history_dir: Path | None = None) -> dict[str, Any]:
    session = ChatSession()
    directory = Path(history_dir) if history_dir is not None else Path(__file__).resolve().parent/'chat_history'
    messages = []
    started_at = datetime.now(timezone.utc).isoformat()
    continuation = {}
    dirty = False

    def document() -> dict:
        return {'schema_version': '1.0', 'session_id': session.session_id, 'started_at': started_at,
                'saved_at': datetime.now(timezone.utc).isoformat(), 'messages': copy.deepcopy(messages),
                'reference_date': session.today.isoformat(), **continuation}

    def save_pending() -> bool:
        nonlocal dirty
        if not persist or not dirty or not messages:
            return True
        try:
            target = save_history(document(), directory)
        except OSError as error:
            print(f'\nLỗi lưu lịch sử: {error}')
            return False
        print(f'\nĐã lưu lịch sử: {target}')
        dirty = False
        return True

    print('Tra cứu tài chính — dữ liệu giả lập, chưa có số liệu thật.')
    print('Gõ /help để xem lệnh; /lichsu để mở phiên cũ; exit để lưu và thoát.')
    try:
        while True:
            try:
                text = input('\nBạn: ').strip()
            except (EOFError, KeyboardInterrupt):
                break
            if not text:
                continue
            command = text.lower()
            if command in ('exit', 'quit', 'thoat', 'thoát'):
                break
            if command == '/help':
                print(HELP)
            elif command == '/tomtat':
                print(session.context_summary())
            elif command == '/json':
                result = session.last_result
                print(json.dumps(result, ensure_ascii=False, indent=2) if result else 'Chưa có kết quả trong phiên này.')
            elif command == '/lichsu':
                try:
                    entries = list_histories(directory)
                    if not entries:
                        print('Chưa có lịch sử hợp lệ trong thư mục này.')
                    for index, entry in enumerate(entries, 1):
                        print(f"{index}. {entry['name']} | {entry['saved_at']} | {entry['turns']} lượt | {entry['preview']}")
                except (ValueError, OSError) as error:
                    print(f'Không đọc được danh sách lịch sử: {error}')
            elif command == '/mo' or command.startswith('/mo '):
                selector = text[3:].strip()
                try:
                    if not selector:
                        raise ValueError('Dùng /mo 1 hoặc /mo ten_file.json.')
                    name = selector
                    if selector.isdigit():
                        entries = list_histories(directory)
                        index = int(selector)
                        if not 1 <= index <= len(entries):
                            raise ValueError('Số thứ tự phiên không hợp lệ. Gõ /lichsu để xem danh sách.')
                        name = entries[index-1]['name']
                    previous = load_history(name, directory)
                    replacement = await restore_session(previous)
                except (ValueError, OSError) as error:
                    print(f'Không mở được phiên: {error}')
                    continue
                if not save_pending():
                    print('Giữ nguyên phiên hiện tại vì chưa lưu được phần chat đang dở.')
                    continue
                session = replacement
                messages = copy.deepcopy(previous['messages'])
                started_at = previous['started_at']
                continuation = {'resumed_from': name, 'parent_session_id': previous['session_id'],
                                'continued_at': datetime.now(timezone.utc).isoformat()}
                dirty = False
                print(f'Đã mở phiên {name}.')
                print(session.context_summary())
            elif command == '/moi':
                messages.append({'role': 'user', 'content': text,
                                 'timestamp': datetime.now(timezone.utc).isoformat(),
                                 'reference_date': session.today.isoformat()})
                session.reset()
                response = 'Đã xóa ngữ cảnh, bắt đầu câu hỏi mới.'
                messages.append({'role': 'assistant', 'content': response,
                                 'timestamp': datetime.now(timezone.utc).isoformat()})
                dirty = True
                print('Trợ lý: '+response)
            elif text.startswith('/'):
                print('Lệnh chưa được hỗ trợ. Gõ /help để xem hướng dẫn.')
            else:
                messages.append({'role': 'user', 'content': text,
                                 'timestamp': datetime.now(timezone.utc).isoformat(),
                                 'reference_date': session.today.isoformat()})
                dirty = True
                result = await session.ask(text)
                response = render_response(result)
                messages.append({'role': 'assistant', 'content': response, 'result': result,
                                 'timestamp': datetime.now(timezone.utc).isoformat()})
                print('Trợ lý: '+response)
    finally:
        save_pending()
    return document()


if __name__ == '__main__':
    try:
        asyncio.run(main(persist=True))
    except KeyboardInterrupt:
        print('\nĐã thoát.')
