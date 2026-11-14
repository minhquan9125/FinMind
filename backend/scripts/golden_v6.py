"""Read the proposed Golden40 v6 questions without treating draft answers as gold."""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_GOLDEN = ROOT / "Golden_TestSet_Lo1_Lo2_TinTuc_GiaCoPhieu.md"

KINDS = {
    "Tìm đoạn bằng vector": "vector",
    "Truy vấn số liệu + tính toán": "calculation",
    "Tra cứu phiên giá": "price_row",
    "Từ chối khi thiếu bằng chứng": "refusal",
}


def load_golden_v6(path=DEFAULT_GOLDEN):
    content = Path(path).read_text(encoding="utf-8")
    if not content.startswith("# Golden40 v6"):
        raise ValueError("Expected Golden40 v6; do not mix this audit with older answers")

    headings = list(re.finditer(r"(?m)^### Q(\d{2}) — ([^\r\n]+)$", content))
    numbers = [int(match.group(1)) for match in headings]
    if numbers != list(range(1, 41)):
        raise ValueError("Golden40 v6 must contain Q01–Q40 exactly once and in order")

    questions = []
    for position, heading in enumerate(headings):
        body_end = headings[position + 1].start() if position + 1 < len(headings) else content.find(
            "\n## ", heading.end()
        )
        body = content[heading.end():body_end if body_end != -1 else None]
        question = re.search(r"(?m)^\*\*Câu hỏi đã sửa:\*\* ([^\r\n]+)$", body)
        if question is None:
            raise ValueError(f"Q{numbers[position]:02d} has no revised question")
        kind_label = heading.group(2).strip()
        if kind_label not in KINDS:
            raise ValueError(f"Q{numbers[position]:02d} has an unknown test kind")
        questions.append({
            "id": f"Q{numbers[position]:02d}",
            "number": numbers[position],
            "kind": KINDS[kind_label],
            "question": question.group(1),
        })
    return questions
