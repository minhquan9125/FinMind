"""Throwaway PostgreSQL database for BCTC DB tests (test cluster 127.0.0.1:15434, never production 15433)."""
import re
from pathlib import Path
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[2]
SCHEMA = ROOT / 'docker/postgres/init/010_schema.sql'
MIGRATION = ROOT / 'supabase/migrations/20261112000000_financial_report_verifications.sql'
# quarantine_records extras that exist on the real VPS but not in 010_schema.sql.
QUARANTINE_EXTRAS = ('review_id uuid', 'reasons jsonb', 'candidate_payload jsonb', 'evaluation_payload jsonb')


def _local_schema_sql() -> str:
    sql = SCHEMA.read_text(encoding='utf-8')
    sql = re.sub(r'^\s*CREATE EXTENSION[^\n]*vector[^\n]*\n', '', sql, flags=re.M | re.I)
    # shortcut: pgvector missing on the test cluster, so embeddings become real[]; fine for non-vector tests.
    return re.sub(r'(?:public\.)?vector\(\d+\)', 'real[]', sql)


async def create_financial_db():
    """Return (admin_conn, conn, dbname); conn is connected to the fresh database."""
    import asyncpg
    admin = await asyncpg.connect(host='127.0.0.1', port=15434, user='finmind_test', database='postgres')
    name = 'frv_db_' + uuid4().hex[:12]
    await admin.execute(f'CREATE DATABASE {name}')
    conn = await asyncpg.connect(host='127.0.0.1', port=15434, user='finmind_test', database=name)
    await conn.execute(_local_schema_sql())
    for col in QUARANTINE_EXTRAS:
        await conn.execute(f'ALTER TABLE public.quarantine_records ADD COLUMN IF NOT EXISTS {col}')
    await conn.execute(MIGRATION.read_text(encoding='utf-8'))
    return admin, conn, name


async def drop_financial_db(admin, conn, name):
    await conn.close()
    await admin.execute(f'DROP DATABASE IF EXISTS {name} WITH (FORCE)')
    await admin.close()
