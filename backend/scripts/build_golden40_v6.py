"""Create a reviewable Golden40 proposal; never overwrite the supplied v5 file."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[2]
INDEX = '434ef5e0-6516-578d-8d18-721d21347e01'

QUESTIONS = [
'Theo bài FireAnt ngày 01/10/2026 về Techcombank (TCB), hai lô trái phiếu được tất toán trước hạn có mã gì, giá trị từng lô và tổng giá trị được bài viết nêu là bao nhiêu?',
'Theo bài FireAnt ngày 01/10/2026 về lãi suất VietinBank (CTG), bài viết nêu khách gửi 300 triệu đồng kỳ hạn 24 tháng có thể nhận khoảng bao nhiêu tiền lãi và áp dụng mức lãi suất nào? Chỉ trích thông tin bài viết đã nêu, không tính một sản phẩm tiết kiệm khác.',
'Theo bài CafeF ngày 29/09/2026 về đợt tăng vốn FPT, số cổ phiếu đã phân phối, số cổ đông nhận cổ phiếu và ngày kết thúc phát hành được nêu là bao nhiêu?',
'Theo bài FireAnt ngày 29/09/2026, số lượng cổ đông FPT và tỷ lệ sở hữu của khối ngoại tại thời điểm bài viết là bao nhiêu?',
'Theo bản tin dẫn SSI Research ngày 29/09/2026, CTG và VCB được dự báo lợi nhuận trước thuế quý 3/2026 lần lượt bao nhiêu? Đây là dự báo hay kết quả đã thực hiện?',
'Theo bài FireAnt ngày 30/09/2026, quy mô tổng tài sản của MBB và số doanh nghiệp thành viên trong hệ sinh thái được bài viết nêu là bao nhiêu?',
'Theo bản tin FireAnt ngày 14/10/2026, Techcombank nhận được chấp thuận về nội dung gì và cơ quan nào chấp thuận? Nếu bài không nêu rõ cơ quan thì không suy đoán.',
'Theo bài CafeF ngày 05/08/2026 về Vietcombank Tower, bài viết nêu Vietcombank chi bao nhiêu tiền? Phân biệt giao dịch tăng sở hữu từ 52% lên 70% với thông tin chủ sở hữu 100% tại thời điểm đăng ký doanh nghiệp được dẫn trong bài.',
'Theo bài CafeF dẫn TCBS Research ngày 28/09/2026, trợ lý lập trình AI của FPT cải thiện tốc độ viết mã bao nhiêu phần trăm và năng suất toàn dự án bao nhiêu phần trăm? Nêu đúng hai cấp độ đo.',
'Theo bài CafeF ngày 13/10/2026, tại 30/09/2026 nhân sự toàn hệ sinh thái FPT xấp xỉ bao nhiêu người và tăng thêm bao nhiêu so với cuối năm 2025? Không dùng nhân sự các đơn vị hợp nhất thay tổng hệ sinh thái.',
'Trong bản giá ENTRADE đã đóng băng của VCB, lấy giá đóng cửa tại đúng hai ngày 02/01/2018 và 25/09/2026. Hai giá là bao nhiêu và biến động phần trăm giữa hai ngày là bao nhiêu?',
'Trong bản giá ENTRADE đã đóng băng của MBB, chỉ xét từ 02/01/2018 đến hết 25/09/2026, phiên hoặc các phiên nào có volume lớn nhất và volume đó là bao nhiêu?',
'Trong bản giá ENTRADE đã đóng băng của FPT từ 02/01/2018 đến hết 25/09/2026, giá đóng cửa cao nhất và thấp nhất là bao nhiêu? Liệt kê tất cả ngày đồng hạng ở từng cực trị.',
'Trong bản giá ENTRADE đã đóng băng của MBB, chọn đúng 20 phiên có giao dịch gần nhất không muộn hơn 25/09/2026. Tổng volume và volume bình quân của 20 phiên là bao nhiêu? Nêu ngày đầu và cuối của cửa sổ thực tế.',
'Theo bản giá ENTRADE đã đóng băng của VCB, ngày 20/05/2026 có open, high, low, close và volume bao nhiêu? Nêu price_scale và đơn vị theo chính bản nguồn này.',
'Theo bản giá ENTRADE đã đóng băng, tính phần trăm biến động close của VCB, MBB và FPT từ đúng phiên 03/09/2026 đến 25/09/2026. Mã nào có mức biến động cao nhất? Nếu bằng nhau, liệt kê tất cả mã đồng hạng.',
'Trong bản giá ENTRADE đã đóng băng của FPT từ 02/01/2018 đến hết 25/09/2026, phiên hoặc các phiên nào có high trừ low lớn nhất? Nêu high, low và biên độ, giữ cùng cơ sở giá và price_scale.',
'Trong bản giá ENTRADE đã đóng băng của VCB từ 02/01/2018 đến hết 25/09/2026, có bao nhiêu ngày giao dịch phân biệt với bản ghi hợp lệ? Không tính bản trùng ngày, không suy số phiên từ số ngày làm việc.',
'Theo bản giá ENTRADE đã đóng băng của VCB, ngày 23/04/2026 có volume, open, high, low và close bao nhiêu? Chỉ tra phiên này; không mặc định đây là kỷ lục toàn lịch sử.',
'Theo bản giá ENTRADE đã đóng băng của MBB, close tại đúng ngày 17/09/2026 và 25/09/2026 là bao nhiêu? Tính chênh lệch có dấu và phần trăm biến động giữa hai ngày.',
'Theo BCTC hợp nhất kiểm toán trong đúng PDF FPT 2024 đã chốt phiên bản, doanh thu thuần năm 2024 là bao nhiêu? Dẫn dòng, cột năm và đơn vị trên bảng.',
'Theo đúng PDF FPT 2024 đã chốt phiên bản, lợi nhuận sau thuế năm 2024 thuộc cổ đông công ty mẹ là bao nhiêu? Không thay bằng tổng lợi nhuận sau thuế hợp nhất.',
'Theo bảng cân đối kế toán hợp nhất trong đúng PDF FPT 2024 đã chốt phiên bản, tổng tài sản tại 31/12/2024 là bao nhiêu? Dẫn đúng cột cuối năm và đơn vị.',
'Theo báo cáo lưu chuyển tiền tệ hợp nhất trong đúng PDF FPT 2024 đã chốt phiên bản, lưu chuyển tiền thuần từ hoạt động kinh doanh năm 2024 là bao nhiêu?',
'Theo Thuyết minh 34(b), báo cáo bộ phận theo khu vực địa lý trong đúng PDF FPT 2024, doanh thu thuần ở cột Nước ngoài năm 2024 là bao nhiêu và bảng ghi đơn vị gì? Không thay bằng doanh thu riêng dịch vụ CNTT nước ngoài.',
'Theo bảng Top 10 cổ đông lớn trong đúng PDF BCTN FPT 2024, cá nhân nào có số cổ phần lớn nhất trong bảng, số cổ phần và tỷ lệ sở hữu là bao nhiêu? Dẫn ngày chốt danh sách nếu tài liệu có nêu.',
'Theo bảng chi tiết thù lao HĐQT trong đúng PDF BCTN FPT 2024, mức thù lao thực nhận năm 2024 của ông Trương Gia Bình là bao nhiêu? Phân biệt số 0 với ô trống hoặc không công bố.',
'Theo phần ESG trong đúng PDF BCTN FPT 2024, tỷ lệ nhân sự nữ được công bố là bao nhiêu và mẫu số/phạm vi nhân sự được tài liệu mô tả thế nào? Nếu không nêu rõ phạm vi thì ghi chưa rõ.',
'Theo báo cáo kiểm toán độc lập trong đúng PDF FPT 2024, tên đơn vị kiểm toán và loại ý kiến đối với BCTC hợp nhất năm 2024 là gì? Dẫn đoạn ý kiến và tên đơn vị ký báo cáo.',
'Chỉ dựa trên đúng PDF BCTN FPT 2024 trong tập kiểm thử, mức giá mục tiêu cổ phiếu FPT vào cuối năm 2025 được tài liệu dự báo là bao nhiêu?',
'Trong bản dữ liệu clean FPT đã đóng băng, tại kỳ 2026-Q2, tiền và các khoản tương đương tiền có giá trị gốc bao nhiêu? Nêu đơn vị và phạm vi báo cáo nếu nguồn xác nhận; nếu chưa thì ghi chưa xác minh.',
'Trong bản dữ liệu clean FPT đã đóng băng, tại kỳ 2026-Q2, dư nợ vay và nợ thuê tài chính ngắn hạn có giá trị gốc bao nhiêu? Không thay bằng tổng nợ ngắn hạn hoặc tổng nợ phải trả.',
'Trong bản dữ liệu clean FPT đã đóng băng, tại kỳ 2026-Q2, lợi nhuận sau thuế chưa phân phối lũy kế có giá trị gốc bao nhiêu? Phân biệt số dư lũy kế với phần chưa phân phối riêng kỳ này.',
'Trong bản dữ liệu clean FPT đã đóng băng, doanh thu thuần bán hàng và cung cấp dịch vụ gắn nhãn kỳ 2026-Q2 có giá trị gốc bao nhiêu? Nêu nguồn đã xác nhận riêng quý hay lũy kế chưa; không tự suy từ nhãn kỳ.',
'Trong bản dữ liệu clean FPT đã đóng băng, kỳ 2026-Q2 có lợi nhuận sau thuế thuộc cổ đông công ty mẹ và lãi cơ bản trên cổ phiếu lần lượt bao nhiêu? Nêu đơn vị/cơ sở kỳ khi có bằng chứng; không dùng tổng LNST thay LNST cổ đông mẹ.',
'Trong bản dữ liệu clean FPT đã đóng băng, lưu chuyển tiền thuần từ hoạt động kinh doanh gắn nhãn kỳ 2026-Q2 có giá trị gốc và dấu thế nào? Nêu riêng quý/lũy kế nếu nguồn xác nhận.',
'Trong bản dữ liệu clean FPT đã đóng băng, tiền chi mua sắm và xây dựng tài sản cố định gắn nhãn kỳ 2026-Q2 có giá trị gốc, dấu dòng tiền và độ lớn khoản chi bao nhiêu? Không tự thêm tài sản dài hạn khác vào phạm vi chỉ tiêu.',
'Theo dữ liệu nguồn tại kỳ 2026-Q2, tỷ suất sinh lời trên vốn chủ sở hữu (ROE) và biên lợi nhuận gộp của FPT có giá trị gốc bao nhiêu và được nguồn ghi theo cơ sở kỳ nào? Không mặc định các tỷ lệ chỉ tính riêng ba tháng Q2.',
'Lấy hai giá trị doanh thu thuần gắn nhãn 2026-Q1 và 2026-Q2 trong cùng bản clean FPT đã đóng băng. Nếu đơn vị, phạm vi và cơ sở kỳ so sánh được đã xác minh, tính chênh lệch và phần trăm biến động; nếu chưa, nêu hai số gốc và điều kiện còn thiếu, không khẳng định tăng trưởng kinh tế.',
'Chỉ dựa trên bản clean FPT được đóng băng trong tập kiểm thử này, doanh thu thuần và lợi nhuận sau thuế kỳ 2026-Q4 là bao nhiêu?',
]

NEEDS = [
['Mã hai lô trái phiếu','Giá trị từng lô','Tổng giá trị'],['Tiền gửi và kỳ hạn bài nêu','Số tiền lãi bài nêu','Lãi suất áp dụng'],
['Số cổ phiếu','Số cổ đông','Ngày kết thúc'],['Số cổ đông','Tỷ lệ khối ngoại'],['Dự báo CTG','Dự báo VCB','Tính chất dự báo'],
['Tổng tài sản','Số doanh nghiệp thành viên'],['Nội dung chấp thuận','Cơ quan chấp thuận hoặc chưa nêu'],
['Khoản tiền bài nêu','Mốc sở hữu 52% → 70%','Mốc doanh nghiệp một chủ 100%'],['Tốc độ viết mã','Năng suất dự án'],
['Nhân sự toàn hệ sinh thái','Mức tăng và mốc so sánh'],
]


def main(args):
    raw = args.source.read_bytes()
    text = raw.decode('utf-8-sig')
    sections = re.split(r'^### Q(\d{2})[^\n]*\n', text, flags=re.M)
    original = {int(sections[i]): sections[i+1].split('\n### ')[0] for i in range(1,len(sections),2)}
    if set(original) != set(range(1,41)):
        raise ValueError('Expected unique Q01–Q40 in supplied document')
    manifest = json.loads((ROOT/'backend/.tmp/corpus-v2.content.manifest.json').read_text(encoding='utf-8'))
    docs = manifest['manifest']['documents']
    corpus = {'content_manifest_sha256':manifest['manifest_sha256'], 'index_version_id':INDEX,
              'registered_corpus_version_id':None,
              'note':'Vector ingest đã audit đủ; đăng ký corpus/manifest chính thức và chạy B1 chưa hoàn tất.'}
    metric_codes = {31:['CASH_AND_CASH_EQUIVALENTS'],32:['SHORT_TERM_LOANS_AND_FINANCE_LEASES'],
                   33:['RETAINED_EARNINGS'],34:['NET_REVENUE'],35:['PARENT_NET_PROFIT','BASIC_EARNINGS_PER_SHARE'],
                   36:['CASH_FLOW_OPERATING'],37:['PURCHASE_FIXED_ASSETS'],38:['ROE','GROSS_MARGIN'],39:['NET_REVENUE']}
    raw_fields = {31:'bsa2',32:'bsa56',33:'bsa90',34:'isa3',35:'isa22; isa23',36:'cfa18',37:'cfa19',38:'roe; grossMargin',39:'isa3'}
    cases = []
    for n, question in enumerate(QUESTIONS,1):
        block = original[n]
        answer = re.search(r'^- \*\*Đáp án(?: chuẩn)?:?\*\*\s*[:：]?\s*(.+)$', block, re.M)
        source = re.search(r'^- \*\*Tài liệu gốc:\*\*\s*(.+)$',block,re.M)
        original_question = re.search(r'^- \*\*Câu hỏi:?\*\*\s*:?\s*(.+)$',block,re.M)
        kind = ('REFUSAL' if n in (30,40) else 'CALCULATION' if n in (11,12,13,14,16,17,18,20,39)
                else 'STRUCTURED_LOOKUP' if n in (15,19) else 'VECTOR_RETRIEVAL')
        family = 'NEWS' if n<=10 else 'PRICE_HISTORY' if n<=20 else 'ANNUAL_REPORT_PDF' if n<=30 else 'FINANCIAL_CLEAN'
        status = ('NEEDS_EVIDENCE_REVIEW' if family=='NEWS' else 'SOURCE_VERSION_ALIGNMENT_REQUIRED' if family=='PRICE_HISTORY'
                  else 'PDF_NOT_INGESTED' if family=='ANNUAL_REPORT_PDF' else 'NEEDS_UNIT_SCOPE_PERIOD_REVIEW')
        if n==40:
            status = 'NEEDS_REFUSAL_REVIEW'
        needed = NEEDS[n-1] if n<=10 else ([f'{code}; kỳ '+('2026-Q1 và 2026-Q2' if n==39 else '2026-Q2') for code in metric_codes[n]] if n in metric_codes else
            ['Đúng bảng/đoạn và tiêu đề, đơn vị, cột năm hoặc phạm vi được hỏi'] if 21<=n<=29 else
            ['Tập giá đúng provider, hash và cửa sổ nêu trong câu hỏi','Các bản ghi đầu vào đủ để tính/tra chính xác'])
        if kind=='REFUSAL':
            needed = ['Xác nhận nguồn và phạm vi đóng băng','Trả lời không đủ thông tin, không bịa con số']
        candidates = []
        if family=='NEWS' and source:
            title = re.search(r'Title:\s*\*"(.+?)"\*',source.group(1))
            if title:
                matched = [d for d in docs if d['doc_type']=='NEWS' and d['title']==title.group(1)]
                candidates = [{'source_document_id':d['document_id'],'title':d['title'],
                               'source_chunk_ids':[c['source_chunk_id'] for c in d['chunks']],
                               'review':'Bài khớp tiêu đề; chưa xác nhận đoạn nào đủ từng ý đáp án.'} for d in matched]
        elif n in metric_codes:
            for d in docs:
                if d['doc_type']!='FINANCIAL_STATEMENT' or d['symbol']!='FPT':continue
                for c in d['chunks']:
                    period = c['locator'].get('period_code')
                    if period not in ({'2026-Q1','2026-Q2'} if n==39 else {'2026-Q2'}):continue
                    matched_codes = [code for code in metric_codes[n] if '('+code+'):' in c['text']]
                    if matched_codes:
                        candidates.append({'source_document_id':d['document_id'],'source_chunk_id':c['source_chunk_id'],
                                           'content_hash':c['content_hash'],'period':period,'codes':matched_codes,
                                           'review':'Ứng viên theo mã chỉ tiêu/kỳ; chưa thay cho nhãn gold đã duyệt.'})
        case = {'id':f'Q{n:02}', 'question':question, 'original_question':original_question.group(1) if original_question else None,
                'test_type':kind,'source_family':family,'readiness':status,'corpus':corpus,
                'required_information':needed,'candidate_evidence':candidates,
                'gold_evidence_groups':[], 'gold_review_status':'PENDING_HUMAN_REVIEW',
                'original_answer_provisional':answer.group(1) if answer else None,
                'original_source_reference':source.group(1) if source else None,
                'approved_answer':None,'benchmark_ready':False,
                'filters_policy':'Chỉ lấy điều kiện công ty/kỳ/loại nguồn từ câu hỏi; không lọc bằng ID hoặc mã chỉ tiêu từ đáp án gold.',
                'source_field_reference':raw_fields.get(n)}
        if family=='PRICE_HISTORY':
            case['scope'] = {'provider':'ENTRADE','start':'2018-01-02','end':'2026-09-25',
                             'frozen_dataset_sha256':None,'price_basis_verified':False,
                             'note':'Corpus-v2 giá hiện tại ngắn hơn và khác phiên bản; Q15 cũng lệch giá (v5 close 64,07, DB đã audit 64,13). Không trộn hai bản.'}
            if n in (14,16,20):case['scope']['note'] += ' Cửa sổ con/ngày cụ thể theo câu hỏi, không lấy toàn dải nếu không được yêu cầu.'
        if family=='ANNUAL_REPORT_PDF':
            case['pdf_reference'] = {'path':'data/references/vietstock/annual_reports/files_pdf/FPT/2024/FPT_2024_498332.pdf',
                                     'sha256':None,'physical_pages_reviewed':False,'ingested':False}
        if n>=31:
            case['source_semantics'] = {'unit':'SOURCE_NATIVE','statement_scope':'UNKNOWN','period_basis':'UNVERIFIED',
                                        'ratio_basis':'RATIO_TTM theo normalized nguồn FPT kỳ Q2' if n==38 else None}
        if kind=='CALCULATION':
            case['scoring'] = 'Chấm đủ dữ liệu đầu vào riêng, phép tính Decimal/SQL riêng; thiếu tập đầu vào không quy thành lỗi xếp hạng vector.'
        elif kind=='REFUSAL':
            case['scoring'] = 'Chấm câu trả lời không bịa và nêu thiếu bằng chứng; không dùng Recall/MRR, không yêu cầu vector trả rỗng.'
        else:
            case['scoring'] = 'Chỉ chấm khi gold đã duyệt: Evidence-group Recall@5/@10; MRR cho câu có một nhóm bằng chứng. Chấm đúng đáp án riêng.'
        cases.append(case)
    result = {'version':'v6.0-proposal','created_date':'2026-10-21','status':'DRAFT_NOT_BENCHMARK_READY',
              'input_file':args.source.name,'input_sha256':hashlib.sha256(raw).hexdigest(),
              'corpus':corpus,'test_type_counts':dict(Counter(c['test_type'] for c in cases)), 'cases':cases}
    out = args.out
    out.mkdir(parents=True,exist_ok=True)
    (out/'Golden40_V6_De_xuat.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    labels = {'VECTOR_RETRIEVAL':'Tìm đoạn bằng vector','CALCULATION':'Truy vấn số liệu + tính toán',
              'STRUCTURED_LOOKUP':'Tra cứu phiên giá','REFUSAL':'Từ chối khi thiếu bằng chứng'}
    statuses = {'NEEDS_EVIDENCE_REVIEW':'Cần duyệt đoạn bằng chứng','SOURCE_VERSION_ALIGNMENT_REQUIRED':'Cần khớp lại bản nguồn giá',
                'PDF_NOT_INGESTED':'Chờ nạp/kiểm tra PDF','NEEDS_UNIT_SCOPE_PERIOD_REVIEW':'Cần xác minh đơn vị/phạm vi/cơ sở kỳ',
                'NEEDS_REFUSAL_REVIEW':'Cần duyệt phạm vi thiếu dữ liệu và thử hành vi từ chối'}
    lines = ['# Golden40 v6 — Bản đề xuất chỉnh sửa để kiểm thử rõ từng chức năng','',
      '**Đây là bản để nhóm duyệt, không phải bộ đề đã nghiệm thu.** Giữ đủ Q01–Q40; không sửa file v5 gốc.',
      'Nguồn đầu vào: bản v5.0 ngày 21/10/2026 người dùng cung cấp. SHA-256: `'+result['input_sha256']+'`.','',
      '## Cách đọc và các điểm đã sửa','',
      '- 27 câu tìm đoạn bằng vector; 9 câu truy vấn/tính toán; 2 câu tra phiên giá; 2 câu từ chối.',
      '- Câu nhiều ý ghi rõ cần tìm đủ ý nào. Không đưa đáp án, nguồn gold hoặc ID đoạn đúng vào đầu vào truy vấn.',
      '- Q02 chỉ trích số tiền lãi bài báo đã nêu; không lẫn với tự tính lãi một sản phẩm khác.',
      '- Câu giá cố định provider và ngày bắt đầu/kết thúc; bỏ “mọi thời đại”, “ngày cuối hiện tại” và giả định kỷ lục. Cực trị chấp nhận toàn bộ ngày đồng hạng.',
      '- Q31–Q39 hỏi số gốc, không tự biến SOURCE_NATIVE/UNKNOWN thành VND/hợp nhất/riêng quý. Q38 nêu cơ sở TTM; Q39 chỉ khẳng định tăng trưởng khi cơ sở so sánh được xác minh.',
      '- Đáp án v5 được giữ là **tham khảo chưa duyệt lại**, không mặc định đúng. Trường “đáp án được duyệt” và nhãn gold để trống có chủ ý.',
      '- Đây là sửa đề, không chạy B1, không nhập thêm dữ liệu hoặc cập nhật vector.','',
      '## Phạm vi corpus và phần còn thiếu','',
      'Index dự kiến: `'+INDEX+'`; content manifest hash: `'+manifest['manifest_sha256']+'`.',
      'Vector v2 đã ingest/audit trước đó; chưa đăng ký corpus chính thức hoặc chạy B1. Chốt manifest ID lưu thật trước khi gắn nhãn gold.',
      'Giá lịch sử 2018–25/09/2026 và PDF FPT 2024 chưa đủ trong corpus-v2 này. Cần chuẩn bị corpus/candidate mở rộng riêng; không ghi đè bản đã đóng băng.',
      'Ngay trong cửa sổ giá hiện có cũng có khác bản nguồn: Q15 v5 ghi close 64,07 nhưng DB đã audit ghi 64,13. Không trộn đáp án ENTRADE v5 với tập giá v2 khác phiên bản.',
      'Danh sách đoạn tự định vị bên JSON chỉ là **ứng viên để duyệt**, không phải nhãn đúng cuối cùng.','',
      '## Cách chấm đề xuất','',
      '1. **Tìm kiếm vector:** chạy hai cấu hình tách biệt: không lọc và lọc công ty/kỳ/loại nguồn suy từ câu hỏi. Không dùng ID gold, mã chỉ tiêu chỉ xuất hiện trong đáp án hoặc tên tài liệu gold làm bộ lọc bí mật.',
      '2. Người duyệt chia câu thành các **nhóm bằng chứng bắt buộc**. Mỗi nhóm chứa các chunk ID lưu DB có thể thay thế nhau, content hash và đoạn trích giải thích vì sao đủ. Một chunk có thể đáp ứng nhiều nhóm nếu chứa đủ ý.',
      '3. Evidence-group Recall@k = số nhóm có ít nhất một chunk đúng trong top-k / số nhóm cần thiết. Báo cáo @5 và @10; ghi riêng tỷ lệ tìm đủ tất cả nhóm. MRR dùng cho câu một nhóm bằng chứng; không trộn với câu tính toàn tập.',
      '4. **Số liệu/tính toán:** chấm tập bản ghi đầu vào đúng, đủ và kết quả số học riêng. Dùng Decimal/SQL, giữ price_scale, không để vector thay phép đếm/MAX/AVG.',
      '5. **Từ chối:** không chấm Recall/MRR. Vector vẫn có thể trả đoạn gần nghĩa; chấm hệ thống có nhận ra thiếu bằng chứng và tránh bịa số hay không.',
      '6. Chỉ chấm các câu đủ nguồn và gold đã duyệt. Luôn báo tổng 40 câu, số đủ điều kiện và số bị chặn; không loại câu khó mà vẫn tuyên bố “40/40 đạt”.',
      '7. Số nguyên đầy đủ so chính xác sau chuẩn hóa định dạng. Số làm tròn cho phép nửa đơn vị ở chữ số hiển thị cuối, chỉ khi đơn vị/quy đổi đã xác minh. Phần trăm 2 chữ số: ±0,005 điểm phần trăm; tỷ lệ 4 chữ số: ±0,00005. Không dùng một dung sai 0,1% chung cho mọi câu.',
      '8. Nếu tách calibration/test, chia theo bài/tài liệu hoặc nhóm nguồn liên quan, không chia ngẫu nhiên các câu cùng PDF/bài sang hai bên. Các câu cùng PDF FPT phải tránh rò rỉ qua tập hiệu chỉnh.','',
      '## Danh sách 40 câu sau sửa','', '| Mã | Cách kiểm thử | Tình trạng cần xử lý |','| --- | --- | --- |']
    for c in cases:lines.append('| '+c['id']+' | '+labels[c['test_type']]+' | '+statuses[c['readiness']]+' |')
    for c in cases:
        lines += ['', '### '+c['id']+' — '+labels[c['test_type']], '', '**Câu hỏi đã sửa:** '+c['question'],'',
                  '**Cần lấy đủ:** '+'; '.join(c['required_information'])+'.',
                  '**Cách chấm:** '+c['scoring'], '**Trạng thái:** '+statuses[c['readiness']]+'. Chưa có nhãn gold được duyệt.']
        if c['original_answer_provisional']:
            lines += ['', '**Đáp án v5 để đối chiếu, chưa duyệt lại:** '+c['original_answer_provisional']]
        if c['source_field_reference']:
            lines += ['**Tham chiếu trường nguồn đã đối chiếu trước đó:** `'+c['source_field_reference']+'`. Vẫn phải khớp đúng hash file/phiên bản nguồn khi nghiệm thu.']
        if c['test_type']=='REFUSAL':
            lines += ['**Kỳ vọng đề xuất:** Nêu không đủ thông tin trong đúng nguồn/phạm vi đã chốt; không bịa số. Lý do từ chối phải dựa bằng chứng, không chỉ vì bộ đề gắn nhãn từ chối.']
        lines += ['**Phiếu duyệt cần bổ sung:** document ID lưu DB; nhóm chunk ID đúng; content hash; locator; bằng chứng; đơn vị/cơ sở kỳ; đáp án duyệt; người/ngày duyệt.']
    lines += ['', '## Các file đi kèm','',
              '`Golden40_V6_De_xuat.json` chứa câu hỏi gốc, câu sửa, loại kiểm thử, đáp án v5 tham khảo, điều kiện nguồn và các ứng viên bằng chứng để nhóm duyệt.',
              'Các gold_evidence_groups/approved_answer còn trống là công việc cần duyệt, không phải đã kiểm thử thất bại. Không đưa toàn bộ JSON chứa đáp án vào prompt truy vấn.','']
    (out/'Golden40_V6_De_xuat.md').write_text('\n'.join(lines),encoding='utf-8')
    simple = ['# Golden40 v6 — 40 câu hỏi sau chỉnh sửa','',
              'Bản đề xuất ngày 21/10/2026 để thành viên đọc và duyệt câu hỏi. Chưa phải bộ đề benchmark đã nghiệm thu.',
              'Cách chấm, đáp án v5 tham khảo và các phần thiếu nguồn nằm trong Golden40_V6_De_xuat.md.','']
    for c in cases:
        n = int(c['id'][1:])
        if n in (1,11,21,31):
            simple += ['## '+{1:'Tin tức doanh nghiệp — Q01–Q10',11:'Giá cổ phiếu — Q11–Q20',
                              21:'PDF FPT 2024 — Q21–Q30',31:'Tài chính clean FPT — Q31–Q40'}[n], '']
        simple += ['**'+c['id']+' — '+labels[c['test_type']]+'**', '', c['question'], '']
    (out/'Golden40_Cau_hoi_sau_sua.md').write_text('\n'.join(simple),encoding='utf-8')
    print(json.dumps({'output':str(out),'questions':len(cases),'types':result['test_type_counts'],
                      'original_answers_preserved':sum(bool(c['original_answer_provisional']) for c in cases)},ensure_ascii=False))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source',type=Path,required=True)
    parser.add_argument('--out',type=Path,default=ROOT/'outputs/golden40-v6')
    main(parser.parse_args())
