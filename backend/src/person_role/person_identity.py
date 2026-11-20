"""Apply upstream Person decisions to exact pinned mentions before extraction."""
import sqlite3
from contextlib import closing
from pathlib import Path
from ..wbs02_person_registry.person_registry import resolve_payload,status


def resolve_person_identity(envelope,store,companies=None,proposals=None):
    path=Path(store).resolve(strict=True)
    # Resolution only reads the store. Ingest/review use the explicit upstream CLI.
    with closing(sqlite3.connect(path.as_uri()+'?mode=ro',uri=True,timeout=30)) as conn:
        conn.row_factory=sqlite3.Row
        conn.execute('PRAGMA foreign_keys=ON')
        if (conn.execute('PRAGMA user_version').fetchone()[0]!=1 or
            conn.execute('PRAGMA application_id').fetchone()[0]!=1346720338):
            raise ValueError('Unsupported WBS02 Person registry store')
        result=resolve_payload(conn,envelope,companies,proposals)
        people=[e for e in result['entities'] if e['entity_type']=='Person']
        audit=dict(mode='WBS02_PERSON_REGISTRY_R2_PINNED_MENTIONS',
            resolved_person_entities=sum(e['resolution_status']=='resolved' for e in people),
            unresolved_person_entities=sum(e['resolution_status']!='resolved' for e in people),
            registry_counts=status(conn),registry_writes=0,relation_approvals_created=0,
            source_verification='CONTRACT_AND_SNAPSHOT_PINS_NOT_LIVE_DB_REPLAY')
        return result,audit
