"""Interactive B1 demo; Gemini is opt-in and credentials stay in memory."""
import argparse
import asyncio
import getpass
import json
import os
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from src.b1_answering.providers.gemini import GeminiError, GeminiProvider
from src.b1_answering.core.policy import Budget, Limits, PolicyError
from src.b1_answering.application.service import complete_retrieval

DEMO_PASSAGE = '[DỮ LIỆU MẪU] Chỉ tiêu minh họa có giá trị 123 đơn vị mẫu; không phải số liệu tài chính thật.'
DEMO_PACK = {'schema_version': '1.0', 'query_id': 'fixture-demo-query',
             'data_version': {'kind': 'INDEX', 'id': 'fixture-demo-v1'},
             'items': [{'evidence_id': 'demo-e1', 'source_id': 'fixture-demo-document',
                        'chunk_id': 'fixture-demo-chunk', 'source_sha256': 'a' * 64,
                        'passage': DEMO_PASSAGE, 'locator': {'table_id': 'fixture-demo-table'}}]}


class FixtureProvider:
    def __init__(self, limits):
        self.limits = limits

    async def count_tokens(self, request):
        return len(json.dumps(request, ensure_ascii=False).encode('utf-8'))  # Offline conservative bound only.

    async def generate(self, request):
        evidence = json.loads(request['contents'][0]['parts'][0]['text'])['evidence']
        payload = {'claims': [{'text': item['passage'], 'evidence_ids': [item['evidence_id']]} for item in evidence]}
        inp, output = await self.count_tokens(request), len(json.dumps(payload, ensure_ascii=False).encode('utf-8'))
        return {'payload': payload, 'usage': {'input_tokens': inp, 'output_tokens': output, 'total_tokens': inp + output},
                'model_version': 'fixture-only'}


def display(result, as_json=False):
    if as_json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return
    answer = result['answering']
    if answer['status'] == 'SKIPPED':
        from src.retrieval_orchestration.retrieval_flow.conversation import render_response
        print(render_response(result))
        return
    print(answer['draft'] or answer['message'])
    if not answer['draft']:
        print('Lý do:', answer['reason_code'])
    for citation in answer['citations']:
        print(f"  [{citation['evidence_id']}] {citation['source_id']} | vị trí: {json.dumps(citation['locator'], ensure_ascii=False)}")


async def run_cli(args):
    limits = Limits.load()
    budget = Budget(limits)
    banner = sys.stderr if args.json else sys.stdout
    if args.live:
        key = os.environ.get('GEMINI_API_KEY')
        if not key and sys.stdin.isatty():
            key = getpass.getpass('Nhập Gemini API key (không hiển thị, không lưu): ')
        provider = GeminiProvider(limits, api_key=key, free_tier_confirmed=True)
        print('Gemini Flash-Lite — project Free Tier đã xác nhận; retrieval vẫn dùng dữ liệu mẫu.', file=banner)
    else:
        provider = FixtureProvider(limits)
        print('OFFLINE — dữ liệu mẫu, không phải số liệu thật; không gọi API.', file=banner)
    if args.example:
        result = {'status': 'EVIDENCE_READY', 'execution_mode': 'FIXTURE', 'evidence_pack': DEMO_PACK}
        display(await complete_retrieval(args.question or 'Chỉ tiêu minh họa?', result, provider=provider, limits=limits, budget=budget), args.json)
        return
    from src.b1_answering.application.dialogue import DialogueSession
    session = DialogueSession()
    if args.question is None:
        print('Nhập câu hỏi; /moi để bắt đầu lại, exit để thoát.')
        print('Ví dụ fixture có sẵn: Tổng tài sản BID tại 30/06/2026 là bao nhiêu?')
    while True:
        try:
            text = args.question if args.question is not None else input('Bạn: ').strip()
        except (EOFError, KeyboardInterrupt):
            return
        if text.lower() in ('exit', 'quit'):
            return
        if text == '/moi':
            session.reset()
            print('Đã bắt đầu hội thoại mới; ngân sách của tiến trình vẫn được giữ.')
            if args.question is not None:
                return
            continue
        if text.strip():
            result = await session.ask(text)
            display(await complete_retrieval(text, result, provider=provider, limits=limits, budget=budget), args.json)
        if args.question is not None:
            return


def main():
    parser = argparse.ArgumentParser(description='Thử B1 với dữ liệu mẫu hoặc Gemini Flash-Lite.')
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument('--live', action='store_true', help='Gọi Gemini trên project Free Tier đã xác nhận.')
    mode.add_argument('--demo', action='store_true', help='Offline (mặc định).')
    parser.add_argument('--example', action='store_true', help='Chạy một ví dụ có số liệu hoàn toàn giả lập rồi thoát.')
    parser.add_argument('--question', help='Hỏi một câu rồi thoát.')
    parser.add_argument('--json', action='store_true', help='In envelope/manifest/trace đầy đủ.')
    try:
        asyncio.run(run_cli(parser.parse_args()))
    except (GeminiError, PolicyError) as exc:
        print('Không thể chạy:', exc.code, file=sys.stderr)
        return 2
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
