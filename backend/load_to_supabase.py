"""
Script nạp dữ liệu từ data/normalized/*.json lên Supabase Postgres.
Sử dụng financial_mapping.py để dịch key thô (isa16) → semantic (PROFIT_BEFORE_TAX).

Chạy: python backend/load_to_supabase.py
"""

import asyncio
import asyncpg
import json
import os
import glob
import sys
from datetime import datetime
from dotenv import load_dotenv

# Import mapping
sys.path.insert(0, os.path.dirname(__file__))
from financial_mapping import get_code, META_KEYS

# Load .env
env_path = os.path.join(os.path.dirname(__file__), ".env")
load_dotenv(env_path)

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    print("❌ Không tìm thấy DATABASE_URL trong backend/.env")
    sys.exit(1)

# asyncpg không hiểu prefix +asyncpg
if "+asyncpg" in DATABASE_URL:
    DATABASE_URL = DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://")

# Section mapping: json_key → section trong DB
SECTION_MAP = {
    "ratios": "RATIOS",
    "income_statement": "INCOME_STATEMENT",
    "balance_sheet": "BALANCE_SHEET",
    "cash_flow_statement": "CASH_FLOW",
}

# Sector map: crawler industry → DB sector
SECTOR_MAP = {
    "BANK": "Banking",
    "TECH": "Technology",
    "OTHER": "Other",
}


def find_json_dir():
    """Tìm thư mục chứa file normalized JSON."""
    candidates = [
        os.path.join(os.path.dirname(__file__), "data", "normalized"),      # backend/data/normalized
        os.path.join(os.path.dirname(__file__), "..", "data", "normalized"), # ../data/normalized
    ]
    for path in candidates:
        if os.path.isdir(path) and glob.glob(os.path.join(path, "*.json")):
            return os.path.abspath(path)
    return None


async def preload_metrics(conn, metric_defs):
    """Preload tất cả metrics vào 1 batch."""
    if not metric_defs:
        return
    print(f"📦 Preload {len(metric_defs)} metrics...")
    await conn.executemany("""
        INSERT INTO metrics (metric_id, code, section, source)
        VALUES ($1, $2, $3, 'VIETCAP_VCI')
        ON CONFLICT (metric_id) DO NOTHING;
    """, list(metric_defs))


def collect_metrics_from_file(data):
    """Duyệt 1 file JSON, trả về set (metric_id, code, section)."""
    metric_defs = set()
    fin = data.get("financial_data", {})
    for json_key, section in SECTION_MAP.items():
        rows = fin.get(json_key, [])
        for row in rows:
            for key, value in row.items():
                if key in META_KEYS:
                    continue
                if not isinstance(value, (int, float)) or isinstance(value, bool):
                    continue
                code = get_code(key, section)
                metric_id = f"{section}_{code}"
                metric_defs.add((metric_id, code, section))
    return metric_defs


async def load_company(conn, data):
    """Insert/update companies."""
    symbol = data["symbol"]
    sector = SECTOR_MAP.get(data.get("industry", "OTHER"), "Other")
    await conn.execute("""
        INSERT INTO companies (symbol, company_name, sector, exchange)
        VALUES ($1, $2, $3, $4)
        ON CONFLICT (symbol) DO UPDATE 
        SET company_name = EXCLUDED.company_name,
            sector = EXCLUDED.sector,
            exchange = EXCLUDED.exchange;
    """, symbol, data.get("company_name"), sector, data.get("exchange", "HOSE"))


async def load_dataset(conn, data):
    """Insert datasets."""
    symbol = data["symbol"]
    dataset_id = f"{symbol}_{data['dataset_version']}"
    generated_at = datetime.fromisoformat(
        data["generated_at"].replace("Z", "+00:00")
    ).replace(tzinfo=None)
    await conn.execute("""
        INSERT INTO datasets (dataset_id, symbol, dataset_version, generated_at, status)
        VALUES ($1, $2, $3, $4, 'PUBLISHED')
        ON CONFLICT (dataset_id) DO NOTHING;
    """, dataset_id, symbol, data["dataset_version"], generated_at)
    return dataset_id


async def load_price_bars(conn, data):
    """Insert price_bars."""
    symbol = data["symbol"]
    prices = data.get("price_history", [])
    if not prices:
        return 0

    records = []
    for p in prices:
        records.append((
            f"{symbol}_{p['date']}",
            symbol,
            datetime.strptime(p["date"], "%Y-%m-%d").date(),  # FIX Ở ĐÂY
            float(p.get("open", 0)),
            float(p.get("high", 0)),
            float(p.get("low", 0)),
            float(p.get("close", 0)),
            int(p.get("volume", 0)),
            int(p.get("source_timestamp", 0)),
            "ENTRADE",
        ))

    await conn.executemany("""
        INSERT INTO price_bars 
            (price_id, symbol, date, open, high, low, close, volume, 
             source_timestamp, source)
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
        ON CONFLICT (price_id) DO NOTHING;
    """, records)
    return len(records)
    """Insert price_bars."""
    symbol = data["symbol"]
    prices = data.get("price_history", [])
    if not prices:
        return 0

    records = []
    for p in prices:
        records.append((
            f"{symbol}_{p['date']}",
            symbol,
            p["date"],
            float(p.get("open", 0)),
            float(p.get("high", 0)),
            float(p.get("low", 0)),
            float(p.get("close", 0)),
            int(p.get("volume", 0)),
            int(p.get("source_timestamp", 0)),
            "ENTRADE",
        ))

    await conn.executemany("""
        INSERT INTO price_bars 
            (price_id, symbol, date, open, high, low, close, volume, 
             source_timestamp, source)
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
        ON CONFLICT (price_id) DO NOTHING;
    """, records)
    return len(records)


async def load_financial_data(conn, data):
    """Insert reporting_periods, financial_reports, observations."""
    symbol = data["symbol"]
    fin = data.get("financial_data", {})
    total_obs = 0

    for json_key, section in SECTION_MAP.items():
        rows = fin.get(json_key, [])
        if not rows:
            continue

        obs_batch = []

        for row in rows:
            period_label = row.get("period_label")
            if not period_label:
                continue

            # Parse period
            if "Q" in period_label:
                year = int(period_label.split("-")[0])
                quarter = int(period_label.split("-")[1].replace("Q", ""))
                period_type = "QUARTER"
            elif period_label.endswith("-YEAR"):
                year = int(period_label.split("-")[0])
                quarter = None
                period_type = "YEAR"
            else:
                # Format khác, thử parse year
                try:
                    year = int(period_label[:4])
                    quarter = None
                    period_type = "YEAR"
                except ValueError:
                    print(f"    ⚠️ Bỏ qua period không rõ format: {period_label}")
                    continue

            # Insert reporting_periods
            await conn.execute("""
                INSERT INTO reporting_periods (period_id, year, quarter, period_type)
                VALUES ($1, $2, $3, $4)
                ON CONFLICT (period_id) DO NOTHING;
            """, period_label, year, quarter, period_type)

            # Insert financial_reports
            report_id = f"{symbol}_{period_label}_{section}"
            await conn.execute("""
                INSERT INTO financial_reports 
                    (report_id, symbol, period_id, section, source)
                VALUES ($1, $2, $3, $4, 'VIETCAP_VCI')
                ON CONFLICT (report_id) DO NOTHING;
            """, report_id, symbol, period_label, section)

            # Duyệt từng field → observation
            for key, value in row.items():
                if key in META_KEYS:
                    continue
                if not isinstance(value, (int, float)) or isinstance(value, bool):
                    continue

                code = get_code(key, section)
                metric_id = f"{section}_{code}"
                obs_id = f"{report_id}_{code}"

                obs_batch.append((
                    obs_id, report_id, metric_id, code, float(value)
                ))

        # Batch insert observations cho section này
        if obs_batch:
            try:
                await conn.executemany("""
                    INSERT INTO observations 
                        (observation_id, report_id, metric_id, code, value)
                    VALUES ($1, $2, $3, $4, $5)
                    ON CONFLICT (observation_id) DO NOTHING;
                """, obs_batch)
                total_obs += len(obs_batch)
                print(f"    ✅ {section}: {len(obs_batch)} observations")
            except Exception as e:
                print(f"    ❌ {section} lỗi: {e}")

    return total_obs


async def main():
    print("=" * 70)
    print("🚀 BẮT ĐẦU NẠP DỮ LIỆU LÊN SUPABASE")
    print("=" * 70)

    json_dir = find_json_dir()
    if not json_dir:
        print("❌ Không tìm thấy thư mục data/normalized")
        return

    print(f"📂 Thư mục: {json_dir}")
    json_files = sorted(glob.glob(os.path.join(json_dir, "*.json")))
    print(f"📄 Tìm thấy {len(json_files)} file JSON\n")

    # Cache file data
    file_data = {}
    for fp in json_files:
        with open(fp, "r", encoding="utf-8") as f:
            file_data[fp] = json.load(f)

    # Collect ALL metrics across files → preload 1 lần
    all_metrics = set()
    for data in file_data.values():
        all_metrics |= collect_metrics_from_file(data)

    # Connect Supabase
    print("🔌 Kết nối Supabase...")
    try:
        conn = await asyncpg.connect(DATABASE_URL, ssl="require")
    except Exception as e:
        print(f"❌ Không kết nối được: {e}")
        return
    print("✅ Kết nối OK\n")

    try:
        # Preload metrics
        await preload_metrics(conn, all_metrics)
        print()

        total_symbols = 0
        total_prices = 0
        total_obs = 0

        for fp, data in file_data.items():
            symbol = data.get("symbol", "?")
            print(f"⏳ Xử lý {symbol}...")

            await load_company(conn, data)
            await load_dataset(conn, data)
            n_prices = await load_price_bars(conn, data)
            n_obs = await load_financial_data(conn, data)

            print(f"  📈 Prices: {n_prices}, Observations: {n_obs}\n")

            total_symbols += 1
            total_prices += n_prices
            total_obs += n_obs

        print("=" * 70)
        print(f"🎉 HOÀN TẤT!")
        print(f"   - Symbols: {total_symbols}")
        print(f"   - Prices: {total_prices}")
        print(f"   - Observations: {total_obs}")
        print(f"   - Metrics: {len(all_metrics)}")
        print("=" * 70)

    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(main())