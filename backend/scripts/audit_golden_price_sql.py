"""Check structured price queries against Golden Q11-Q20 on the live DB.

All database transactions are read-only. The fixed expected values describe
the approved Golden dataset; report a mismatch if the source DB changes.
"""

import argparse
import asyncio
import json
import sys
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from src.core.db import connect, disconnect, get_pool
from src.documents.price_queries import query_price

from audit_golden_q01_q20 import load_golden


def rounded(value, places="0.01"):
    return Decimal(str(value)).quantize(Decimal(places), rounding=ROUND_HALF_UP)


def matches(number, result):
    data = result["data"]
    sources = result["sources"]
    if number == 11:
        return (rounded(data["first_close"]) == Decimal("58.96")
                and rounded(data["last_close"]) == Decimal("57.30")
                and rounded(data["change_percent"]) == Decimal("-2.82")
                and [row["trade_date"] for row in sources] == ["2026-04-09", "2026-10-06"])
    if number == 12:
        return (data["symbol"] == "MBB" and data["volume"] == 38940600
                and data["trade_date"] == "2026-05-20" and len(sources) == 1)
    if number == 13:
        return (rounded(data["highest_close"]) == Decimal("69.70")
                and data["highest_date"] == "2026-04-10"
                and rounded(data["lowest_close"]) == Decimal("56.56")
                and data["lowest_date"] == "2026-07-27" and len(sources) == 2)
    if number == 14:
        return (data["symbol"] == "CTR" and data["bar_count"] == 123
                and rounded(data["average_volume"], "1") == Decimal("316524"))
    if number == 15:
        bar = data["bar"]
        return (bar["trade_date"] == "2026-05-20"
                and [rounded(bar[key]) for key in ("open", "high", "low", "close")]
                == [Decimal("63.23"), Decimal("64.22"), Decimal("61.35"), Decimal("64.13")]
                and bar["price_id"] == sources[0]["price_id"])
    if number == 16:
        return (data["symbol"] == "NLG"
                and rounded(data["change_percent"]) == Decimal("-24.26")
                and len(data["compared_symbols"]) == 6 and len(sources) == 2)
    if number == 17:
        return (rounded(data["bar"]["close"]) == Decimal("63.90")
                and rounded(data["intraday_range"]) == Decimal("1.60")
                and data["bar"]["trade_date"] == "2026-07-27")
    if number == 18:
        return (data["total"] == 737 and data["counts"] == {
            "VCB": 123, "MBB": 122, "FPT": 123,
            "CTR": 123, "MSN": 123, "NLG": 123,
        })
    if number == 19:
        bar = data["bar"]
        return (bar["trade_date"] == "2026-04-23" and bar["volume"] == 35200000
                and [rounded(bar[key]) for key in ("open", "high", "low", "close")]
                == [Decimal("59.26"), Decimal("63.03"), Decimal("59.16"), Decimal("62.34")])
    if number == 20:
        return (rounded(data["first_close"]) == Decimal("19.65")
                and rounded(data["last_close"]) == Decimal("19.20")
                and rounded(data["change"]) == Decimal("-0.45")
                and rounded(data["change_percent"]) == Decimal("-2.29")
                and [row["trade_date"] for row in sources] == ["2026-09-30", "2026-10-06"])
    raise ValueError(f"Unsupported Golden Q{number:02d}")


async def run(args):
    questions = load_golden(ROOT / "Golden_TestSet_Lo1_Lo2_TinTuc_GiaCoPhieu.md")
    await connect()
    try:
        report = []
        for number in range(11, 21):
            try:
                result = await query_price(get_pool(), questions[number]["question"])
                passed = matches(number, result)
                report.append({"id": f"Q{number:02d}", "passed": passed,
                               "operation": result["operation"],
                               "data": result["data"], "sources": result["sources"]})
            except Exception as exc:
                report.append({"id": f"Q{number:02d}", "passed": False,
                               "error": f"{type(exc).__name__}: {exc}"})
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps({"questions": report}, ensure_ascii=False, indent=2) + "\n",
                            encoding="utf-8")
        for row in report:
            print(row["id"], "PASS" if row["passed"] else "FAIL", row.get("error", ""))
        print(f"Passed {sum(row['passed'] for row in report)}/{len(report)}; report: {args.out}")
    finally:
        await disconnect()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    asyncio.run(run(parser.parse_args()))
