import re, sys
sys.stdout.reconfigure(encoding='utf-8')
from pathlib import Path

content = Path('Golden_TestSet_Lo1_Lo2_TinTuc_GiaCoPhieu.md').read_text(encoding='utf-8')
lines = content.splitlines()

print("=== CHECKING FORBIDDEN TICKERS IN QUESTIONS (Q01 - Q40) ===")
in_q_block = False
cur_q = ""
for idx, line in enumerate(lines, 1):
    if line.startswith("### Q"):
        cur_q = line.strip()
    if cur_q and not line.startswith("## "):
        for ticker in ["CTR", "MSN", "NLG"]:
            # Chỉ cảnh báo nếu không phải là dòng giải trình loại bỏ
            if ticker in line and "thay thế" not in line.lower() and "loại bỏ" not in line.lower():
                print(f"Line {idx} [{cur_q}]: {line.strip()}")

print("\n=== CHECKING VIRTUAL PATH 'supabase_export' ===")
for idx, line in enumerate(lines, 1):
    if "supabase_export" in line and "loại bỏ" not in line.lower():
        print(f"Line {idx}: {line.strip()}")
