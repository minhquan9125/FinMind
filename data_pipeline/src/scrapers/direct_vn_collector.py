import requests
import json
import time
import os
import sys
import math
from datetime import datetime

# Thiết lập encoding UTF-8 cho Windows Console
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

# Danh sách 8 mã cổ phiếu mục tiêu
TARGET_SYMBOLS = ["FPT", "VNM", "HPG", "VCB", "MWG", "VIC", "TCB", "SSI"]

def sanitize_json_value(val):
    """
    Xử lý làm sạch kiểu dữ liệu cho JSON chuẩn:
    - NaN -> null (None)
    - Infinity / -Infinity -> null (None)
    - Giữ nguyên null (None), không biến null thành 0
    - Giữ nguyên số thực (float), số nguyên (int), chuỗi (str), bool
    - Đệ quy cho dict và list
    """
    if val is None:
        return None
    if isinstance(val, float):
        if math.isnan(val) or math.isinf(val):
            return None
        return round(val, 4)
    if isinstance(val, dict):
        return {k: sanitize_json_value(v) for k, v in val.items()}
    if isinstance(val, list):
        return [sanitize_json_value(v) for v in val]
    return val

def format_period(year_val, length_or_quarter):
    """
    Xác định nhãn và kiểu kỳ báo cáo:
    - 1, 2, 3, 4 -> "QUARTER", quarter=1..4, label="{year}-Q{quarter}"
    - 5 hoặc không có quarter -> "YEAR", quarter=null, label="{year}-YEAR" (hoặc "{year}-FY")
    """
    try:
        y = int(year_val)
    except Exception:
        y = year_val

    try:
        q_num = int(length_or_quarter) if length_or_quarter is not None else 5
    except Exception:
        q_num = 5

    if q_num in [1, 2, 3, 4]:
        return f"{y}-Q{q_num}", "QUARTER", y, q_num
    else:
        return f"{y}-YEAR", "YEAR", y, None

def sort_period_key(item):
    """Sắp xếp kỳ dữ liệu từ mới nhất đến cũ nhất"""
    try:
        y = item.get("year", 0) or 0
        q = item.get("quarter")
        q_score = q if q is not None else 5
        return int(y) * 10 + int(q_score)
    except Exception:
        return 0

class VietnamStockDataCollector:
    """
    Bộ thu thập dữ liệu chuyên sâu cho Thị trường Chứng khoán Việt Nam:
    - Thu thập lịch sử giá (OHLCV) từ 2018 -> hiện tại.
    - Thu thập toàn bộ Chỉ số Tài chính (Ratios), Báo cáo KQKD (Income Statement),
      Bảng CĐKT (Balance Sheet), Lưu chuyển Tiền tệ (Cash Flow).
    - Lưu 2 bản: data/raw/ và data/normalized/.
    - Giữ trọn vẹn 100% trường dữ liệu gốc mà không tự ý loại bỏ.
    - Xử lý NaN / Infinity -> null hợp lệ chuẩn JSON.
    - Cơ chế Error Handling độc lập cho từng nguồn, không làm dừng chương trình.
    """
    def __init__(self, output_root=None):
        if output_root is None:
            base_dir = os.path.dirname(os.path.abspath(__file__))
            self.root_dir = os.path.abspath(os.path.join(base_dir, "..", "..", "..", "data"))
        else:
            self.root_dir = os.path.abspath(output_root)

        self.raw_dir = os.path.join(self.root_dir, "raw")
        self.norm_dir = os.path.join(self.root_dir, "normalized")

        os.makedirs(self.raw_dir, exist_ok=True)
        os.makedirs(self.norm_dir, exist_ok=True)

        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "application/json, text/plain, */*",
            "Origin": "https://trading.vietcap.com.vn",
            "Referer": "https://trading.vietcap.com.vn/"
        })

    def fetch_prices(self, symbol: str, retries: int = 3) -> tuple[dict, list]:
        """
        Lấy lịch sử giá nến ngày (OHLCV) từ 2018 đến nay qua Chart API (có retry)
        """
        start_ts = int(datetime(2018, 1, 1).timestamp())
        end_ts = int(datetime.now().timestamp())
        url = f"https://services.entrade.com.vn/chart-api/v2/ohlcs/stock?symbol={symbol}&from={start_ts}&to={end_ts}&resolution=1D"

        for attempt in range(1, retries + 1):
            try:
                resp = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=20)
                if not resp.ok:
                    raise Exception(f"HTTP Status {resp.status_code}")
                
                raw_data = resp.json()
                t_list = raw_data.get('t', [])
                o_list = raw_data.get('o', [])
                h_list = raw_data.get('h', [])
                l_list = raw_data.get('l', [])
                c_list = raw_data.get('c', [])
                v_list = raw_data.get('v', [])

                norm_prices = []
                for i in range(len(t_list)):
                    norm_prices.append({
                        "date": datetime.fromtimestamp(t_list[i]).strftime('%Y-%m-%d'),
                        "open": sanitize_json_value(o_list[i]),
                        "high": sanitize_json_value(h_list[i]),
                        "low": sanitize_json_value(l_list[i]),
                        "close": sanitize_json_value(c_list[i]),
                        "volume": int(v_list[i]) if v_list[i] is not None else 0
                    })
                
                return raw_data, norm_prices
            except Exception as e:
                if attempt < retries:
                    time.sleep(1.0 * attempt)
                    continue
                print(f"    [!] {symbol} - Price failed (sau {retries} lần thử): {e}")
                return {}, []
        return {}, []

    def fetch_statement_section(self, symbol: str, section_name: str, retries: int = 3) -> tuple[dict, list]:
        """
        Lấy báo cáo tài chính theo phân hệ (INCOME_STATEMENT, BALANCE_SHEET, CASH_FLOW)
        Bao gồm cả các kỳ quý (quarters) và các kỳ năm (years) (có retry).
        """
        url = f"https://iq.vietcap.com.vn/api/iq-insight-service/v1/company/{symbol}/financial-statement?section={section_name}"
        for attempt in range(1, retries + 1):
            try:
                resp = self.session.get(url, timeout=20)
                if not resp.ok:
                    raise Exception(f"HTTP Status {resp.status_code}")
                
                raw_json = resp.json()
                data_dict = raw_json.get("data", {})
                quarters = data_dict.get("quarters", []) or []
                years = data_dict.get("years", []) or []

                combined_raw_rows = quarters + years
                norm_list = []

                for row in combined_raw_rows:
                    y_raw = row.get("yearReport")
                    l_raw = row.get("lengthReport")
                    if not y_raw:
                        continue
                    
                    label, p_type, y_num, q_num = format_period(y_raw, l_raw)
                    
                    # Giữ nguyên toàn bộ các trường gốc, làm sạch NaN -> null
                    item = {
                        "period_label": label,
                        "period_type": p_type,
                        "year": y_num,
                        "quarter": q_num
                    }
                    for k, v in row.items():
                        item[k] = sanitize_json_value(v)
                    
                    norm_list.append(item)

                # Sắp xếp từ mới nhất về cũ nhất
                norm_list.sort(key=sort_period_key, reverse=True)
                return raw_json, norm_list
            except Exception as e:
                if attempt < retries:
                    time.sleep(1.0 * attempt)
                    continue
                print(f"    [!] {symbol} - {section_name} failed (sau {retries} lần thử): {e}")
                return {}, []
        return {}, []

    def fetch_financial_ratios(self, symbol: str, retries: int = 3) -> tuple[dict, list]:
        """
        Lấy toàn bộ chỉ số tài chính (P/E, P/B, ROE, ROA, EPS, Margin, Nợ...)
        Bao gồm cả các kỳ quý và kỳ năm tổng hợp (có retry).
        """
        url = f"https://iq.vietcap.com.vn/api/iq-insight-service/v1/company/{symbol}/statistics-financial"
        for attempt in range(1, retries + 1):
            try:
                resp = self.session.get(url, timeout=20)
                if not resp.ok:
                    raise Exception(f"HTTP Status {resp.status_code}")
                
                raw_json = resp.json()
                rows = raw_json.get("data", []) or []
                norm_list = []

                for row in rows:
                    y_raw = row.get("year") or row.get("yearReport")
                    q_raw = row.get("quarter")
                    if not y_raw:
                        continue
                    
                    label, p_type, y_num, q_num = format_period(y_raw, q_raw)
                    
                    # Giữ nguyên toàn bộ các trường gốc
                    item = {
                        "period_label": label,
                        "period_type": p_type,
                        "year": y_num,
                        "quarter": q_num
                    }
                    for k, v in row.items():
                        item[k] = sanitize_json_value(v)
                    
                    norm_list.append(item)

                norm_list.sort(key=sort_period_key, reverse=True)
                return raw_json, norm_list
            except Exception as e:
                if attempt < retries:
                    time.sleep(1.0 * attempt)
                    continue
                print(f"    [!] {symbol} - Financial Ratios failed (sau {retries} lần thử): {e}")
                return {}, []
        return {}, []

    def process_stock(self, idx: int, total: int, symbol: str):
        print(f"\n[{idx}/{total}] {symbol}")

        # 1. Price History
        raw_price, norm_prices = self.fetch_prices(symbol)
        if norm_prices:
            print(f"  Price: OK ({len(norm_prices)} sessions)")
        else:
            print(f"  Price: FAILED / EMPTY")

        # 2. Financial Ratios
        raw_ratios, norm_ratios = self.fetch_financial_ratios(symbol)
        if norm_ratios:
            print(f"  Ratios: OK ({len(norm_ratios)} periods)")
        else:
            print(f"  Ratios: FAILED / EMPTY")

        # 3. Income Statement
        raw_income, norm_income = self.fetch_statement_section(symbol, "INCOME_STATEMENT")
        if norm_income:
            print(f"  Income Statement: OK ({len(norm_income)} periods)")
        else:
            print(f"  Income Statement: FAILED / EMPTY")

        # 4. Balance Sheet
        raw_bs, norm_bs = self.fetch_statement_section(symbol, "BALANCE_SHEET")
        if norm_bs:
            print(f"  Balance Sheet: OK ({len(norm_bs)} periods)")
        else:
            print(f"  Balance Sheet: FAILED / EMPTY")

        # 5. Cash Flow Statement
        raw_cf, norm_cf = self.fetch_statement_section(symbol, "CASH_FLOW")
        if norm_cf:
            print(f"  Cash Flow: OK ({len(norm_cf)} periods)")
        else:
            print(f"  Cash Flow: FAILED / EMPTY")

        # Lưu RAW DATA (data/raw/{symbol}_raw.json)
        raw_payload = {
            "symbol": symbol,
            "crawled_at": datetime.now().isoformat(),
            "raw_prices": raw_price,
            "raw_ratios": raw_ratios,
            "raw_income_statement": raw_income,
            "raw_balance_sheet": raw_bs,
            "raw_cash_flow": raw_cf
        }
        raw_file_path = os.path.join(self.raw_dir, f"{symbol}_raw.json")
        try:
            with open(raw_file_path, "w", encoding="utf-8") as f:
                json.dump(raw_payload, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"    [!] Lỗi ghi file raw {symbol}: {e}")

        # Lưu NORMALIZED DATA (data/normalized/{symbol}.json)
        p_start = norm_prices[0]["date"] if norm_prices else None
        p_end = norm_prices[-1]["date"] if norm_prices else None

        normalized_payload = {
            "symbol": symbol,
            "generated_at": datetime.now().isoformat(),
            "meta": {
                "price_start_date": p_start,
                "price_end_date": p_end,
                "total_price_sessions": len(norm_prices),
                "total_ratio_periods": len(norm_ratios),
                "total_income_periods": len(norm_income),
                "total_balance_sheet_periods": len(norm_bs),
                "total_cash_flow_periods": len(norm_cf)
            },
            "price_history": norm_prices,
            "financial_data": {
                "ratios": norm_ratios,
                "income_statement": norm_income,
                "balance_sheet": norm_bs,
                "cash_flow_statement": norm_cf
            }
        }
        norm_file_path = os.path.join(self.norm_dir, f"{symbol}.json")
        try:
            with open(norm_file_path, "w", encoding="utf-8") as f:
                json.dump(normalized_payload, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"    [!] Lỗi ghi file normalized {symbol}: {e}")

        print(f"  -> Saved: {os.path.relpath(raw_file_path, self.root_dir)} & {os.path.relpath(norm_file_path, self.root_dir)}")

    def run_all(self, symbols: list[str] = None):
        if symbols is None:
            symbols = TARGET_SYMBOLS
        
        total = len(symbols)
        print(f"🚀 BẮT ĐẦU CRAWL DỮ LIỆU CHO {total} MÃ CỔ PHIẾU ({', '.join(symbols)}):\n")
        
        for i, s in enumerate(symbols, 1):
            try:
                self.process_stock(i, total, s)
            except Exception as e:
                print(f"[!] Lỗi không xác định khi xử lý mã {s}: {e}")
            time.sleep(0.5)

        print("\n🎉 HOÀN TẤT THU THẬP & CHUẨN HÓA DỮ LIỆU TOÀN BỘ CÁC MÃ!")

if __name__ == "__main__":
    collector = VietnamStockDataCollector()
    collector.run_all(TARGET_SYMBOLS)