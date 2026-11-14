import json
import re
from collections import Counter
from pathlib import Path

root=Path(r'D:\finmind\data\references\vietstock\annual_reports\ocr_standard')
draft=Path(r'D:\finmind\tmp\ocr-review')
rel='ELC/2025/ELC_2025_541948'
common={
    'CÔNG TY CO PHAN':'CÔNG TY CỔ PHẦN', 'CONG TY CÔ PHAN':'CÔNG TY CỔ PHẦN',
    'CÔNG TY CÔ PHÀN':'CÔNG TY CỔ PHẦN', 'VIỄN THONG':'VIỄN THÔNG',
    'Téa nha':'Tòa nhà', 'Tòa nha':'Tòa nhà', 'Toa nhà':'Tòa nhà', 'Eleom':'Elcom',
    'Câu Giấy':'Cầu Giấy', 'phó Duy Tân':'phố Duy Tân', 'Thành phó':'Thành phố',
    'Thành phô':'Thành phố', 'Thông tư s6':'Thông tư số', 'TT- BTC':'TT-BTC',
    'BẢN THUYET MINH BAO CÁO':'BẢN THUYẾT MINH BÁO CÁO',
    'BAN THUYET MINH BAO CÁO':'BẢN THUYẾT MINH BÁO CÁO',
    'BAN THUYET MINH BÁO CÁO':'BẢN THUYẾT MINH BÁO CÁO',
    'TÀI CHÍNH HỢP NHAT':'TÀI CHÍNH HỢP NHẤT',
    'TAI CHÍNH HỢP NHAT':'TÀI CHÍNH HỢP NHẤT',
    'CÁC CHỈNH SÁCH KE TOÁN AP DỤNG':'CÁC CHÍNH SÁCH KẾ TOÁN ÁP DỤNG',
    'CÁC CHÍNH SÁCH KẺ TOÁN ÁP DỤNG':'CÁC CHÍNH SÁCH KẾ TOÁN ÁP DỤNG',
    'CÁC CHÍNH SÁCH KE TOÁN ÁP DỤNG':'CÁC CHÍNH SÁCH KẾ TOÁN ÁP DỤNG',
    'Chỉ phí':'Chi phí', 'chỉ phí':'chi phí', 'ghỉ nhận':'ghi nhận',
    'đoanh thu':'doanh thu', 'Đoanh thu':'Doanh thu',
    'chi phi':'chi phí', 'ky kế toán':'kỳ kế toán', 'trong ky':'trong kỳ',
    'bảo hành':'bảo hành', 'bao hành':'bảo hành',
    'cỗ đông':'cổ đông', 'cỗ phiếu':'cổ phiếu', 'cô phiếu':'cổ phiếu',
    'phô thông':'phổ thông', 'lưu hanh':'lưu hành',
}
specific={
    75:{
        'dé đâm bảo':'để đảm bảo','đột biển':'đột biến','cơ sở hạ tang':'cơ sở hạ tầng',
        'cung cap':'cung cấp','nhiều kỷ':'nhiều kỳ','phân bỏ':'phân bổ',
        'nợ phải tra':'nợ phải trả','cổ phiêu':'cổ phiếu','ngan hạn va dai hạn':'ngắn hạn và dài hạn',
        'tài sản đở dang':'tài sản dở dang','Chuan mực':'Chuẩn mực','Bảo cáo':'Báo cáo',
        'von hóa':'vốn hóa','tiên sẽ phải chỉ':'tiền sẽ phải chi','kế toán nấm':'kế toán năm',
        'ban dau':'ban đầu','bù dap':'bù đắp','sân xuất, kinh đoanh':'sản xuất, kinh doanh',
        'dy phỏng':'dự phòng','xây lap':'xây lắp','vễn thực góp':'vốn thực góp',
        'Thang đư vốn cé phan':'Thặng dư vốn cổ phần','lan dau':'lần đầu',
        'k     el as':'','phan phối':'phân phối','Hội đồng cỗ đông':'Hội đồng cổ đông',
        'tắt cả':'tất cả','diéu kién':'điều kiện','chuyên giao':'chuyển giao',
        'gan liên':'gắn liền','quyển':'quyền','giao dich':'giao dịch',
        'Doanh thụ ban hàng':'Doanh thu bán hàng','Đối với doanh thu cung cap dịch vụ':'Đối với doanh thu cung cấp dịch vụ',
        'két qua':'kết quả','giao địch':'giao dịch','ghỉ nhận':'ghi nhận',
        'phan công việc':'phần công việc','hoan thành':'hoàn thành',
        'Bang cân':'Bảng cân','đói kế toán':'đối kế toán',
        'bến (4)':'bốn (4)','tương. đối':'tương đối','dich vụ':'dịch vụ',
        'chỉ phí':'chi phí','có tức':'cổ tức','địch vụ':'dịch vụ',
        'hang tháng':'hàng tháng',
    },
    76:{
        'thu nhập đoanh nghiệp':'thu nhập doanh nghiệp','lỗ cña':'lỗ của',
        'lợi nhuận ké toán':'lợi nhuận kế toán','là đo điều chỉnh':'là do điều chỉnh',
        'nộp thuê':'nộp thuế','thuê thu nhập':'thuế thu nhập','hiện  hành ve':'hiện hành về',
        'thay đôi':'thay đổi','sau củng':'sau cùng','kiêm tra':'kiểm tra','thấm quyền':'thẩm quyền',
        'đáng kẻ':'đáng kể','bén kia':'bên kia','tai chính':'tài chính',
        'mỗi quan hệ':'mối quan hệ','liền quan':'liên quan','hình thúc':'hình thức',
        'có thé':'có thể','6ô phận seo lĩnh TựC kinh doanh':'bộ phận theo lĩnh vực kinh doanh',
        'cung cap':'cung cấp','cụ thé':'cụ thể','bộ phan':'bộ phận',
        'Tổng Giảm déc':'Tổng Giám đốc','tr rong':'trong',
        'fa sản xuất':'là sản xuất','bat động sản':'bất động sản',
        'cho thué':'cho thuê','cho thưê ha':'cho thuê hạ','đào tgo,...}':'đào tạo,...)',
        'THONG TIN BO SUNG':'THÔNG TIN BỔ SUNG','TRINH BAY TREN BANG CAN DOI KE TOÁN':'TRÌNH BÀY TRÊN BẢNG CÂN ĐỐI KẾ TOÁN',
        'HOP NHAT':'HỢP NHẤT','Sill.':'5.1.','các khoắn':'các khoản',
        'Tién mat':'Tiền mặt','ngân hang':'ngân hàng','Các khoân':'Các khoản',
        'ky hạn':'kỳ hạn','thương mai':'thương mại','Don vị tinh':'Đơn vị tính',
        'Giá trịghisổ':'Giá trị ghi sổ','Giá trị ghỉ số':'Giá trị ghi sổ',
        'Ngắn han':'Ngắn hạn','— 14.890.000.000 — 114.890.000.000':'— 114.890.000.000 — 114.890.000.000',
        '6,2%/ndm':'6,2%/năm','33.     Phai thu khach hang':'5.3. Phải thu khách hàng',
        '627.626.911,601':'627.626.911.601','Phải tha khúch hang':'Phải thu khách hàng',
        '397.770.779':'597.770.779','v: an dang':'vẫn đang',
        'nảy':'này','lễ trình':'lộ trình','cam Kết':'cam kết',
    },
}
manifest=root/'assisted_visual_review.json'
data=json.loads(manifest.read_text(encoding='utf-8')) if manifest.exists() else {'basis':'Visual review of rendered PDF, with Tesseract vie+eng draft corrected against page image','entries':[]}
doc=root/rel
rows=[json.loads(s) for s in (doc/'pages.jsonl').read_text(encoding='utf-8').splitlines()]
for page in (75,76):
    text='\n\n'.join((draft/f'ELC-2025-{page:03d}-part{i}.txt').read_text(encoding='utf-8').strip() for i in (1,2))
    for old,new in common.items(): text=text.replace(old,new)
    for old,new in specific[page].items(): text=text.replace(old,new)
    text=re.sub(r'\n{3,}','\n\n',text).strip()
    row=next(r for r in rows if r['page']==page)
    assert row['status']=='REVIEW' and 'GEMINI_FAILED' in row.get('flags',[])
    row.update(text=text,status='OK',flags=['VISUAL_REVIEWED_TESSERACT_ASSISTED'])
    row['manualReview']={'source':'ocr_standard/assisted_visual_review.json','basis':'rendered_pdf_page_tesseract_assisted'}
    row.pop('splitOcr',None)
    (doc/'text'/f'p-{page:03d}.txt').write_text(text+'\n',encoding='utf-8')
    data['entries'].append({'document':rel,'page':page,'text':text})
    print(page,len(text))
manifest.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
(doc/'pages.jsonl').write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in rows),encoding='utf-8')
summary_path=doc/'summary.json';summary=json.loads(summary_path.read_text(encoding='utf-8'))
summary['status']=dict(Counter(r['status'] for r in rows))
summary['flags']=dict(Counter(f for r in rows for f in r.get('flags',[])))
summary['reviewPages']=[r['page'] for r in rows if r['status']=='REVIEW']
summary_path.write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
