"""Export one chat session for the user: a sourced summary plus every question and answer, as TXT or JSON.

The summary reuses summarize_session (saved, sourced answers only; nothing is generated again).
Internal ids, hashes and evidence packs never leave the server.
"""
from datetime import datetime, timedelta, timezone

from .conversation_summary import summarize_session

VIETNAM = timezone(timedelta(hours=7))
DISCLAIMER = ('Chỉ hỗ trợ nghiên cứu · Không phải khuyến nghị đầu tư. Thông tin chỉ để tham khảo, nghiên cứu. '
              'Chúng tôi không chịu trách nhiệm về quyết định đầu tư của bạn.')
RESET = ('/new', '/moi')


def _local(stamp):
    try:
        return datetime.fromisoformat(stamp).astimezone(VIETNAM).strftime('%d/%m/%Y %H:%M')
    except (TypeError, ValueError):
        return None


def _sources(citations):
    sources = []
    for index, cite in enumerate(citations or [], 1):
        locator = cite.get('locator') or {}
        sources.append({'number': cite.get('citation_number', index), 'title': cite.get('title') or 'Nguồn',
                        'url': locator.get('url') or locator.get('source_url') or cite.get('url')})
    return sources


def build_export(doc, now=None):
    now = (now or datetime.now(timezone.utc)).astimezone(VIETNAM)
    turns, companies, question = [], [], None
    for message in doc.get('messages') or []:
        if message.get('role') == 'user':
            question = None if message.get('content', '').strip().lower() in RESET else message
        elif message.get('role') == 'assistant' and question is not None:
            result = message.get('result') or {}
            for company in (result.get('scope') or {}).get('companies') or []:
                if company not in companies:
                    companies.append(company)
            turns.append({'asked_at': _local(question.get('timestamp')), 'question': question.get('content', ''),
                          'answer': message.get('content', ''),
                          'sources': _sources((result.get('answering') or {}).get('citations'))})
            question = None
    try:
        summary = summarize_session(doc)
        answer = summary.get('answering') or {}
        summary_text, summary_sources = answer.get('draft') or summary.get('message'), _sources(answer.get('citations'))
    except Exception:  # a summary failure must not block downloading the conversation itself
        summary_text, summary_sources = 'Chưa tạo được phần tóm tắt cho phiên này.', []
    return {'title': 'FinMind – Tóm tắt hội thoại', 'exported_at': now.strftime('%d/%m/%Y %H:%M'),
            'companies': companies, 'turn_count': len(turns),
            'summary': {'text': summary_text, 'sources': summary_sources},
            'turns': turns, 'disclaimer': DISCLAIMER}


def _source_lines(sources, indent=''):
    return [f'{indent}[{s["number"]}] {s["title"]}' + (f' — {s["url"]}' if s['url'] else '') for s in sources]


def render_txt(data):
    rule = '=' * 72
    head = f'Xuất lúc: {data["exported_at"]} · {data["turn_count"]} lượt hỏi đáp'
    if data['companies']:
        head += ' · Doanh nghiệp: ' + ', '.join(data['companies'])
    lines = [data['title'].upper(), head, rule, 'I. TÓM TẮT', '', data['summary']['text'] or '']
    if data['summary']['sources']:
        lines += ['', 'Nguồn của phần tóm tắt:', *_source_lines(data['summary']['sources'])]
    lines += ['', rule, 'II. CHI TIẾT HỎI ĐÁP', '']
    for number, turn in enumerate(data['turns'], 1):
        when = f'[{turn["asked_at"]}] ' if turn['asked_at'] else ''
        lines += [f'{number}. {when}Hỏi: {turn["question"]}', '   Trả lời:',
                  *('   ' + line for line in (turn['answer'] or '').splitlines())]
        if turn['sources']:
            lines += ['   Nguồn:', *_source_lines(turn['sources'], '   ')]
        lines.append('')
    lines += [rule, data['disclaimer']]
    return '\n'.join(lines) + '\n'
