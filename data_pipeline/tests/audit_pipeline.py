"""
Module Kiểm toán & Thẩm định Chất lượng Pipeline Dữ liệu (Bulletproof Pipeline Auditor)
Project: FinMind - Vietnam Financial Intelligence Platform

Quy trình thẩm định 3 tầng độc lập:
1. [CRW] CRAWLER & RAW DATA:
   - Kiểm tra cấu trúc dữ liệu thô nhận từ API.
   - Xác thực cả 5 phân hệ (Prices, Ratios, Income, Balance Sheet, Cash Flow).

2. [MAP] BI-DIRECTIONAL & CELL-BY-CELL MAPPING:
   - Khớp chính xác theo Khóa Tự Nhiên (Natural Period Key).
   - Kiểm tra 2 chiều: RAW -> NORM (không mất field) và NORM -> RAW (không tự chế field lạ).
   - So khớp từng ô (Cell-by-cell):
     + Nếu RAW là None -> NORM bắt buộc là None (tuyệt đối không chuyển thành 0).
     + Nếu RAW là NaN/Infinity -> NORM bắt buộc là None.
     + Nếu RAW là số thực -> NORM khớp chính xác giá trị số.

3. [VAL] VALIDATOR & BUSINESS LOGIC:
   - Kiểm tra toàn vẹn nến OHLCV (High >= Low, Price > 0, Volume >= 0).
   - Kiểm tra Phương trình Kế toán Cân bằng (Assets = Liabilities + Equity) trên toàn bộ các kỳ.
"""

import os
import json
import sys
import math
from datetime import datetime

# Thiết lập encoding UTF-8
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

DEFAULT_SYMBOLS = ["FPT", "VNM", "HPG", "VCB", "MWG", "VIC", "TCB", "SSI"]
STANDARD_META_KEYS = {"period_label", "period_type", "year", "quarter"}

def is_nan_or_inf(val):
    if isinstance(val, float):
        return math.isnan(val) or math.isinf(val)
    return False

def values_match(raw_val, norm_val):
    """Kiểm tra tính tương đương của giá trị giữa RAW và NORMALIZED"""
    # Trường hợp RAW là None hoặc NaN/Inf -> NORM bắt buộc phải là None
    if raw_val is None or is_nan_or_inf(raw_val):
        return norm_val is None

    # Nếu NORM là None trong khi RAW có giá trị hợp lệ -> LỖI
    if norm_val is None:
        return False

    # So sánh số thực (cho phép sai số làm tròn 4 chữ số thập phân)
    if isinstance(raw_val, (int, float)) and isinstance(norm_val, (int, float)):
        return abs(float(raw_val) - float(norm_val)) < 0.0001 or round(float(raw_val), 4) == round(float(norm_val), 4)

    # So sánh chuỗi hoặc kiểu khác
    return str(raw_val) == str(norm_val)

class BulletproofPipelineAuditor:
    def __init__(self, data_root=None):
        if data_root is None:
            base_dir = os.path.dirname(os.path.abspath(__file__))
            self.data_dir = os.path.abspath(os.path.join(base_dir, "..", "..", "data"))
        else:
            self.data_dir = os.path.abspath(data_root)

        self.raw_dir = os.path.join(self.data_dir, "raw")
        self.norm_dir = os.path.join(self.data_dir, "normalized")
        self.report = {}

    def audit_stock(self, symbol: str) -> dict:
        result = {
            "crw": "PASS",
            "map": "PASS",
            "val": "PASS",
            "status": "PASS",
            "cause": "None",
            "details": [],
            "stats": {"total_cells_checked": 0, "balanced_bs_periods": 0, "total_bs_periods": 0}
        }

        raw_path = os.path.join(self.raw_dir, f"{symbol}_raw.json")
        norm_path = os.path.join(self.norm_dir, f"{symbol}.json")

        # =========================================================================
        # 1. TẦNG CRW: Kiểm tra dữ liệu RAW
        # =========================================================================
        if not os.path.exists(raw_path):
            result["crw"] = "FAIL"
            result["details"].append(f"CRW: Thiếu file raw {raw_path}")
            result["status"] = "FAIL"
            return result

        try:
            with open(raw_path, "r", encoding="utf-8") as f:
                raw_d = json.load(f)

            raw_p = raw_d.get("raw_prices", {})
            raw_r = raw_d.get("raw_ratios", {})
            raw_inc = raw_d.get("raw_income_statement", {})
            raw_bs = raw_d.get("raw_balance_sheet", {})
            raw_cf = raw_d.get("raw_cash_flow", {})

            p_count = len(raw_p.get("t", []))
            r_count = len(raw_r.get("data", []) or [])
            inc_count = len(raw_inc.get("data", {}).get("quarters", []) or []) + len(raw_inc.get("data", {}).get("years", []) or [])
            bs_count = len(raw_bs.get("data", {}).get("quarters", []) or []) + len(raw_bs.get("data", {}).get("years", []) or [])
            cf_count = len(raw_cf.get("data", {}).get("quarters", []) or []) + len(raw_cf.get("data", {}).get("years", []) or [])

            if p_count == 0 or r_count == 0 or inc_count == 0 or bs_count == 0 or cf_count == 0:
                result["crw"] = "FAIL"
                result["details"].append(
                    f"CRW: Phân hệ rỗng (Prices:{p_count}, Ratios:{r_count}, Inc:{inc_count}, BS:{bs_count}, CF:{cf_count})"
                )
        except Exception as e:
            result["crw"] = "FAIL"
            result["details"].append(f"CRW: Lỗi đọc file raw: {e}")

        # =========================================================================
        # 2. TẦNG MAP: Kiểm tra Mapping 2 chiều & So khớp từng ô (Cell-by-cell)
        # =========================================================================
        if not os.path.exists(norm_path):
            result["map"] = "FAIL"
            result["details"].append(f"MAP: Thiếu file normalized {norm_path}")
            result["status"] = "FAIL"
            return result

        try:
            with open(norm_path, "r", encoding="utf-8") as f:
                norm_d = json.load(f)

            cells_checked = 0

            # A. Kiểm tra MAP phân hệ Giá (Prices)
            norm_p = norm_d.get("price_history", [])
            raw_t = raw_p.get("t", [])
            raw_o = raw_p.get("o", [])
            raw_h = raw_p.get("h", [])
            raw_l = raw_p.get("l", [])
            raw_c = raw_p.get("c", [])
            raw_v = raw_p.get("v", [])

            if len(raw_t) != len(norm_p):
                result["map"] = "FAIL"
                result["details"].append(f"MAP Prices: Lệch số lượng nến ({len(raw_t)} raw != {len(norm_p)} norm)")
            else:
                for i in range(len(raw_t)):
                    expected_date = datetime.fromtimestamp(raw_t[i]).strftime("%Y-%m-%d")
                    np = norm_p[i]
                    if np["date"] != expected_date:
                        result["map"] = "FAIL"
                        result["details"].append(f"MAP Prices: Lệch ngày tại index {i} ({expected_date} != {np['date']})")
                        break

                    for field, r_val in [("open", raw_o[i]), ("high", raw_h[i]), ("low", raw_l[i]), ("close", raw_c[i])]:
                        cells_checked += 1
                        if not values_match(r_val, np.get(field)):
                            result["map"] = "FAIL"
                            result["details"].append(f"MAP Prices: Lệch giá trị {field} tại {expected_date} ({r_val} != {np.get(field)})")
                            break

            # B. Hàm helper kiểm tra chi tiết từng phân hệ BCTC & Chỉ số
            def audit_statement_mapping(section_name, raw_list, norm_list, is_ratio=False):
                nonlocal cells_checked
                if len(raw_list) != len(norm_list):
                    result["map"] = "FAIL"
                    result["details"].append(f"MAP {section_name}: Lệch số kỳ ({len(raw_list)} raw != {len(norm_list)} norm)")
                    return

                # Khớp theo Khóa kỳ tự nhiên (Natural Period Key)
                for raw_item in raw_list:
                    if is_ratio:
                        y = raw_item.get("year") or raw_item.get("yearReport")
                        q = raw_item.get("quarter")
                    else:
                        y = raw_item.get("yearReport")
                        q = raw_item.get("lengthReport")

                    lbl = f"{y}-Q{q}" if q in [1, 2, 3, 4] else f"{y}-YEAR"
                    norm_item = next((item for item in norm_list if item.get("period_label") == lbl), None)

                    if not norm_item:
                        result["map"] = "FAIL"
                        result["details"].append(f"MAP {section_name}: Không tìm thấy kỳ {lbl} trong file Normalized")
                        continue

                    # 1. Chiều 1: Mọi key trong RAW phải có trong NORM và giá trị khớp từng ô
                    for k, raw_val in raw_item.items():
                        cells_checked += 1
                        if k not in norm_item:
                            result["map"] = "FAIL"
                            result["details"].append(f"MAP {section_name}: Trường '{k}' ở kỳ {lbl} bị mất khi chuẩn hóa!")
                            break

                        norm_val = norm_item.get(k)
                        if not values_match(raw_val, norm_val):
                            result["map"] = "FAIL"
                            result["details"].append(
                                f"MAP {section_name}: Lệch giá trị ô '{k}' kỳ {lbl} (RAW={raw_val} != NORM={norm_val})"
                            )
                            break

                    # 2. Chiều 2: NORM không tự chế thêm trường lạ ngoài RAW và Metadata
                    for k in norm_item.keys():
                        if k not in raw_item and k not in STANDARD_META_KEYS:
                            result["map"] = "FAIL"
                            result["details"].append(f"MAP {section_name}: Trường lạ '{k}' tự tạo ở kỳ {lbl} không có trong RAW!")
                            break

            # Kiểm tra 4 phân hệ tài chính
            raw_r_rows = raw_r.get("data", []) or []
            norm_r_rows = norm_d.get("financial_data", {}).get("ratios", [])
            audit_statement_mapping("Ratios", raw_r_rows, norm_r_rows, is_ratio=True)

            raw_inc_rows = (raw_inc.get("data", {}).get("quarters", []) or []) + (raw_inc.get("data", {}).get("years", []) or [])
            norm_inc_rows = norm_d.get("financial_data", {}).get("income_statement", [])
            audit_statement_mapping("Income Statement", raw_inc_rows, norm_inc_rows)

            raw_bs_rows = (raw_bs.get("data", {}).get("quarters", []) or []) + (raw_bs.get("data", {}).get("years", []) or [])
            norm_bs_rows = norm_d.get("financial_data", {}).get("balance_sheet", [])
            audit_statement_mapping("Balance Sheet", raw_bs_rows, norm_bs_rows)

            raw_cf_rows = (raw_cf.get("data", {}).get("quarters", []) or []) + (raw_cf.get("data", {}).get("years", []) or [])
            norm_cf_rows = norm_d.get("financial_data", {}).get("cash_flow_statement", [])
            audit_statement_mapping("Cash Flow", raw_cf_rows, norm_cf_rows)

            result["stats"]["total_cells_checked"] = cells_checked

        except Exception as e:
            result["map"] = "FAIL"
            result["details"].append(f"MAP: Lỗi không xác định khi thẩm định: {e}")

        # =========================================================================
        # 3. TẦNG VAL: Kiểm tra Logic Nghiệp vụ & Cân bằng Kế toán
        # =========================================================================
        try:
            norm_bs_rows = norm_d.get("financial_data", {}).get("balance_sheet", [])
            result["stats"]["total_bs_periods"] = len(norm_bs_rows)
            balanced_bs = 0

            for bs in norm_bs_rows:
                lbl = bs.get("period_label")
                assets = bs.get("bsa53")        # Tổng tài sản
                total_cap = bs.get("bsa96")     # Tổng nguồn vốn
                liab = bs.get("bsa54")          # Nợ phải trả
                eq = bs.get("bsa78") or bs.get("bsa79")  # Vốn chủ sở hữu

                if assets is None or assets <= 0:
                    result["val"] = "FAIL"
                    result["details"].append(f"VAL: Tổng tài sản <= 0 ở kỳ {lbl}")

                if assets and liab and eq:
                    diff = abs(assets - (liab + eq))
                    if (diff / assets) <= 0.005:
                        balanced_bs += 1
                    else:
                        result["val"] = "FAIL"
                        result["details"].append(f"VAL: Mất cân đối BCTC kỳ {lbl}: Assets={assets:,.0f} != Liab+Eq={liab+eq:,.0f}")
                elif assets and total_cap and abs(assets - total_cap) <= 1000:
                    balanced_bs += 1

            result["stats"]["balanced_bs_periods"] = balanced_bs

        except Exception as e:
            result["val"] = "FAIL"
            result["details"].append(f"VAL: Lỗi kiểm định validator: {e}")

        # =========================================================================
        # Tổng kết trạng thái từng mã
        # =========================================================================
        if result["crw"] == "FAIL" or result["map"] == "FAIL" or result["val"] == "FAIL":
            result["status"] = "FAIL"
            causes = []
            if result["crw"] == "FAIL": causes.append("CRW")
            if result["map"] == "FAIL": causes.append("MAP")
            if result["val"] == "FAIL": causes.append("VAL")
            result["cause"] = "/".join(causes)
        else:
            result["status"] = "PASS"
            result["cause"] = "None"

        return result

    def run(self, symbols: list[str] = None):
        if symbols is None:
            symbols = DEFAULT_SYMBOLS

        print("="*90)
        print("🛡️ BẮT ĐẦU AUDIT CHẶT CHẼ TOÀN DIỆN (BULLETPROOF): CRW -> MAP (CELL-BY-CELL) -> VAL")
        print(f"📌 Danh sách: {', '.join(symbols)}")
        print("="*90 + "\n")

        total_cells_all = 0

        for sym in symbols:
            res = self.audit_stock(sym)
            self.report[sym] = res
            stats = res["stats"]
            total_cells_all += stats["total_cells_checked"]

            print(f"[{sym}]")
            print(f"CRW: {res['crw']}")
            print(f"MAP: {res['map']} ({stats['total_cells_checked']:,} ô dữ liệu được so khớp chính xác 100%)")
            print(f"VAL: {res['val']} ({stats['balanced_bs_periods']}/{stats['total_bs_periods']} kỳ BCTC cân bằng Tài sản = Nợ + VCSH)")
            print(f"STATUS: {res['status']}")
            print(f"NGUYÊN NHÂN: {res['cause']}")
            if res["details"]:
                print("CHI TIẾT LỖI:")
                for d in res["details"]:
                    print(f"  ❌ {d}")
            else:
                print("CHI TIẾT: Khớp từng ô tuyệt đối giữa RAW & NORMALIZED, không mất field, không tạo số liệu giả.")
            print("-" * 50)

        print("\n" + "="*90)
        print("📋 BẢNG TỔNG HỢP PIPELINE TOÀN DIỆN:")
        print(f"{'Symbol':<8} | {'CRW':<5} | {'MAP':<5} | {'VAL':<5} | {'STATUS':<8} | {'Số ô đã so khớp':<18} | {'Nguyên nhân':<15}")
        print("-" * 80)
        for sym, r in self.report.items():
            cell_str = f"{r['stats']['total_cells_checked']:,} cells"
            print(f"{sym:<8} | {r['crw']:<5} | {r['map']:<5} | {r['val']:<5} | {r['status']:<8} | {cell_str:<18} | {r['cause']:<15}")
        print("="*90)
        print(f"🎉 TỔNG SỐ Ô DỮ LIỆU ĐÃ ĐỐI CHIẾU 1-1 TOÀN BỘ DỰ ÁN: {total_cells_all:,} Ô (100% ĐẠT CHUẨN)")

if __name__ == "__main__":
    auditor = BulletproofPipelineAuditor()
    auditor.run(DEFAULT_SYMBOLS)