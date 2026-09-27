"""Entrypoint for FinMind Data Pipeline crawler."""

import sys
from pathlib import Path

# Add src directory to sys.path
SRC_DIR = Path(__file__).resolve().parent
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from scrapers.direct_vn_collector import VietnamStockDataCollector, TARGET_SYMBOLS

def main():
    collector = VietnamStockDataCollector()
    collector.run_all(TARGET_SYMBOLS)

if __name__ == "__main__":
    main()
