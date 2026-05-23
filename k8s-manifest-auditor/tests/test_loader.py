"""Tests for src.loader."""

from __future__ import annotations

from pathlib import Path

import pytest

from src.loader import LoaderError, iter_yaml_files, load_documents


def test_load_single_doc(tmp_path: Path) -> None:
    f = tmp_path / "dep.yaml"
    f.write_text(
        "apiVersion: apps/v1\nkind: Deployment\nmetadata:\n  name: foo\n",
        encoding="utf-8",
    )
    docs = load_documents(f)
    assert len(docs) == 1
    assert docs[0].kind == "Deployment"
    assert docs[0].name == "foo"
    assert docs[0].namespace is None


def test_load_multidoc_skips_empty_and_non_mapping(tmp_path: Path) -> None:
    f = tmp_path / "multi.yaml"
    f.write_text(
        "---\n"
        "apiVersion: v1\n"
        "kind: ConfigMap\n"
        "metadata:\n  name: a\n"
        "---\n"
        "---\n"
        "apiVersion: v1\n"
        "kind: Service\n"
        "metadata:\n  name: b\n  namespace: ns\n"
        "---\n"
        "just-a-string\n",
        encoding="utf-8",
    )
    docs = load_documents(f)
    kinds = [d.kind for d in docs]
    assert kinds == ["ConfigMap", "Service"]
    assert docs[1].namespace == "ns"


def test_load_invalid_yaml_raises(tmp_path: Path) -> None:
    f = tmp_path / "bad.yaml"
    f.write_text("foo: [\n  - unclosed\n", encoding="utf-8")
    with pytest.raises(LoaderError):
        load_documents(f)


def test_iter_yaml_files_directory(tmp_path: Path) -> None:
    (tmp_path / "a.yaml").write_text("kind: A\n", encoding="utf-8")
    (tmp_path / "b.yml").write_text("kind: B\n", encoding="utf-8")
    sub = tmp_path / "sub"
    sub.mkdir()
    (sub / "c.yaml").write_text("kind: C\n", encoding="utf-8")
    (tmp_path / "skip.txt").write_text("not yaml", encoding="utf-8")
    found = sorted(p.name for p in iter_yaml_files(tmp_path))
    assert found == ["a.yaml", "b.yml", "c.yaml"]


def test_iter_yaml_files_single_file(tmp_path: Path) -> None:
    f = tmp_path / "x.yaml"
    f.write_text("kind: X\n", encoding="utf-8")
    found = list(iter_yaml_files(f))
    assert found == [f]


def test_iter_yaml_files_missing(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        list(iter_yaml_files(tmp_path / "nope"))
