"""YAML manifest loader.

Recursively walks a directory, parses each ``*.yaml`` / ``*.yml`` file
as a multi-document YAML stream, and yields one ``ParsedDoc`` per
document. Empty documents (a file containing only ``---`` separators)
are skipped silently. Files that are not valid YAML are surfaced as
``LoaderError`` so the CLI can decide whether to abort or continue.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, Iterator, List, Optional, Union

import yaml


YAML_SUFFIXES = {".yaml", ".yml"}


class LoaderError(Exception):
    """Raised when a YAML file cannot be parsed."""


@dataclass
class ParsedDoc:
    """One YAML document plus the path metadata needed for findings."""

    file: str
    doc_index: int
    body: Dict[str, Any]

    @property
    def kind(self) -> str:
        return str(self.body.get("kind", ""))

    @property
    def name(self) -> str:
        meta = self.body.get("metadata") or {}
        if isinstance(meta, dict):
            return str(meta.get("name", ""))
        return ""

    @property
    def namespace(self) -> Optional[str]:
        meta = self.body.get("metadata") or {}
        if isinstance(meta, dict):
            ns = meta.get("namespace")
            return str(ns) if ns is not None else None
        return None


def iter_yaml_files(root: Union[str, Path]) -> Iterator[Path]:
    """Yield every YAML file under ``root`` (recursively).

    If ``root`` is itself a file, it is yielded directly so callers can
    point the auditor at a single manifest.
    """

    p = Path(root)
    if p.is_file():
        if p.suffix.lower() in YAML_SUFFIXES:
            yield p
        return
    if not p.is_dir():
        raise FileNotFoundError(f"path does not exist: {p}")
    for child in sorted(p.rglob("*")):
        if child.is_file() and child.suffix.lower() in YAML_SUFFIXES:
            yield child


def load_documents(path: Union[str, Path]) -> List[ParsedDoc]:
    """Parse one YAML file into a list of ``ParsedDoc``.

    Multi-document files are split on ``---``. Documents that are
    ``None`` (e.g. a trailing separator) or that are not mappings
    (e.g. a stray scalar) are skipped — kubernetes manifests are
    always top-level mappings.
    """

    p = Path(path)
    try:
        with p.open("r", encoding="utf-8") as f:
            raw_docs = list(yaml.safe_load_all(f))
    except yaml.YAMLError as exc:
        raise LoaderError(f"{p}: invalid YAML: {exc}") from exc

    out: List[ParsedDoc] = []
    for idx, body in enumerate(raw_docs):
        if body is None:
            continue
        if not isinstance(body, dict):
            continue
        out.append(ParsedDoc(file=str(p), doc_index=idx, body=body))
    return out


def load_all(paths: Iterable[Union[str, Path]]) -> Iterator[ParsedDoc]:
    """Yield every ``ParsedDoc`` produced by loading ``paths``.

    ``paths`` can mix files and directories. Each directory is walked
    recursively via :func:`iter_yaml_files`.
    """

    seen: set = set()
    for p in paths:
        for f in iter_yaml_files(p):
            key = str(f.resolve())
            if key in seen:
                continue
            seen.add(key)
            for doc in load_documents(f):
                yield doc
