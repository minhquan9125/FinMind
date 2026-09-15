import requests
import time
import os
import sys
from datetime import datetime, timezone

SRC_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

from pipeline_quality import (
    PayloadValidationError,
    atomic_write_json,
    normalize_financial_rows,
    normalize_price_payload,
)

# Thiết lập encoding UTF-8 cho Windows Console
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

# Danh sách 8 mã cổ phiếu mục tiêu
TARGET_SYMBOLS = ["FPT", "VNM", "HPG", "VCB", "MWG", "VIC", "TCB", "SSI"]

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

    def fetch_prices(self, symbol: str, retries: int = 3) -> tuple[dict, list, list]:
        """
        Lấy lịch sử giá nến ngày (OHLCV) từ 2018 đến nay qua Chart API (có retry)
        """
        start_ts = int(datetime(2018, 1, 1).timestamp())
        end_ts = int(datetime.now().timestamp())
        url = "https://services.entrade.com.vn/chart-api/v2/ohlcs/stock"
        params = {"symbol": symbol, "from": start_ts, "to": end_ts, "resolution": "1D"}

        for attempt in range(1, retries + 1):
            try:
                resp = self.session.get(url, params=params, timeout=20)
                resp.raise_for_status()
                raw_data = resp.json()
                norm_prices, quality_issues = normalize_price_payload(raw_data)
                return raw_data, norm_prices, quality_issues
            except Exception as e:
                if attempt < retries:
                    time.sleep(1.0 * attempt)
                    continue
                print(f"    [!] {symbol} - Price failed (sau {retries} lần thử): {e}")
                return {}, [], []
        return {}, [], []

    def fetch_statement_section(self, symbol: str, section_name: str, retries: int = 3) -> tuple[dict, list]:
        """
        Lấy báo cáo tài chính theo phân hệ (INCOME_STATEMENT, BALANCE_SHEET, CASH_FLOW)
        Bao gồm cả các kỳ quý (quarters) và các kỳ năm (years) (có retry).
        """
        url = f"https://iq.vietcap.com.vn/api/iq-insight-service/v1/company/{symbol}/financial-statement?section={section_name}"
        for attempt in range(1, retries + 1):
            try:
                resp = self.session.get(url, timeout=20)
                resp.raise_for_status()
                raw_json = resp.json()
                if raw_json.get("successful") is False:
                    raise PayloadValidationError(raw_json.get("msg") or "Provider reported failure")
                data_dict = raw_json.get("data", {})
                quarters = data_dict.get("quarters", []) or []
                years = data_dict.get("years", []) or []
                norm_list = normalize_financial_rows(quarters + years)
                if not norm_list:
                    raise PayloadValidationError("Provider returned no financial statement rows")
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
                resp.raise_for_status()
                raw_json = resp.json()
                if raw_json.get("successful") is False:
                    raise PayloadValidationError(raw_json.get("msg") or "Provider reported failure")
                rows = raw_json.get("data", []) or []
                norm_list = normalize_financial_rows(rows, ratio=True)
                if not norm_list:
                    raise PayloadValidationError("Provider returned no financial ratio rows")
                return raw_json, norm_list
            except Exception as e:
                if attempt < retries:
                    time.sleep(1.0 * attempt)
                    continue
                print(f"    [!] {symbol} - Financial Ratios failed (sau {retries} lần thử): {e}")
                return {}, []
        return {}, []

    def process_stock(self, idx: int, total: int, symbol: str) -> dict:
        print(f"\n[{idx}/{total}] {symbol}")

        # 1. Price History
        raw_price, norm_prices, price_issues = self.fetch_prices(symbol)
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

        sections = {
            "prices": norm_prices,
            "ratios": norm_ratios,
            "income_statement": norm_income,
            "balance_sheet": norm_bs,
            "cash_flow": norm_cf,
        }
        failed_sections = [name for name, rows in sections.items() if not rows]
        if failed_sections:
            print(f"  -> NOT PUBLISHED: thiếu dữ liệu {', '.join(failed_sections)}; giữ nguyên bản tốt gần nhất")
            return {"symbol": symbol, "status": "FAILED", "failed_sections": failed_sections}

        now_utc = datetime.now(timezone.utc)
        generated_at = now_utc.isoformat().replace("+00:00", "Z")
        dataset_version = now_utc.strftime("%Y%m%dT%H%M%SZ")

        # Lưu RAW DATA (data/raw/{symbol}_raw.json)
        raw_payload = {
            "schema_version": "1.0",
            "dataset_version": dataset_version,
            "symbol": symbol,
            "crawled_at": generated_at,
            "sources": {"prices": "ENTRADE", "fundamentals": "VIETCAP_VCI"},
            "raw_prices": raw_price,
            "raw_ratios": raw_ratios,
            "raw_income_statement": raw_income,
            "raw_balance_sheet": raw_bs,
            "raw_cash_flow": raw_cf
        }
        raw_file_path = os.path.join(self.raw_dir, f"{symbol}_raw.json")
        # Lưu NORMALIZED DATA (data/normalized/{symbol}.json)
        p_start = norm_prices[0]["date"] if norm_prices else None
        p_end = norm_prices[-1]["date"] if norm_prices else None

        normalized_payload = {
            "schema_version": "1.0",
            "dataset_version": dataset_version,
            "symbol": symbol,
            "generated_at": generated_at,
            "sources": {"prices": "ENTRADE", "fundamentals": "VIETCAP_VCI"},
            "quality": {
                "status": "PASS_WITH_WARNINGS" if price_issues else "PASS",
                "raw_price_records": len(raw_price.get("t", [])),
                "published_price_records": len(norm_prices),
                "rejected_price_records": len(raw_price.get("t", [])) - len(norm_prices),
                "issues": price_issues,
            },
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
            atomic_write_json(raw_file_path, raw_payload)
            atomic_write_json(norm_file_path, normalized_payload)
        except Exception as e:
            print(f"    [!] Không thể publish dữ liệu {symbol}: {e}")
            return {"symbol": symbol, "status": "FAILED", "failed_sections": ["publish"]}

        print(f"  -> Saved: {os.path.relpath(raw_file_path, self.root_dir)} & {os.path.relpath(norm_file_path, self.root_dir)}")
        print(f"  -> Quality: {normalized_payload['quality']['status']} ({len(price_issues)} vấn đề nguồn, đã loại khỏi output)")
        return {"symbol": symbol, "status": "PASSED", "quality": normalized_payload["quality"]}

    def run_all(self, symbols: list[str] = None):
        if symbols is None:
            symbols = TARGET_SYMBOLS
        
        total = len(symbols)
        print(f"🚀 BẮT ĐẦU CRAWL DỮ LIỆU CHO {total} MÃ CỔ PHIẾU ({', '.join(symbols)}):\n")
        
        results = []
        for i, s in enumerate(symbols, 1):
            try:
                results.append(self.process_stock(i, total, s))
            except Exception as e:
                print(f"[!] Lỗi không xác định khi xử lý mã {s}: {e}")
                results.append({"symbol": s, "status": "FAILED"})
            time.sleep(0.5)

        passed = sum(result["status"] == "PASSED" for result in results)
        print(f"\nHOÀN TẤT: {passed}/{total} mã được publish; {total - passed} mã thất bại và giữ dữ liệu cũ.")
        return results

if __name__ == "__main__":
    collector = VietnamStockDataCollector()
    collector.run_all(TARGET_SYMBOLS)
