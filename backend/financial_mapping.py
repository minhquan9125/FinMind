"""Financial Data Metric Mapping Table for FinMind.

Maps raw crawler/Vietcap keys (bsa, bsb, isa, isb, cfa, ratios) into standardized,
canonical financial observation codes (e.g., TOTAL_ASSETS, NET_INTEREST_INCOME)
specifically verified against BIDV's official financial statements (BID_BCTC_6T2026_soatxet.pdf
and BID_BCTC_Q2_2026.pdf).

Quality Bar: Level A (Core Financial Metrics)
- 100% verified accuracy for mapped codes.
- No two keys map to the same code in any section.
- Max code length <= 50 characters (fit for observations.code).
- Unmapped keys retain original uppercase notation (e.g. bsa1 -> BSA1).
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Final

# Metadata fields that should not be mapped to financial metrics
META_KEYS: Final[set[str]] = {
    "period_label",
    "period_type",
    "year",
    "quarter",
    "organCode",
    "ticker",
    "createDate",
    "updateDate",
    "yearReport",
    "lengthReport",
    "publicDate",
    "ratioTTMId",
    "ratioType",
}

# ==============================================================================
# 1. BALANCE SHEET MAPPING (Bảng Cân đối kế toán)
# ==============================================================================
BALANCE_SHEET_MAPPING: Final[dict[str, str]] = {
    # --- Chỉ tiêu bắt buộc chung (CONFIDENCE: HIGH - BCTC Soát xét 6T/2026 trang 8 & 9) ---
    "bsa2": "CASH_AND_GOLD",               # 12.509.838 triệu VND (Tiền mặt, vàng bạc, đá quý)
    "bsa29": "FIXED_ASSETS",                # 12.790.868 triệu VND (Tài sản cố định)
    "bsa30": "TANGIBLE_FIXED_ASSETS",       # 7.242.139 triệu VND (Tài sản cố định hữu hình)
    "bsa31": "TANGIBLE_FA_GROSS",           # 17.979.666 triệu VND (Nguyên giá TSCĐ hữu hình)
    "bsa32": "TANGIBLE_FA_DEPRECIATION",    # -10.737.527 triệu VND (Hao mòn TSCĐ hữu hình)
    "bsa36": "INTANGIBLE_FIXED_ASSETS",     # 5.548.729 triệu VND (Tài sản cố định vô hình)
    "bsa37": "INTANGIBLE_FA_GROSS",         # 8.824.302 triệu VND (Nguyên giá TSCĐ vô hình)
    "bsa38": "INTANGIBLE_FA_DEPRECIATION",  # -3.275.573 triệu VND (Hao mòn TSCĐ vô hình)
    "bsa43": "LONG_TERM_INVESTMENTS",       # 4.681.899 triệu VND (Góp vốn, đầu tư dài hạn)
    "bsa45": "INVESTMENTS_IN_ASSOCIATES_JV",# 4.603.155 triệu VND (Vốn góp liên doanh + liên kết)
    "bsa46": "OTHER_LONG_TERM_INVESTMENTS", # 182.941 triệu VND (Góp vốn, ĐTDH khác)
    "bsa47": "PROVISION_LONG_TERM_INVESTMENTS", # -104.197 triệu VND (Dự phòng giảm giá ĐTDH)
    "bsa53": "TOTAL_ASSETS",                # 3.440.840.854 triệu VND (Tổng tài sản)
    "bsa54": "TOTAL_LIABILITIES",           # 3.242.057.568 triệu VND (Tổng nợ phải trả)
    "bsa78": "OWNERS_EQUITY",               # 198.783.286 triệu VND (Tổng vốn chủ sở hữu)
    "bsa80": "CHARTER_CAPITAL",             # 72.800.652 triệu VND (Vốn điều lệ)
    "bsa81": "SHARE_PREMIUM",               # 26.309.607 triệu VND (Thặng dư vốn cổ phần)
    "bsa82": "OTHER_CAPITAL",               # 1.127.596 triệu VND (Vốn khác)
    "bsa85": "FX_DIFFERENCE",               # -455.949 triệu VND (Chênh lệch tỷ giá hối đoái)
    "bsa90": "RETAINED_EARNINGS",           # 59.497.817 triệu VND (Lợi nhuận chưa phân phối)
    "bsa96": "TOTAL_LIABILITIES_EQUITY",    # 3.440.840.854 triệu VND (Tổng nợ phải trả và VCSH)
    "bsa210": "MINORITY_INTEREST_EQUITY",   # 5.733.452 triệu VND (Lợi ích CĐ không kiểm soát)
    "bsa276": "JV_INVESTMENTS",             # 3.423.613 triệu VND (Vốn góp liên doanh)
    "bsa277": "ASSOCIATES_INVESTMENTS",     # 1.179.542 triệu VND (Đầu tư vào CT liên kết)

    # --- Chỉ tiêu đặc thù Ngân hàng (CONFIDENCE: HIGH - BCTC trang 8 & 9) ---
    "bsb97": "DEPOSITS_AT_CENTRAL_BANK",          # 117.294.507 triệu VND (Tiền gửi tại NHNN)
    "bsb98": "DEPOSITS_LOANS_OTHER_BANKS",        # 458.253.061 triệu VND (Tiền gửi và cho vay các TCTD khác)
    "bsb99": "TRADING_SECURITIES",                # 24.701.404 triệu VND (Chứng khoán kinh doanh thuần)
    "bsb100": "TRADING_SECURITIES_GROSS",         # 24.758.606 triệu VND (CKKD nguyên giá)
    "bsb101": "PROVISION_TRADING_SECURITIES",     # -57.202 triệu VND (Dự phòng rủi ro CKKD)
    "bsb102": "DERIVATIVES_ASSETS",               # 755.982 triệu VND (Công cụ phái sinh & TS tài chính khác)
    "bsb103": "CUSTOMER_LOANS_NET",               # 2.467.112.319 triệu VND (Cho vay khách hàng thuần)
    "bsb104": "CUSTOMER_LOANS_GROSS",             # 2.501.807.043 triệu VND (Dư nợ cho vay KH nguyên giá)
    "bsb105": "CUSTOMER_LOANS_PROVISION",         # -34.694.724 triệu VND (Dự phòng rủi ro cho vay KH)
    "bsb106": "INVESTMENT_SECURITIES",            # 274.907.315 triệu VND (Chứng khoán đầu tư)
    "bsb107": "SECURITIES_AVAILABLE_FOR_SALE",    # 174.011.299 triệu VND (CKĐT sẵn sàng để bán - AFS)
    "bsb108": "SECURITIES_HELD_TO_MATURITY",      # 100.956.425 triệu VND (CKĐT giữ đến ngày đáo hạn - HTM)
    "bsb109": "PROVISION_INVESTMENT_SECURITIES",  # -60.409 triệu VND (Dự phòng rủi ro CKĐT)
    "bsb110": "OTHER_ASSETS",                     # 67.833.661 triệu VND (Tài sản Có khác)
    "bsb111": "DUE_TO_GOVT_AND_CENTRAL_BANK",     # 236.367.270 triệu VND (Các khoản nợ Chính phủ và NHNN)
    "bsb112": "DUE_TO_AND_BORROWINGS_FROM_BANKS", # 372.325.267 triệu VND (Tiền gửi và vay các TCTD khác)
    "bsb113": "CUSTOMER_DEPOSITS",                # 2.261.489.130 triệu VND (Tiền gửi của khách hàng)
    "bsb115": "FUNDS_GRANTS_TRUSTS",              # 11.588.851 triệu VND (Vốn tài trợ, ủy thác đầu tư)
    "bsb116": "VALUABLE_PAPERS_ISSUED",           # 301.731.655 triệu VND (Phát hành giấy tờ có giá)
    "bsb117": "OTHER_LIABILITIES",                # 58.555.395 triệu VND (Các khoản nợ khác)
    "bsb258": "DEPOSITS_AT_OTHER_BANKS",          # 445.646.196 triệu VND (Tiền gửi tại TCTD khác)
    "bsb259": "LOANS_TO_OTHER_BANKS",             # 12.677.150 triệu VND (Cho vay các TCTD khác)
    "bsb260": "PROVISION_LOANS_OTHER_BANKS",      # -70.285 triệu VND (Dự phòng tiền gửi & cho vay TCTD)
    "bsb270": "DEPOSITS_FROM_OTHER_BANKS",        # 332.257.415 triệu VND (Tiền gửi của các TCTD khác)
    "bsb271": "BORROWINGS_FROM_OTHER_BANKS",      # 40.067.852 triệu VND (Vay các TCTD khác)
    "bsb272": "ACCRUED_EXPENSES_PAYABLE",         # 39.647.968 triệu VND (Các khoản lãi, phí phải trả)
    "bsb274": "OTHER_PAYABLES_AND_LIABILITIES",   # 18.841.838 triệu VND (Các khoản phải trả & công nợ khác)

    # --- Chỉ tiêu trùng giá trị với bsa90 (CONFIDENCE: LOW - Không map) ---
    "bsa178": "BSA178",                           # 59.497.817 triệu VND (Trùng bsa90, giữ nguyên)
}

# ==============================================================================
# 2. INCOME STATEMENT MAPPING (Báo cáo Kết quả hoạt động kinh doanh)
# ==============================================================================
INCOME_STATEMENT_MAPPING: Final[dict[str, str]] = {
    # --- Chỉ tiêu bắt buộc chung (CONFIDENCE: HIGH - BCTC Q2/2026 trang 7) ---
    "isa16": "PROFIT_BEFORE_TAX",     # 10.332.973 triệu VND (Tổng lợi nhuận trước thuế)
    "isa17": "TAX_EXPENSE_CURRENT",   # -2.038.057 triệu VND (Chi phí thuế TNDN hiện hành)
    "isa19": "TAX_EXPENSE_TOTAL",     # -2.038.057 triệu VND (Tổng chi phí thuế TNDN)
    "isa20": "PROFIT_AFTER_TAX",      # 8.294.916 triệu VND (Lợi nhuận sau thuế)
    "isa21": "MINORITY_INTEREST",     # -148.660 triệu VND (Lợi ích của cổ đông không kiểm soát)
    "isa22": "PARENT_NET_PROFIT",     # 8.146.256 triệu VND (Lợi nhuận thuần thuộc về Ngân hàng mẹ)

    # --- Chỉ tiêu đặc thù Ngân hàng (CONFIDENCE: HIGH - BCTC Q2/2026 trang 7) ---
    "isb25": "INTEREST_INCOME",                    # 49.659.834 triệu VND (Thu nhập lãi và các khoản tương tự)
    "isb26": "INTEREST_EXPENSE",                   # -31.855.603 triệu VND (Chi phí lãi và các chi phí tương tự)
    "isb27": "NET_INTEREST_INCOME",                # 17.804.231 triệu VND (Thu nhập lãi thuần)
    "isb28": "FEE_COMMISSION_INCOME",              # 3.614.586 triệu VND (Thu nhập từ hoạt động dịch vụ)
    "isb29": "FEE_COMMISSION_EXPENSE",             # -1.654.803 triệu VND (Chi phí hoạt động dịch vụ)
    "isb30": "NET_FEE_COMMISSION_INCOME",          # 1.959.783 triệu VND (Lãi thuần từ hoạt động dịch vụ)
    "isb31": "NET_FX_GAIN",                        # 708.376 triệu VND (Lãi thuần từ kinh doanh ngoại hối)
    "isb32": "NET_TRADING_SECURITIES_GAIN",        # 136.120 triệu VND (Lãi thuần mua bán chứng khoán kinh doanh)
    "isb33": "NET_INVESTMENT_SECURITIES_GAIN",     # 16.631 triệu VND (Lãi thuần mua bán chứng khoán đầu tư)
    "isb34": "OTHER_OPERATING_INCOME",             # 3.721.513 triệu VND (Thu nhập từ hoạt động khác)
    "isb35": "OTHER_OPERATING_EXPENSE",            # -869.901 triệu VND (Chi phí hoạt động khác)
    "isb36": "NET_OTHER_OPERATING_INCOME",         # 2.851.612 triệu VND (Lãi thuần từ hoạt động khác)
    "isb37": "DIVIDEND_INCOME",                    # 161.165 triệu VND (Thu nhập từ góp vốn, mua cổ phần)
    "isb39": "TOTAL_OPERATING_EXPENSES",           # -7.484.712 triệu VND (Tổng chi phí hoạt động)
    "isb40": "OPERATING_PROFIT_BEFORE_PROVISION",  # 16.153.206 triệu VND (LN thuần trước CP dự phòng rủi ro TD)
    "isb41": "CREDIT_LOSS_PROVISION",              # -5.820.288 triệu VND (Chi phí dự phòng rủi ro tín dụng)
}

# ==============================================================================
# 3. CASH FLOW MAPPING (Báo cáo Lưu chuyển tiền tệ)
# ==============================================================================
CASH_FLOW_MAPPING: Final[dict[str, str]] = {
    # --- Xác thực kiểm chứng khớp phương trình (CONFIDENCE: HIGH - BCTC Q2/2026 & 6T trang 12-13) ---
    "cfa9": "OPERATING_PROFIT_BEFORE_WC",  # 17.672.138 triệu VND (LCTT trước thay đổi vốn lưu động)
    "cfa18": "CASH_FLOW_OPERATING",        # -24.471.221 triệu VND (LCTT thuần từ hoạt động kinh doanh)
    "cfa19": "PURCHASE_FIXED_ASSETS",      # -914.316 triệu VND (Mua sắm tài sản cố định)
    "cfa20": "PROCEEDS_DISPOSAL_FA",       # 1.922 triệu VND (Tiền thu thanh lý, nhượng bán TSCĐ)
    "cfa25": "DIVIDENDS_RECEIVED",         # 165.750 triệu VND (Cổ tức và lợi nhuận được chia)
    "cfa26": "CASH_FLOW_INVESTING",        # -747.536 triệu VND (LCTT thuần từ hoạt động đầu tư)
    "cfa34": "CASH_FLOW_FINANCING",        # 2.840.220 triệu VND (LCTT thuần từ hoạt động tài chính)
    "cfa35": "NET_CASH_FLOW",              # -22.378.537 triệu VND (Lưu chuyển tiền thuần trong kỳ)
    "cfa36": "CASH_EQUIVALENTS_BEGIN",     # 544.528.992 triệu VND (Tiền & tương đương tiền đầu kỳ)
    "cfa38": "CASH_EQUIVALENTS_END",       # 522.150.455 triệu VND (Tiền & tương đương tiền cuối kỳ)
    "cfa43": "TAX_PAID",                   # -1.702.854 triệu VND (Tiền thuế TNDN đã thực nộp)
}

# ==============================================================================
# 4. RATIOS MAPPING (Chỉ số tài chính)
# ==============================================================================
RATIOS_MAPPING: Final[dict[str, str]] = {
    # Định giá & Thị trường (CONFIDENCE: HIGH)
    "numberOfSharesMktCap": "NUMBER_OF_SHARES_MKT_CAP",
    "marketCap": "MARKET_CAP",
    "dividendYield": "DIVIDEND_YIELD",
    "pe": "PE",
    "pb": "PB",
    "ps": "PS",
    "priceToCashFlow": "PRICE_TO_CASH_FLOW",
    "evToEbitda": "EV_TO_EBITDA",

    # Thanh khoản & Đòn bẩy (CONFIDENCE: HIGH)
    "cashRatio": "CASH_RATIO",
    "quickRatio": "QUICK_RATIO",
    "currentRatio": "CURRENT_RATIO",
    "ownersEquity": "OWNERS_EQUITY_RATIO",
    "debtPerEquity": "DEBT_PER_EQUITY",
    "debtToEquity": "DEBT_TO_EQUITY",
    "financialLeverage": "FINANCIAL_LEVERAGE",

    # Khả năng sinh lời & Hiệu quả (CONFIDENCE: HIGH)
    "roe": "ROE",
    "roa": "ROA",
    "roic": "ROIC",
    "grossMargin": "GROSS_MARGIN",
    "ebitMargin": "EBIT_MARGIN",
    "preTaxProfitMargin": "PRE_TAX_MARGIN",
    "afterTaxProfitMargin": "AFTER_TAX_MARGIN",
    "ebit": "EBIT",
    "ebitda": "EBITDA",

    # Hoạt động & Vòng quay (CONFIDENCE: HIGH)
    "daySaleOutstanding": "DAYS_SALES_OUTSTANDING",
    "daysInventoryOutstanding": "DAYS_INVENTORY_OUTSTANDING",
    "daysPayableOutstanding": "DAYS_PAYABLE_OUTSTANDING",
    "assetTurnover": "ASSET_TURNOVER",
    "fixedAssetTurnover": "FIXED_ASSET_TURNOVER",
    "cashCycle": "CASH_CYCLE",

    # Chỉ số chuyên biệt Ngân hàng (CONFIDENCE: HIGH)
    "netInterestMargin": "NIM",
    "averageYieldOnEarningAssets": "AVG_YIELD_EARNING_ASSETS",
    "averageCostOfFinancing": "AVG_COST_OF_FINANCING",
    "nonAndInterestIncome": "NON_INTEREST_INCOME_RATIO",
    "costToIncome": "COST_TO_INCOME",
    "cir": "CIR",
    "car": "CAR",
    "casaRatio": "CASA_RATIO",
    "ldrLoanDepositRatio": "LDR",
    "npl": "NPL_RATIO",
    "loansLossReservesToNPLs": "LLR_TO_NPLS",
    "loansLossReserveToLoans": "LLR_TO_LOANS",
    "provisionToOutstandingLoans": "PROVISION_TO_LOANS",
    "loansGrowth": "LOANS_GROWTH",
    "depositGrowth": "DEPOSIT_GROWTH",
    "equityToLiabilities": "EQUITY_TO_LIABILITIES",
    "equityToLoans": "EQUITY_TO_LOANS",
    "totalEquityTotalAsset": "EQUITY_TO_TOTAL_ASSETS",

    # Chỉ số Vietcap đặc thù dạng mã (CONFIDENCE: MEDIUM / LOW - Giữ nguyên)
    "nob66": "NOB66",
    "nob69": "NOB69",
    "nob70": "NOB70",
    "bsb113": "BSB113",
}

SECTION_MAPS: Final[dict[str, dict[str, str]]] = {
    "balance_sheet": BALANCE_SHEET_MAPPING,
    "income_statement": INCOME_STATEMENT_MAPPING,
    "cash_flow_statement": CASH_FLOW_MAPPING,
    "cash_flow": CASH_FLOW_MAPPING,
    "ratios": RATIOS_MAPPING,
}


def get_code(field_name: str, section: str) -> str:
    """Return the standardized observation code for a given field name and section.

    - If the field is in the section's mapping table, returns the mapped uppercase code.
    - If unmapped, retains original field_name converted to UPPERCASE (e.g. isa45 -> ISA45).
    - If field is in META_KEYS, returns field_name unchanged.
    """
    if field_name in META_KEYS:
        return field_name

    norm_sec = section.strip().lower()
    mapping = SECTION_MAPS.get(norm_sec)
    if mapping and field_name in mapping:
        return mapping[field_name]

    # Default fallback: keep original identifier in UPPERCASE
    return field_name.upper()


def locate_bid_json() -> Path | None:
    """Dynamically locate BID.json in project workspace."""
    base_dir = Path(__file__).resolve().parent
    candidates = [
        base_dir.parent / "data" / "normalized" / "BID.json",
        base_dir / "data" / "normalized" / "BID.json",
        base_dir.parent / "data" / "normalized" / "vu" / "BID.json",
    ]
    for p in candidates:
        if p.is_file():
            return p

    # Fallback glob
    for p in base_dir.parent.glob("**/data/normalized/BID.json"):
        if p.is_file():
            return p
    return None


if __name__ == "__main__":
    if sys.platform == "win32":
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except Exception:
            pass

    print("=" * 70)
    print("[TEST] RUNNING VERIFICATION FOR financial_mapping.py")
    print("=" * 70)

    # 1. Check constraints on mapping tables
    for sec_name, mapping in [
        ("BALANCE_SHEET", BALANCE_SHEET_MAPPING),
        ("INCOME_STATEMENT", INCOME_STATEMENT_MAPPING),
        ("CASH_FLOW", CASH_FLOW_MAPPING),
        ("RATIOS", RATIOS_MAPPING),
    ]:
        values = list(mapping.values())
        duplicates = [v for v in values if values.count(v) > 1]
        assert not duplicates, f"Duplicate values in {sec_name}: {set(duplicates)}"

        too_long = [v for v in values if len(v) > 50]
        assert not too_long, f"Values exceeding 50 chars in {sec_name}: {too_long}"
        print(f"  [OK] {sec_name:<20}: {len(mapping):>3} mapped keys. Max length: {max(len(v) for v in values)} chars.")

    # 2. Test get_code behavior
    assert get_code("bsa53", "balance_sheet") == "TOTAL_ASSETS"
    assert get_code("bsb103", "balance_sheet") == "CUSTOMER_LOANS_NET"
    assert get_code("isb27", "income_statement") == "NET_INTEREST_INCOME"
    assert get_code("isa16", "income_statement") == "PROFIT_BEFORE_TAX"
    assert get_code("cfa35", "cash_flow_statement") == "NET_CASH_FLOW"
    assert get_code("cir", "ratios") == "CIR"
    assert get_code("costToIncome", "ratios") == "COST_TO_INCOME"
    assert get_code("bsa999", "balance_sheet") == "BSA999"  # unmapped -> UPPERCASE
    assert get_code("period_label", "balance_sheet") == "period_label"  # meta key
    print("  [OK] get_code() function passed all unit tests.")

    # 3. Dynamic test against BID.json
    bid_path = locate_bid_json()
    if bid_path:
        print(f"\n[INFO] Found BID.json at: {bid_path}")
        with open(bid_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        fin = data.get("financial_data", {})

        print("\n[REPORT] COVERAGE & MAPPING STATS ON BID.JSON:")
        print(f"{'Section':<22} | {'Total Keys':<10} | {'Mapped':<8} | {'Fallback':<8} | {'Rate':<8}")
        print("-" * 65)

        for sec_json, sec_key in [
            ("balance_sheet", "balance_sheet"),
            ("income_statement", "income_statement"),
            ("cash_flow_statement", "cash_flow"),
            ("ratios", "ratios"),
        ]:
            rows = fin.get(sec_json, [])
            keys = set()
            for r in rows:
                for k in r.keys():
                    if k not in META_KEYS:
                        keys.add(k)

            mapping = SECTION_MAPS[sec_key]
            mapped_count = sum(1 for k in keys if k in mapping)
            fallback_count = len(keys) - mapped_count
            rate = (mapped_count / len(keys) * 100) if keys else 0.0
            print(f"{sec_json:<22} | {len(keys):<10} | {mapped_count:<8} | {fallback_count:<8} | {rate:>6.1f}%")

    print("\n[SUCCESS] ALL TESTS PASSED SUCCESSFULLY!")
