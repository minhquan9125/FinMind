import os
import traceback
from openai import OpenAI

api_key = os.environ.get("OPENROUTER_API_KEY")
if not api_key:
    raise SystemExit("Chưa đặt biến môi trường OPENROUTER_API_KEY")
if not api_key.isascii():
    raise SystemExit(
        "OPENROUTER_API_KEY có ký tự không hợp lệ. Hãy thay placeholder bằng key thật từ OpenRouter."
    )

client = OpenAI(base_url="https://openrouter.ai/api/v1", api_key=api_key)

# 2. Dữ liệu văn bản OCR cần sửa
text_raw = (
    "PHN FPT\n17:13:56 +07'00'\nCÔNG TY C PHN FPT\nCNG HOÀ X HI CH NGHA VIT NAM\n"
    "FPT CORPORATION\nĐc lp - T do - Hnh phc\nTHE SOCIALIST REPUBLIC OF VIETNAM\n"
    "Independence - Freedom - Happiness\nS:71./FPT-FCC\nNo.: 3A/FPT-FCC\n"
    "Hà Ni, ngày 02 tháng04 năm 2025\nHanoi, April 02tħ 2025\nCÔNG B THNG TIN ĐNH K\n"
    "PERIODIC INFORMATION DISCLOSURE\nKính gi: y ban Chng khoán Nhà nưc\n"
    "S Giao dch Chúng khoán thành ph H Chí Minh\nONO\nTo: The State Securities Commission\n"
    "Hochiminh Stock Exchange\n1. Tên t chúc/Name of organization: Công ty C phn FPT/ FPT Corporation\n"
    "- Mã chng khoán/Mã thành viên/ Stock code/ Broker code: FPT/ FPT\n"
    "- Đa chí/Address: Só 10, ph Phm Văn Bch, Phưng Dch Vng, Qun Cu Giáy,\n"
    "Thành phó Hà Ni, Vit Nam/ 10 Pham Van Bach Street, Dich Vong Ward, Cau\n"
    "Giay District, Hanoi, Vietnam\nFax: 024.3768 7410\n- Đin thoi liên h/Tel.: 024. 7300 7300\n"
    "- E-mail: ir@fpt.com\nwebsite:https://fpt.com\n2. Ni dung thông tin công b / Contents of disclosure:\n"
    "Báo cáo thưòng niên 2024/ 2024 Annual Report.\n3. Thông tin này đã đưc công b trên trang thông tin đin t ca công ty vào ngày\n"
    "02/04/2025 ti dưòng dn https://fpt.com/vi/nha-dau-tu/thong-tin-cong-bo/ This\n"
    "information was published on the company's website on 02/04/2025, as in the link\n"
    "https://fpt.com/en/ir/information-disclosures"
)

prompt = f"""-Use only the supplied OCR text. Do not use outside knowledge or invent missing content.
- Correct clear OCR character and spacing errors; preserve the original wording, language, reading order, and paragraph meaning.
- Preserve every number, date, percentage, amount, code, URL, and email exactly. Do not add, remove, or change digits.
- Remove only obvious OCR layout noise such as duplicated whitespace or isolated decorative symbols. Keep meaningful labels and signature names.
- Return only the cleaned transcription. Do not summarize, explain, translate, or add headings.
Văn bản lỗi:
{text_raw}"""

# 3. Gọi API có kiểm soát lỗi
try:
    print("Đang gửi request tới OpenRouter...")
    response = client.chat.completions.create(
        model="inclusionai/ling-3.1-flash",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.1,
        max_tokens=4080,
    )

    content = response.choices[0].message.content
    usage = response.usage
    if usage:
        print("\n=== TOKEN ĐÃ DÙNG ===")
        print(f"Đầu vào: {getattr(usage, 'prompt_tokens', 0)}")
        print(f"Đầu ra: {getattr(usage, 'completion_tokens', 0)}")
        print(f"Tổng: {getattr(usage, 'total_tokens', 0)}")

    if content:
        print("\n=== KẾT QUẢ VĂN BẢN ĐÃ SỬA ===")
        print(content)
    else:
        print("[CẢNH BÁO] OpenRouter trả về nội dung rỗng.")

except Exception as e:
    print(f"\n[LỖI XẢY RA]: {e}")
    traceback.print_exc()
