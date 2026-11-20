"""financial_report_verifications is append-only and value-constrained (isolated test cluster)."""
from pathlib import Path
import unittest
from uuid import uuid4

MIGRATION = Path(__file__).resolve().parents[2] / 'supabase/migrations/20261112000000_financial_report_verifications.sql'
INSERT = ("INSERT INTO financial_report_verifications(verification_id,report_id,document_id,job_id,status) "
          "VALUES($1,$2,$3,$4,$5)")


class VerificationSchemaTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        import asyncpg
        self.admin = await asyncpg.connect(host='127.0.0.1', port=15434, user='finmind_test', database='postgres')
        self.dbname = 'frv_test_' + uuid4().hex[:12]
        await self.admin.execute(f'CREATE DATABASE {self.dbname}')
        self.c = await asyncpg.connect(host='127.0.0.1', port=15434, user='finmind_test', database=self.dbname)
        await self.c.execute(
            'CREATE TABLE financial_reports(report_id uuid PRIMARY KEY);'
            'CREATE TABLE documents(document_id uuid PRIMARY KEY);'
            'CREATE TABLE ingestion_jobs(job_id uuid PRIMARY KEY);')
        self.ids = [uuid4() for _ in range(3)]
        for t, i in zip(('financial_reports', 'documents', 'ingestion_jobs'), self.ids):
            await self.c.execute(f'INSERT INTO {t} VALUES($1)', i)
        sql = MIGRATION.read_text(encoding='utf-8')
        await self.c.execute(sql)
        await self.c.execute(sql)  # idempotent re-run

    async def asyncTearDown(self):
        await self.c.close()
        await self.admin.execute(f'DROP DATABASE IF EXISTS {self.dbname}')
        await self.admin.close()

    async def insert(self, status='VERIFIED'):
        vid = uuid4()
        await self.c.execute(INSERT, vid, *self.ids, status)
        return vid

    async def test_migration_creates_append_only_table(self):
        import asyncpg
        vid = await self.insert()
        row = await self.c.fetchrow('SELECT * FROM financial_report_verifications WHERE verification_id=$1', vid)
        self.assertEqual(row['statement_scope'], 'UNKNOWN')
        self.assertIsNotNone(row['verified_at'])
        for sql in ("UPDATE financial_report_verifications SET status='X'",
                    'DELETE FROM financial_report_verifications'):
            with self.assertRaisesRegex(asyncpg.RaiseError, 'append-only'):
                await self.c.execute(sql)
        with self.assertRaises(asyncpg.CheckViolationError):
            await self.insert('X')
        # supersedes_id self-FK
        await self.c.execute('INSERT INTO financial_report_verifications(report_id,status,supersedes_id) '
                             "VALUES($1,'PARTIAL',$2)", self.ids[0], vid)
        with self.assertRaises(asyncpg.ForeignKeyViolationError):
            await self.c.execute("INSERT INTO financial_report_verifications(report_id,status,supersedes_id) "
                                 "VALUES($1,'PARTIAL',$2)", self.ids[0], uuid4())

    async def test_truncate_is_rejected_without_losing_history(self):
        import asyncpg
        vid = await self.insert()
        with self.assertRaisesRegex(asyncpg.RaiseError, 'append-only'):
            await self.c.execute('TRUNCATE financial_report_verifications')
        self.assertEqual(await self.c.fetchval('SELECT verification_id FROM financial_report_verifications'), vid)

    async def test_migration_rerun_twice_preserves_history_and_truncate_protection(self):
        import asyncpg
        vid = await self.insert()
        sql = MIGRATION.read_text(encoding='utf-8')
        await self.c.execute(sql)
        await self.c.execute(sql)
        self.assertEqual(await self.c.fetchval('SELECT verification_id FROM financial_report_verifications'), vid)
        with self.assertRaisesRegex(asyncpg.RaiseError, 'append-only'):
            await self.c.execute('TRUNCATE financial_report_verifications')
        self.assertEqual(await self.c.fetchval('SELECT count(*) FROM financial_report_verifications'), 1)

    async def test_finance_roles_get_select_insert_only(self):
        # Roles are cluster-wide: create them if this test cluster lacks them, never drop them.
        for role in ('finmind_developer', 'finmind_graph_reader'):
            if not await self.admin.fetchval('SELECT EXISTS(SELECT 1 FROM pg_roles WHERE rolname=$1)', role):
                await self.admin.execute(f'CREATE ROLE {role} NOLOGIN')
        await self.c.execute(MIGRATION.read_text(encoding='utf-8'))
        expected = {('finmind_developer', 'SELECT'): True, ('finmind_developer', 'INSERT'): True,
                    ('finmind_graph_reader', 'SELECT'): True, ('finmind_graph_reader', 'INSERT'): False}
        for role in ('finmind_developer', 'finmind_graph_reader'):
            for privilege in ('SELECT', 'INSERT', 'UPDATE', 'DELETE', 'TRUNCATE'):
                with self.subTest(role=role, privilege=privilege):
                    self.assertEqual(await self.c.fetchval(
                        "SELECT has_table_privilege($1, 'public.financial_report_verifications', $2)", role, privilege),
                        expected.get((role, privilege), False))

    async def test_chat_runtime_has_no_financial_verification_privileges(self):
        if not await self.c.fetchval("SELECT EXISTS(SELECT 1 FROM pg_roles WHERE rolname='finmind_chat_runtime')"):
            self.skipTest('chat runtime role is not installed in this fixture')
        for privilege in ('SELECT', 'INSERT', 'UPDATE', 'DELETE', 'TRUNCATE'):
            with self.subTest(privilege=privilege):
                self.assertFalse(await self.c.fetchval(
                    "SELECT has_table_privilege('finmind_chat_runtime', 'public.financial_report_verifications', $1)",
                    privilege))


class BootstrapVerificationSchemaTests(VerificationSchemaTests):
    async def asyncSetUp(self):
        import asyncpg
        from backend.tests.financial_db_fixture import _local_schema_sql

        self.admin = await asyncpg.connect(host='127.0.0.1', port=15434, user='finmind_test', database='postgres')
        self.dbname = 'frv_bootstrap_' + uuid4().hex[:12]
        await self.admin.execute(f'CREATE DATABASE {self.dbname}')
        self.c = await asyncpg.connect(host='127.0.0.1', port=15434, user='finmind_test', database=self.dbname)
        # Execute bootstrap alone: applying migration here would hide missing bootstrap protection.
        await self.c.execute(_local_schema_sql())
        self.ids = [uuid4() for _ in range(3)]
        for table, identifier in zip(('financial_reports', 'documents', 'ingestion_jobs'), self.ids):
            column = {'financial_reports': 'report_id', 'documents': 'document_id', 'ingestion_jobs': 'job_id'}[table]
            await self.c.execute(f'INSERT INTO {table}({column}) VALUES($1)', identifier)


if __name__ == '__main__':
    unittest.main()
