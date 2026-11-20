"""Run the Entrade/Vietcap API collector for the configured companies."""

import argparse
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[2]
FINANCIAL_DIR=Path(__file__).resolve().parent
if str(FINANCIAL_DIR) not in sys.path:
    sys.path.insert(0,str(FINANCIAL_DIR))
if str(ROOT) not in sys.path:
    sys.path.insert(0,str(ROOT))

from collect_financial_data import COMPANIES_INFO, TARGET_SYMBOLS, VietnamStockDataCollector


def main(argv=None):
    parser = argparse.ArgumentParser(description="Collect and normalize financial data")
    parser.add_argument(
        "--symbols",
        help="Comma-separated ticker symbols (default: all configured companies)",
    )
    parser.add_argument('--financial-only',action='store_true',help='Capture financial data independently of prices')
    parser.add_argument('--output-root',type=Path,help='Root for new immutable financial capture directories')
    args = parser.parse_args(argv)

    symbols = (
        [item.strip().upper() for item in args.symbols.split(",") if item.strip()]
        if args.symbols
        else TARGET_SYMBOLS
    )
    unknown = sorted(set(symbols) - set(TARGET_SYMBOLS))
    if unknown:
        parser.error(f"Unknown symbols: {', '.join(unknown)}")

    if args.financial_only:
        from data_pipeline.financial_data.financial_capture import capture_financial
        output=args.output_root or Path(__file__).resolve().parent/'captures'
        result=capture_financial(symbols,output,COMPANIES_INFO)
        print(f"BCTC capture: {result['status']}; {result['run_dir']}")
        return 0 if result['status']=='complete' else 1
    if args.output_root:
        parser.error('--output-root requires --financial-only')

    VietnamStockDataCollector().run_all(symbols)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
