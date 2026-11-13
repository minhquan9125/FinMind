"""Replay the frozen audit with only retired consumer sources archived.

Active Nhan classification sources still have to match their frozen hashes.
The original method, vectors, classifier, gold and audit implementation are kept.
"""
import hashlib
from importlib.machinery import SourceFileLoader
from importlib.util import module_from_spec, spec_from_loader

from run_s5_intent_review2 import ROOT, OUT
from run_s5_intent_reviewfix import read


ARCHIVE = 'outputs/s5_intent_review2_20261112/scope-archive/'
ARCHIVED_SOURCES = {
    'backend/src/retrieval_orchestration/intent_routing.py': ARCHIVE + 'intent_routing.py.snapshot',
    'backend/src/retrieval_orchestration/intent_handoff.py': ARCHIVE + 'intent_handoff.py.snapshot',
    'backend/scripts/audit_s5_intent_review2.py': ARCHIVE + 'audit_s5_intent_review2.py.snapshot',
}


def source_path(name):
    return ROOT / ARCHIVED_SOURCES.get(name, name)


def verify_sources(hashes):
    for name, digest in hashes.items():
        assert hashlib.sha256(source_path(name).read_bytes()).hexdigest() == digest, name


class FrozenSourceRoot:
    """Resolve only the three explicit historical source paths into the archive."""

    def __truediv__(self, name):
        return source_path(str(name))


def main():
    hashes = read(OUT / 'method.json')['source_hashes']
    verify_sources({name: hashes[name] for name in ARCHIVED_SOURCES})
    loader = SourceFileLoader('_frozen_s5_review2_auditor',
                              str(source_path('backend/scripts/audit_s5_intent_review2.py')))
    auditor = module_from_spec(spec_from_loader(loader.name, loader))
    loader.exec_module(auditor)
    auditor.ROOT = FrozenSourceRoot()
    auditor.main()


if __name__ == '__main__':
    main()
