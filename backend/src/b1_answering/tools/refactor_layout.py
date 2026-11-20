"""Migration tool to restructure b1_answering package into canonical layout."""
from __future__ import annotations

import argparse
from pathlib import Path
import sys

MOVE_MAP = {
    "policy.py": "core/policy.py",
    "citations.py": "evidence/citations.py",
    "prompt.py": "evidence/prompt.py",
    "gemini.py": "providers/gemini.py",
    "service.py": "application/service.py",
    "dialogue.py": "application/dialogue.py",
    "hoi.py": "cli/main.py",
    "limits.json": "config/limits.json",
}

SUBPACKAGES = ["application", "cli", "config", "core", "evidence", "providers"]

ROOT_INIT = """\"""Compatibility registry for b1_answering layout.""\"""
import sys
from .core import policy
from .evidence import citations, prompt
from .providers import gemini
from .application import service, dialogue

_ALIASES = {
    "policy": policy,
    "citations": citations,
    "prompt": prompt,
    "gemini": gemini,
    "service": service,
    "dialogue": dialogue,
}
for _name, _mod in _ALIASES.items():
    sys.modules[f"{__name__}.{_name}"] = _mod
    globals()[_name] = _mod
"""

ROOT_HOI = """\"""Legacy CLI entrypoint shim.""\"""
import sys
from pathlib import Path

_backend = Path(__file__).resolve().parents[2]
if str(_backend) not in sys.path:
    sys.path.insert(0, str(_backend))

from src.b1_answering.cli.main import (
    DEMO_PACK,
    DEMO_PASSAGE,
    FixtureProvider,
    run_cli,
    main,
    display,
)

if __name__ == "__main__":
    raise SystemExit(main())
"""

ROOT_MAIN = """\"""Entrypoint for python -m src.b1_answering.""\"""
from .cli.main import main

if __name__ == "__main__":
    raise SystemExit(main())
"""


def _transform_content(rel_dest: str, text: str) -> str:
    if rel_dest == "core/policy.py":
        return text.replace(
            "Path(__file__).with_name('limits.json')",
            "Path(__file__).resolve().parents[1] / 'config' / 'limits.json'",
        )
    if rel_dest == "providers/gemini.py":
        return text.replace("from .policy import ", "from ..core.policy import ")
    if rel_dest in ("application/service.py", "application/dialogue.py"):
        return (
            text.replace("from .policy import ", "from ..core.policy import ")
            .replace("from .citations import ", "from ..evidence.citations import ")
            .replace("from .prompt import ", "from ..evidence.prompt import ")
            .replace("from .gemini import ", "from ..providers.gemini import ")
        )
    if rel_dest == "cli/main.py":
        out = text.replace("parents[2]", "parents[3]")
        for mod, pkg in [("policy", "core"), ("citations", "evidence"), ("prompt", "evidence"), ("gemini", "providers"), ("service", "application"), ("dialogue", "application")]:
            out = out.replace(f"src.b1_answering.{mod}", f"src.b1_answering.{pkg}.{mod}")
        return out
    return text


def build_layout(source: Path, destination: Path) -> None:
    source, destination = Path(source), Path(destination)
    def linked(path):
        return path.is_symlink() or getattr(path, 'is_junction', lambda: False)()
    if any(linked(p) for p in (source, *source.parents, destination, *destination.parents)):
        raise ValueError('Source/destination symlink or junction not supported')
    src = source.resolve()
    dest = destination.resolve()
    if not src.is_dir() or src.name != 'b1_answering':
        raise ValueError(f'Invalid source directory: {source}')
    if src == dest or src in dest.parents or dest in src.parents:
        raise ValueError('Source and destination must be distinct non-nested paths')
    if dest.exists():
        raise FileExistsError(f'Destination must not exist: {destination}')

    snapshots: dict[str, bytes] = {}
    for p in src.rglob("*"):
        if linked(p):
            raise ValueError(f"Symlinks not supported in source: {p}")
        if p.is_file():
            rel = p.relative_to(src).as_posix()
            if "__pycache__" in p.parts or rel.endswith(".pyc"):
                continue
            snapshots[rel] = p.read_bytes()

    output_files: dict[str, bytes] = {}
    for rel, content in snapshots.items():
        target = MOVE_MAP.get(rel, 'docs/' + rel if '/' not in rel and (rel.endswith('_CONTRACT.md') or rel == 'CONTRACT.md') else rel)
        if target in output_files:
            raise ValueError(f'Output path collision: {target}')
        if rel in MOVE_MAP:
            dest_rel = MOVE_MAP[rel]
            text = content.decode("utf-8")
            output_files[dest_rel] = _transform_content(dest_rel, text).encode("utf-8")
        elif "/" not in rel and (rel.endswith("_CONTRACT.md") or rel == "CONTRACT.md"):
            output_files[f"docs/{rel}"] = content
        elif rel == "__init__.py":
            continue
        else:
            output_files[rel] = content

    for sub in SUBPACKAGES:
        init_path = f"{sub}/__init__.py"
        if init_path not in output_files:
            output_files[init_path] = b""

    output_files["__init__.py"] = ROOT_INIT.encode("utf-8")
    output_files["hoi.py"] = ROOT_HOI.encode("utf-8")
    output_files["__main__.py"] = ROOT_MAIN.encode("utf-8")

    dest.mkdir(parents=True, exist_ok=False)
    for rel_path, data in output_files.items():
        out_path = dest / rel_path
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_bytes(data)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build structured b1_answering layout")
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--destination", required=True, type=Path)
    args = parser.parse_args(argv)
    build_layout(args.source, args.destination)
    return 0


if __name__ == "__main__":
    sys.exit(main())
