"""Load the same configuration for demo startup and read-only preflight."""
import os
from pathlib import Path
from dotenv import dotenv_values


def load_demo_environment(backend=None):
    backend=Path(backend or Path(__file__).resolve().parents[1])
    values={}
    for path in (backend.parent/'.env',backend/'.env'):
        values.update({k:v for k,v in dotenv_values(path,encoding='utf-8-sig').items() if v is not None})
    # The shell/container environment always wins over dotenv files.
    for key,value in values.items():os.environ.setdefault(key,value)
    operator=dotenv_values(backend/'.env.operator',interpolate=False,encoding='utf-8-sig').get('DATABASE_URL')
    if operator:os.environ.setdefault('ADMIN_INGEST_DATABASE_URL',operator)
