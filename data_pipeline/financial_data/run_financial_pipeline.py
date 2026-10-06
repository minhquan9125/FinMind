"""Run the Entrade/Vietcap API collector for the configured companies."""

import argparse

from collect_financial_data import TARGET_SYMBOLS, VietnamStockDataCollector


def main(argv=None):
    parser = argparse.ArgumentParser(description="Collect and normalize financial data")
    parser.add_argument(
        "--symbols",
        help="Comma-separated ticker symbols (default: all configured companies)",
    )
    args = parser.parse_args(argv)

    symbols = (
        [item.strip().upper() for item in args.symbols.split(",") if item.strip()]
        if args.symbols
        else TARGET_SYMBOLS
    )
    unknown = sorted(set(symbols) - set(TARGET_SYMBOLS))
    if unknown:
        parser.error(f"Unknown symbols: {', '.join(unknown)}")

    VietnamStockDataCollector().run_all(symbols)


if __name__ == "__main__":
    main()
