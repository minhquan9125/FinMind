import re

with open('Golden_TestSet_Lo1_Lo2_TinTuc_GiaCoPhieu.md', 'r', encoding='utf-8') as f:
    text = f.read()

approved = {'VCB', 'BID', 'CTG', 'MBB', 'TCB', 'FPT', 'CMG', 'ELC', 'ITD', 'ICT'}

# Tìm tất cả các từ viết hoa 3 chữ cái
words = set(re.findall(r'\b[A-Z]{3}\b', text))
stock_candidates = {w for w in words if w not in {'VND', 'USD', 'BCT', 'CFO', 'EPS', 'ROE', 'VAS', 'NIM', 'LDR', 'API', 'PDF', 'SRS', 'RAG', 'HĐQ', 'CCDV', 'TOP', 'SHA', 'CĐK', 'KQKD', 'LCTT', 'VCSH', 'CĐC', 'HOSE', 'HNX'}}

print('Stock candidates in text:', stock_candidates)
for s in stock_candidates:
    is_app = s in approved
    print(f"  {s}: {'APPROVED' if is_app else 'OUT OF SCOPE'}")
