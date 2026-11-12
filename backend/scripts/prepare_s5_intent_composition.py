"""Freeze a diagnostic contrast set before running clause composition."""
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
DATA=ROOT/'docs/sprint5/intent-composition-v1'


def main():
    if DATA.exists(): raise FileExistsError(DATA)
    patterns=[('ROLE','Theo báo cáo thường niên {c} năm 2021, ai đảm nhiệm chức Chủ tịch HĐQT?', 'PERSON_ROLE'),
              ('REPORT','Báo cáo thường niên {c} năm 2021 giải thích chính sách kiểm soát rủi ro ra sao?', 'REPORT_CONTENT'),
              ('COMBINED','Theo báo cáo thường niên {c} năm 2021, ai đảm nhiệm chức Chủ tịch HĐQT? Báo cáo giải thích chính sách kiểm soát rủi ro ra sao?', 'MIXED'),
              ('EVIDENCE','Theo báo cáo thường niên {c} năm 2021, ai đảm nhiệm chức Chủ tịch HĐQT? Trích câu làm bằng chứng cho câu trả lời.', 'PERSON_ROLE')]
    rows=[]
    for kind,text,label in patterns:
        for company in ['VCB','MBB','FPT','VNM','SAB','HDB']:
            rows.append(dict(id=f'CONTROL-{kind}-{company}',text=text.format(c=company),intent_label=label,
                family_id='CONTROL-'+kind,company=company,kind=kind,split='DIAGNOSTIC_ONLY'))
    edges=[('Doanh thu và lợi nhuận sau thuế VNM năm 2021 là bao nhiêu?', 'NUMERIC'),
           ('Ai là Tổng giám đốc VNM và ai là Giám đốc tài chính VNM cuối năm 2021?', 'PERSON_ROLE'),
           ('Trích nguyên văn chính sách quản trị rủi ro trong BCTN SAB 2021.', 'REPORT_CONTENT'),
           ('Tìm bài tin bổ nhiệm Chủ tịch HDB tháng 07/2021 rồi dẫn nguồn cho câu trả lời.', 'NEWS'),
           ('Doanh thu SAB năm 2021 là bao nhiêu? Giá đóng cửa SAB phiên 03/08/2021 là bao nhiêu?', 'NUMERIC'),
           ('Xác định công ty con VNM cuối năm 2021 rồi cho biết doanh thu năm 2021 của từng công ty.', 'MIXED'),
           ('Đánh giá chung chiều hướng giá và ROA HDB trong giai đoạn 2018–2021.', 'TREND'),
           ('Ai được bổ nhiệm làm KTT SAB cuối năm 2021? Trích câu làm bằng chứng cho câu trả lời; KTT = kế toán trưởng.', 'PERSON_ROLE')]
    rows += [dict(id=f'EDGE-{i:02}',text=text,intent_label=label,family_id=f'EDGE-{i:02}',
                 kind='EDGE',split='DIAGNOSTIC_ONLY') for i,(text,label) in enumerate(edges,1)]
    DATA.mkdir()
    raw=''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in rows).encode('utf-8')
    (DATA/'controls.jsonl').write_bytes(raw)
    (DATA/'manifest.json').write_text(json.dumps(dict(version='intent-composition-controls-v1',rows=len(rows),
          authored_by_same_agent=True,blind_test=False,fit_allowed=False,source_sha256=hashlib.sha256(raw).hexdigest()),indent=2)+'\n',encoding='utf-8',newline='\n')
    print('Frozen diagnostic controls:',len(rows))


if __name__=='__main__': main()
