"""Golden question set for the admin Evaluation page, read from the team's markdown file.

Two layouts exist in the repo; both are accepted:
  - "- **Câu hỏi**: ..." / "- **Đáp án chuẩn**: ..." with "✅ Đã xác thực" (answers verified against sources)
  - "**Câu hỏi đã sửa:** ..." / "**Đáp án v5 để đối chiếu, chưa duyệt lại:** ..." (answers not approved)
A question is `verified` only when its block carries the check mark.
"""
from __future__ import annotations

import re
from pathlib import Path

GOLDEN_FILE = 'bo cau hoi cua huyen 40 cau.md'
FALLBACK_FILE = 'Golden_TestSet_Lo1_Lo2_TinTuc_GiaCoPhieu.md'

_HEAD = re.compile(r'^### (Q\d+)[ \t]*(?:[—-][ \t]*)?(.*)$', re.M)
_QUESTION = re.compile(r'^\s*(?:-\s*)?\*\*Câu hỏi[^*\n]*\*\*:?\s*(.+)$', re.M)
_ANSWER = re.compile(r'^\s*(?:-\s*)?\*\*Đáp án[^*\n]*\*\*:?\s*(.+)$', re.M)
_CATEGORY = re.compile(r'^\*Phân loại:\s*(.+?)\*\s*$', re.M)


def _clean(text):
    return re.sub(r'\s+', ' ', text.replace('`', '').replace('**', '')).strip()


def parse_golden(text):
    """List of {id, label, category, question, expected, verified}; blocks without both parts are skipped."""
    text = text.replace('\r\n', '\n')
    heads = list(_HEAD.finditer(text))
    items = []
    for index, head in enumerate(heads):
        block = text[head.end(): heads[index + 1].start() if index + 1 < len(heads) else len(text)]
        question, answer = _QUESTION.search(block), _ANSWER.search(block)
        if not question or not answer:
            continue
        category = _CATEGORY.search(block)
        items.append({
            'id': head.group(1), 'label': head.group(2).strip(' ()') or None,
            'category': _clean(category.group(1)) if category else None,
            'question': _clean(question.group(1)), 'expected': _clean(answer.group(1)),
            'verified': '✅' in block,
        })
    return items


def golden_path(root=None):
    base = Path(root) if root else Path(__file__).resolve().parents[3]
    for name in (GOLDEN_FILE, FALLBACK_FILE):
        if (base / name).is_file():
            return base / name
    return None


def load_golden(root=None):
    path = golden_path(root)
    return parse_golden(path.read_text(encoding='utf-8')) if path else []
