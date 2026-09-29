"""Entrypoint for FinMind Data Pipeline crawler."""

import argparse
import sys
from pathlib import Path

# Add src directory to sys.path
SRC_DIR = Path(__file__).resolve().parent
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from scrapers.cafef_pdf_collector import CafeFPDFCollector, parse_years


def main(argv=None):
    parser = argparse.ArgumentParser(description="FinMind data and PDF ingestion")
    parser.add_argument(
        "--pdf",
        action="store_true",
        help="Download financial-statement/annual-report PDFs from CafeF instead of crawling Vietcap/Entrade data",
    )
    parser.add_argument(
        "--symbols",
        help="Comma-separated target tickers (default: all 10 project companies)",
    )
    parser.add_argument(
        "--years",
        help="Comma-separated years for PDF mode (default: current year and prior two years)",
    )
    parser.add_argument(
        "--all-years",
        action="store_true",
        help="In PDF mode, include all years available on CafeF",
    )
    parser.add_argument(
        "--categories",
        default="financial,annual",
        help="PDF categories: financial,annual (default: financial,annual)",
    )
    parser.add_argument(
        "--refresh",
        action="store_true",
        help="Redownload existing PDFs and refresh their local copies",
    )
    args = parser.parse_args(argv)

    symbols = [item.strip().upper() for item in args.symbols.split(",") if item.strip()] if args.symbols else None

    if args.pdf:
        if args.all_years and args.years:
            parser.error("Use either --all-years or --years, not both")
        try:
            years = None if args.all_years else parse_years(args.years)
        except ValueError as exc:
            parser.error(str(exc))
        categories = [item.strip().lower() for item in args.categories.split(",") if item.strip()]
        collector = CafeFPDFCollector()
        collector.run(symbols=symbols, years=years, categories=categories, refresh=args.refresh)
        return

    if args.years or args.all_years or args.refresh or args.categories != "financial,annual":
        parser.error("--years, --all-years, --categories, and --refresh require --pdf")
    from scrapers.direct_vn_collector import VietnamStockDataCollector, TARGET_SYMBOLS

    collector = VietnamStockDataCollector()
    collector.run_all(symbols or TARGET_SYMBOLS)

if __name__ == "__main__":
    main()
