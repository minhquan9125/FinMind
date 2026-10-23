import os
import sys
import pypdf

sys.stdout.reconfigure(encoding='utf-8')

pdf_path = "data/references/vietstock/annual_reports/files_pdf/FPT/2024/FPT_2024_498332.pdf"
print(f"Checking PDF: {pdf_path}")
print("Exists:", os.path.exists(pdf_path))

reader = pypdf.PdfReader(pdf_path)
total_pages = len(reader.pages)
print(f"Total pages: {total_pages}")

def check_page(pdf_page_num, label, search_terms):
    # pypdf is 0-indexed, so page_idx = pdf_page_num - 1
    page = reader.pages[pdf_page_num - 1]
    text = page.extract_text()
    print(f"\n--- {label} (PDF Page {pdf_page_num}) ---")
    for term in search_terms:
        found = term.lower() in text.lower()
        print(f"  [{'FOUND' if found else 'NOT FOUND'}] '{term}'")
        if found:
            # print surrounding lines
            for line in text.split('\n'):
                if term.lower() in line.lower():
                    print(f"     Line: {line.strip()[:120]}")

# Q21: Doanh thu thuần 62.848.794.351.367 (PDF 153), 62.849 (PDF 52)
check_page(153, "Q21 BCTC KQSXKD", ["62.848.794.351.367", "Doanh thu thuần", "Mã số 10", "10"])
check_page(52, "Q21 BCTN Tom tat", ["62.849", "Doanh thu"])

# Q22: LNST co dong me (PDF 154)
check_page(154, "Q22 LNST co dong me", ["7.856.767.812.178", "9.427.422.530.444", "1.570.654.718.266", "Cổ đông của công ty mẹ", "61"])

# Q23: Tong tai san (PDF 150 & 52)
check_page(150, "Q23 Tong tai san", ["71.999.995.678.620", "270", "TỔNG TÀI SẢN"])
check_page(52, "Q23 BCTN Tom tat tai san", ["72.000", "Tổng tài sản"])

# Q24: Luu chuyen tien thuan tu HDKD (PDF 155)
check_page(155, "Q24 Luu chuyen tien thuan HDKD", ["11.703.777.188.868", "20", "Lưu chuyển tiền thuần từ hoạt động kinh doanh"])

# Q25: Thuyet minh 34b (PDF 199)
check_page(199, "Q25 Thuyet minh 34b", ["31.294.207", "Nước ngoài", "Bộ phận theo khu vực địa lý", "34"])

# Q26: Top 10 co dong (PDF 30)
check_page(30, "Q26 Top 10 co dong", ["Trương Gia Bình", "102.041.710", "6,94"])

# Q27: Thu lao HDQT (PDF 79)
check_page(79, "Q27 Thu lao HDQT", ["Trương Gia Bình", "Thù lao", "Hội đồng Quản trị"])

# Q28: Ty le nu gioi ESG (PDF 106)
check_page(106, "Q28 Ty le nu ESG", ["37,1%", "37.1%", "nữ", "nhân sự"])

# Q29: Kiem toan doc lap (PDF 146 - 147)
check_page(146, "Q29 Kiem toan doc lap 1", ["PwC", "Kiểm toán", "Trách nhiệm của kiểm toán viên"])
check_page(147, "Q29 Kiem toan doc lap 2", ["Ý kiến của kiểm toán viên", "trung thực và hợp lý", "PwC"])
