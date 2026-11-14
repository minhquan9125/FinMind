"""One local scheduler process. Schedule stays disabled until enabled in admin."""
import argparse
import os
import sys
import time
from pathlib import Path
BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))
from src.core.config import get_settings
from src.documents.admin_ingestion import Queue
from src.documents.admin_pipeline import run_full


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--once', action='store_true')
    args = parser.parse_args()
    # Same private operator connection run_demo_backend.py uses; needed only for auto_index.
    from dotenv import dotenv_values
    writer = dotenv_values(BACKEND / '.env.operator', interpolate=False).get('DATABASE_URL')
    if writer:
        os.environ.setdefault('ADMIN_INGEST_DATABASE_URL', writer)
    settings = get_settings()
    q = Queue(settings.admin_ingestion_directory)
    while True:
        try:
            ident = q.due()
            if ident: run_full(q, ident, settings)
        except ValueError:
            pass  # A manual job owns the queue. Try next tick.
        if args.once: break
        time.sleep(30)


if __name__ == '__main__': main()
