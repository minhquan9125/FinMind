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

SYMBOLS = ["FPT", "HPG", "MWG", "SSI", "TCB", "VCB", "VIC", "VNM"]

COMPANIES_INFO = {
    "FPT": {"name": "Công ty Cổ phần FPT", "name_en": "FPT Corporation", "exchange": "HOSE", "industry": "TECH"},
    "HPG": {"name": "Công ty Cổ phần Tập đoàn Hòa Phát", "name_en": "Hoa Phat Group", "exchange": "HOSE", "industry": "STEEL"},
    "MWG": {"name": "Công ty Cổ phần Đầu tư Thế Giới Di Động", "name_en": "Mobile World Investment Corp", "exchange": "HOSE", "industry": "RETAIL"},
    "SSI": {"name": "Công ty Cổ phần Chứng khoán SSI", "name_en": "SSI Securities Corporation", "exchange": "HOSE", "industry": "FINANCE"},
    "TCB": {"name": "Ngân hàng TMCP Kỹ thương Việt Nam", "name_en": "Techcombank", "exchange": "HOSE", "industry": "BANK"},
    "VCB": {"name": "Ngân hàng TMCP Ngoại thương Việt Nam", "name_en": "Vietcombank", "exchange": "HOSE", "industry": "BANK"},
    "VIC": {"name": "Tập đoàn Vingroup - CTCP", "name_en": "Vingroup JSC", "exchange": "HOSE", "industry": "REAL_ESTATE"},
    "VNM": {"name": "Công ty Cổ phần Sữa Việt Nam", "name_en": "Vinamilk", "exchange": "HOSE", "industry": "CONSUMER"},
}

INDUSTRIES = [
    ("TECH", "Công nghệ thông tin"),
    ("STEEL", "Thép & Vật liệu xây dựng"),
    ("RETAIL", "Bán lẻ"),
    ("FINANCE", "Dịch vụ tài chính / Chứng khoán"),
    ("BANK", "Ngân hàng"),
    ("REAL_ESTATE", "Bất động sản"),
    ("CONSUMER", "Hàng tiêu dùng"),
]


async def main():
    print(f"[*] Connecting to Supabase...")
    conn = await asyncpg.connect(DATABASE_URL, statement_cache_size=0)
    print("  -> Connected successfully!")

    try:
        # 1. Ingest Industries
        print("\n[1/4] Ingesting Industries...")
        for code, name in INDUSTRIES:
            await conn.execute(
                """
                INSERT INTO public.industries (code, name)
                VALUES ($1, $2)
                ON CONFLICT (code) DO UPDATE SET name = EXCLUDED.name;
                """,
                code, name,
            )

        # 2. Ingest Companies
        print("[2/4] Ingesting Companies...")
        for sym, info in COMPANIES_INFO.items():
            await conn.execute(
                """
                INSERT INTO public.companies (symbol, name, name_en, exchange, industry_code)
                VALUES ($1, $2, $3, $4, $5)
                ON CONFLICT (symbol) DO UPDATE SET
                    name = EXCLUDED.name,
                    name_en = EXCLUDED.name_en,
                    exchange = EXCLUDED.exchange,
                    industry_code = EXCLUDED.industry_code;
                """,
                sym, info["name"], info["name_en"], info["exchange"], info["industry"],
            )

        # Process each JSON file
        for sym in SYMBOLS:
            file_path = DATA_DIR / f"{sym}.json"
            if not file_path.exists():
                print(f"  [!] File not found: {file_path}")
                continue

            print(f"\n[*] Processing {sym} ({file_path.name})...")
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            dataset_id = f"ds_{sym.lower()}_v1"
            dataset_version = data.get("dataset_version", "20260915T093340Z")

            # 3. Dataset record
            await conn.execute(
                """
                INSERT INTO public.datasets (id, symbol, dataset_version, checksum, status, generated_at)
                VALUES ($1, $2, $3, $4, $5, now())
                ON CONFLICT (id) DO NOTHING;
                """,
                dataset_id, sym, dataset_version, f"chk_{sym}", "PUBLISHED",
            )

            # 4. Ingest Price Bars (Entrade OHLCV)
            prices = data.get("price_history", [])
            print(f"  [3/4] Inserting {len(prices)} price bars for {sym}...")
            price_rows = []
            for p in prices:
                bar_id = f"pb_{sym.lower()}_{p['date']}"
                price_rows.append(
                    (
                        bar_id,
                        dataset_id,
                        p["date"],  # string format YYYY-MM-DD
                        float(p["open"]) if p.get("open") is not None else None,
                        float(p["high"]) if p.get("high") is not None else None,
                        float(p["low"]) if p.get("low") is not None else None,
                        float(p["close"]) if p.get("close") is not None else None,
                        int(p["volume"]) if p.get("volume") is not None else None,
                        int(p["source_timestamp"]) if p.get("source_timestamp") is not None else None,
                        "ENTRADE",
                        f"{sym}.json",
                    )
                )

            # Batch insert price bars
            for row in price_rows:
                await conn.execute(
                    """
                    INSERT INTO public.price_bars (id, dataset_id, date, open, high, low, close, volume, source_timestamp, source, source_file)
                    VALUES ($1, $2, $3::date, $4, $5, $6, $7, $8, $9, $10, $11)
                    ON CONFLICT (id) DO NOTHING;
                    """,
                    *row,
                )

            # 5. Ingest Financial Reports & Metrics
            sections = [
                ("income_statement", "INCOME_STATEMENT"),
                ("balance_sheet", "BALANCE_SHEET"),
                ("cash_flow", "CASH_FLOW"),
                ("financial_ratios", "RATIO"),
            ]

            total_obs = 0
            for sec_key, sec_name in sections:
                rows = data.get(sec_key, [])
                for r in rows:
                    period_label = r.get("period_label")
                    if not period_label:
                        continue

                    year = int(r.get("year", 2023))
                    quarter = int(r["quarter"]) if r.get("quarter") is not None else None
                    period_type = str(r.get("period_type", "QUARTER" if quarter else "YEAR"))

                    await conn.execute(
                        """
                        INSERT INTO public.reporting_periods (id, year, quarter, period_type)
                        VALUES ($1, $2, $3, $4)
                        ON CONFLICT (id) DO NOTHING;
                        """,
                        period_label, year, quarter, period_type,
                    )

                    report_id = f"rep_{sym.lower()}_{sec_name.lower()}_{period_label.lower()}"
                    await conn.execute(
                        """
                        INSERT INTO public.financial_reports (id, dataset_id, section, period_label, source, source_file)
                        VALUES ($1, $2, $3, $4, $5, $6)
                        ON CONFLICT (id) DO NOTHING;
                        """,
                        report_id, dataset_id, sec_name, period_label, "VIETCAP_VCI", f"{sym}.json",
                    )

                    for k, val in r.items():
                        if k in ["period_label", "period_type", "year", "quarter"] or val is None:
                            continue

                        metric_id = f"metric_{sec_name.lower()}_{k}"
                        await conn.execute(
                            """
                            INSERT INTO public.metrics (id, code, section, source)
                            VALUES ($1, $2, $3, $4)
                            ON CONFLICT (id) DO NOTHING;
                            """,
                            metric_id, k, sec_name, "VIETCAP_VCI",
                        )

                        obs_id = f"obs_{report_id}_{k}"
                        num_val = float(val) if isinstance(val, (int, float)) else None
                        json_val = str(val) if not isinstance(val, (int, float)) else None

                        await conn.execute(
                            """
                            INSERT INTO public.observations (id, report_id, metric_id, code, value, value_json, value_type)
                            VALUES ($1, $2, $3, $4, $5, $6, $7)
                            ON CONFLICT (id) DO NOTHING;
                            """,
                            obs_id, report_id, metric_id, k, num_val, json_val, "NUMBER" if num_val is not None else "TEXT",
                        )
                        total_obs += 1

            print(f"  [4/4] Financials & Metrics: Ingested {total_obs} observations.")

        print("\n=======================================================")
        print("🎉 INGESTION COMPLETED SUCCESSFULLY 100% INTO SUPABASE!")
        print("=======================================================")

    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
