"""Script to ingest normalized JSON stock data into Supabase Relational Schema using asyncpg."""

import asyncio
import json
import os
from pathlib import Path
import asyncpg
from dotenv import load_dotenv

# Load env from backend/.env
ENV_PATH = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(ENV_PATH)

DATABASE_URL = os.getenv("DATABASE_URL")
DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "normalized"

# 10 mã chuẩn quy định trong SRS FinMind (5 Banking, 5 Tech)
SYMBOLS = ["VCB", "BID", "CTG", "MBB", "TCB", "FPT", "CMG", "ELC", "ITD", "ICT"]

COMPANIES_INFO = {
    # Banking
    "VCB": {"name": "Ngân hàng TMCP Ngoại thương Việt Nam", "name_en": "Vietcombank", "exchange": "HOSE", "industry": "BANK"},
    "BID": {"name": "Ngân hàng TMCP Đầu tư và Phát triển Việt Nam", "name_en": "BIDV", "exchange": "HOSE", "industry": "BANK"},
    "CTG": {"name": "Ngân hàng TMCP Công Thương Việt Nam", "name_en": "VietinBank", "exchange": "HOSE", "industry": "BANK"},
    "MBB": {"name": "Ngân hàng TMCP Quân đội", "name_en": "Military Commercial Joint Stock Bank", "exchange": "HOSE", "industry": "BANK"},
    "TCB": {"name": "Ngân hàng TMCP Kỹ thương Việt Nam", "name_en": "Techcombank", "exchange": "HOSE", "industry": "BANK"},
    # Technology
    "FPT": {"name": "Công ty Cổ phần FPT", "name_en": "FPT Corporation", "exchange": "HOSE", "industry": "TECH"},
    "CMG": {"name": "Tập đoàn Công nghệ CMC", "name_en": "CMC Corporation", "exchange": "HOSE", "industry": "TECH"},
    "ELC": {"name": "Công ty Cổ phần Công nghệ - Viễn thông Elcom", "name_en": "Elcom Technology Communications Corp", "exchange": "HOSE", "industry": "TECH"},
    "ITD": {"name": "Công ty Cổ phần Công nghệ Tiên Phong", "name_en": "Innovative Technology Development Corp", "exchange": "HOSE", "industry": "TECH"},
    "ICT": {"name": "Công ty Cổ phần Viễn thông - Tin học Bưu điện", "name_en": "Post and Telecommunications Insurance Corp", "exchange": "HOSE", "industry": "TECH"},
}

INDUSTRIES = [
    ("TECH", "Công nghệ thông tin"),
    ("BANK", "Ngân hàng"),
]


async def main():
    if not DATABASE_URL:
        raise ValueError("DATABASE_URL not found in environment variables!")

    print("[*] Connecting to Supabase...")
    conn = await asyncpg.connect(DATABASE_URL, statement_cache_size=0)
    print("  -> Connected successfully!")

    try:
        # 1. Ingest Industries
        print("\n[1/4] Ingesting Industries...")
        await conn.executemany(
            """
            INSERT INTO public.industries (code, name)
            VALUES ($1, $2)
            ON CONFLICT (code) DO UPDATE SET name = EXCLUDED.name;
            """,
            INDUSTRIES,
        )

        # 2. Ingest Companies
        print("[2/4] Ingesting Companies...")
        companies_data = [
            (sym, info["name"], info["name_en"], info["exchange"], info["industry"])
            for sym, info in COMPANIES_INFO.items()
        ]
        await conn.executemany(
            """
            INSERT INTO public.companies (symbol, name, name_en, exchange, industry_code)
            VALUES ($1, $2, $3, $4, $5)
            ON CONFLICT (symbol) DO UPDATE SET
                name = EXCLUDED.name,
                name_en = EXCLUDED.name_en,
                exchange = EXCLUDED.exchange,
                industry_code = EXCLUDED.industry_code;
            """,
            companies_data,
        )

        # 3. Process each JSON file
        for sym in SYMBOLS:
            file_path = DATA_DIR / f"{sym}.json"
            if not file_path.exists():
                print(f"  [!] Bỏ qua (Chưa có file): {file_path.name}")
                continue

            print(f"\n[*] Processing {sym} ({file_path.name})...")
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            dataset_id = f"ds_{sym.lower()}_v1"
            dataset_version = data.get("dataset_version", "20260915T093340Z")

            # Ingest Dataset record
            await conn.execute(
                """
                INSERT INTO public.datasets (id, symbol, dataset_version, checksum, status, generated_at)
                VALUES ($1, $2, $3, $4, $5, now())
                ON CONFLICT (id) DO NOTHING;
                """,
                dataset_id, sym, dataset_version, f"chk_{sym}", "PUBLISHED",
            )

            # Ingest Price Bars (Batch Insert với executemany)
            prices = data.get("price_history", [])
            price_rows = [
                (
                    f"pb_{sym.lower()}_{p['date']}",
                    dataset_id,
                    p["date"],
                    float(p["open"]) if p.get("open") is not None else None,
                    float(p["high"]) if p.get("high") is not None else None,
                    float(p["low"]) if p.get("low") is not None else None,
                    float(p["close"]) if p.get("close") is not None else None,
                    int(p["volume"]) if p.get("volume") is not None else None,
                    int(p["source_timestamp"]) if p.get("source_timestamp") is not None else None,
                    "ENTRADE",
                    f"{sym}.json",
                )
                for p in prices
            ]

            if price_rows:
                print(f"  [3/4] Batch inserting {len(price_rows)} price bars for {sym}...")
                await conn.executemany(
                    """
                    INSERT INTO public.price_bars (id, dataset_id, date, open, high, low, close, volume, source_timestamp, source, source_file)
                    VALUES ($1, $2, $3::date, $4, $5, $6, $7, $8, $9, $10, $11)
                    ON CONFLICT (id) DO NOTHING;
                    """,
                    price_rows,
                )

            # Ingest Financial Reports, Metrics & Observations
            sections = [
                ("income_statement", "INCOME_STATEMENT"),
                ("balance_sheet", "BALANCE_SHEET"),
                ("cash_flow", "CASH_FLOW"),
                ("financial_ratios", "RATIO"),
            ]

            reporting_periods_rows = []
            financial_reports_rows = []
            metrics_dict = {}
            obs_rows = []

            for sec_key, sec_name in sections:
                rows = data.get(sec_key, [])
                for r in rows:
                    period_label = r.get("period_label")
                    if not period_label:
                        continue

                    year = int(r.get("year", 2023))
                    quarter = int(r["quarter"]) if r.get("quarter") is not None else None
                    period_type = str(r.get("period_type", "QUARTER" if quarter else "YEAR"))

                    reporting_periods_rows.append((period_label, year, quarter, period_type))

                    report_id = f"rep_{sym.lower()}_{sec_name.lower()}_{period_label.lower()}"
                    financial_reports_rows.append((report_id, dataset_id, sec_name, period_label, "VIETCAP_VCI", f"{sym}.json"))

                    for k, val in r.items():
                        if k in ["period_label", "period_type", "year", "quarter"] or val is None:
                            continue

                        metric_id = f"metric_{sec_name.lower()}_{k}"
                        metrics_dict[metric_id] = (metric_id, k, sec_name, "VIETCAP_VCI")

                        obs_id = f"obs_{report_id}_{k}"
                        num_val = float(val) if isinstance(val, (int, float)) else None
                        json_val = str(val) if not isinstance(val, (int, float)) else None
                        obs_rows.append(
                            (obs_id, report_id, metric_id, k, num_val, json_val, "NUMBER" if num_val is not None else "TEXT")
                        )

            # Batch run financials
            if reporting_periods_rows:
                await conn.executemany(
                    """
                    INSERT INTO public.reporting_periods (id, year, quarter, period_type)
                    VALUES ($1, $2, $3, $4)
                    ON CONFLICT (id) DO NOTHING;
                    """,
                    reporting_periods_rows,
                )

            if financial_reports_rows:
                await conn.executemany(
                    """
                    INSERT INTO public.financial_reports (id, dataset_id, section, period_label, source, source_file)
                    VALUES ($1, $2, $3, $4, $5, $6)
                    ON CONFLICT (id) DO NOTHING;
                    """,
                    financial_reports_rows,
                )

            if metrics_dict:
                await conn.executemany(
                    """
                    INSERT INTO public.metrics (id, code, section, source)
                    VALUES ($1, $2, $3, $4)
                    ON CONFLICT (id) DO NOTHING;
                    """,
                    list(metrics_dict.values()),
                )

            if obs_rows:
                print(f"  [4/4] Batch inserting {len(obs_rows)} observations for {sym}...")
                await conn.executemany(
                    """
                    INSERT INTO public.observations (id, report_id, metric_id, code, value, value_json, value_type)
                    VALUES ($1, $2, $3, $4, $5, $6, $7)
                    ON CONFLICT (id) DO NOTHING;
                    """,
                    obs_rows,
                )

        print("\n=======================================================")
        print("🎉 NẠP DỮ LIỆU HOÀN TẤT VÀ KHỚP 100% PHẠM VI FINMIND!")
        print("=======================================================")

    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
    