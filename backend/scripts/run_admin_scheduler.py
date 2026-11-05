"""One local scheduler process. Schedule stays disabled until enabled in admin."""
import argparse
import sys
import time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.core.config import get_settings
from src.documents.admin_ingestion import Queue, crawl_job


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--once', action='store_true')
    args = parser.parse_args()
    q = Queue(get_settings().admin_ingestion_directory)
    while True:
        try:
            ident = q.due()
            if ident: crawl_job(q, ident)
        except ValueError:
            pass  # A manual job owns the queue. Try next tick.
        if args.once: break
        time.sleep(30)


if __name__ == '__main__': main()
