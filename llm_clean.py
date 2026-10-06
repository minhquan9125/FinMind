#!/usr/bin/env python3
"""Clean OCR text with Gemini while validating every proposed line.

Per page:
  1. Apply deterministic cleanup with clean_pipeline.step1 and crosscheck_docno.
  2. Send numbered line groups to Gemini for cautious OCR correction.
  3. Validate each corrected line with kiem_tra_llm.validate_line.
  4. Keep the original line and add a flag whenever validation fails.

The input text_raw is never modified. Set GEMINI_API_KEY in the environment.
Run:
  python llm_clean.py --input data.jsonl --out llm_clean.jsonl --limit 3
"""

import argparse
import json
import os
import re
import time

from google import genai
from google.genai import types

from clean_pipeline import step1, crosscheck_docno
from kiem_tra_llm import validate_line


SYSTEM = """Bạn sửa lỗi OCR cho văn bản hành chính, tài chính tiếng Việt.
Văn bản có thể mất dấu và mất một số chữ cái có dấu (ví dụ 'CNG HOÀ X HI' là 'CỘNG HOÀ XÃ HỘI').
Quy tắc:
1. Mỗi dòng đầu vào dạng 'n| nội dung'. Trả về đúng một dòng cho mỗi số n, cùng định dạng 'n| nội dung'.
2. Chỉ khôi phục chữ cái và dấu bị mất khi chắc chắn. Không thêm, bớt, hoặc đổi thứ tự từ. Không dịch.
3. Giữ nguyên dòng tiếng Anh, mọi chữ số, ngày tháng, mã số, URL và email.
4. Nếu không chắc một từ, đặc biệt tên riêng, giữ nguyên từ đó, không đoán.
5. Chỉ trả về các dòng đã đánh số, không giải thích."""


def call(client, model, lines, retries=3):
    body = "\n".join("%d| %s" % (i + 1, line) for i, line in enumerate(lines))
    for attempt in range(retries):
        try:
            response = client.models.generate_content(
                model=model,
                contents=body,
                config=types.GenerateContentConfig(
                    system_instruction=SYSTEM,
                    temperature=0,
                    max_output_tokens=3000,
                ),
            )
            return response.text or ""
        except Exception as exc:
            print("  lỗi Gemini API (lần %d): %s" % (attempt + 1, exc))
            if attempt + 1 < retries:
                time.sleep(2**attempt)
    return ""


def clean_page(client, model, text_raw, chunk=25):
    items = step1(text_raw)
    crosscheck_docno(items)
    raw_lines = [line for line, _ in items]
    flags = [
        "%d: %s" % (i + 1, flag)
        for i, (_, line_flags) in enumerate(items)
        for flag in line_flags
    ]
    output_lines = []

    for start in range(0, len(raw_lines), chunk):
        part = raw_lines[start : start + chunk]
        reply = call(client, model, part)
        corrected = {
            int(match.group(1)): match.group(2)
            for match in re.finditer(r"^\s*(\d+)\|\s?(.*)$", reply, re.M)
        }

        for local_index, original in enumerate(part, start=1):
            new_line = corrected.get(local_index)
            global_index = start + local_index
            if new_line is None:
                output_lines.append(original)
                flags.append("%d: Gemini thiếu dòng" % global_index)
                continue

            problems = validate_line(original, new_line)
            if problems:
                output_lines.append(original)
                flags.append(
                    "%d: bỏ kết quả Gemini (%s)"
                    % (global_index, "; ".join(problems))
                )
            else:
                output_lines.append(new_line)

    return "\n".join(output_lines), flags


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--model", default="gemini-3.8-flash")
    parser.add_argument("--limit", type=int)
    args = parser.parse_args()

    if not os.environ.get("GEMINI_API_KEY"):
        raise SystemExit("Chưa đặt biến môi trường GEMINI_API_KEY")

    client = genai.Client()
    count = 0
    with open(args.input, encoding="utf-8") as source, open(
        args.out, "w", encoding="utf-8"
    ) as target:
        for line in source:
            if not line.strip():
                continue
            record = json.loads(line)
            text, flags = clean_page(client, args.model, record["text_raw"])
            record.update({"text_llm": text, "flags": flags})
            target.write(json.dumps(record, ensure_ascii=False) + "\n")
            target.flush()
            count += 1
            print(
                "xong trang %s/%s (%d cờ)"
                % (record.get("doc_id"), record.get("page_no"), len(flags))
            )
            if args.limit and count >= args.limit:
                break


if __name__ == "__main__":
    main()
