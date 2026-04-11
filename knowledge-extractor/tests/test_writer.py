"""TripleWriter: dedup on (subject, object), schema shape, atomic write."""

from __future__ import annotations

import json
from pathlib import Path

from knowledge_extractor.base import RawTriple
from knowledge_extractor.writer import TripleWriter


def _triples(*specs):
    return [RawTriple(subject=s, relation=r, object=o) for s, r, o in specs]


def test_writer_dedupes_on_subject_object(tmp_path: Path):
    out = tmp_path / "out.json"
    w = TripleWriter()
    n = w.write(
        triples=_triples(
            ("dog", "is_a", "mammal"),
            ("dog", "is_a", "mammal"),  # exact dup
            ("dog", "is_a", "animal"),  # different object, kept
        ),
        output_path=str(out),
        relation="is_a",
        source="test",
        description="unit test",
        layer_band="knowledge",
    )
    assert n == 2
    payload = json.loads(out.read_text())
    pairs = {tuple(p) for p in payload["pairs"]}
    assert pairs == {("dog", "mammal"), ("dog", "animal")}


def test_writer_schema_fields(tmp_path: Path):
    out = tmp_path / "out.json"
    TripleWriter().write(
        triples=_triples(("a", "r", "b")),
        output_path=str(out),
        relation="r",
        source="src",
        description="desc",
        layer_band="syntax",
    )
    payload = json.loads(out.read_text())
    assert payload["source"] == "src"
    assert payload["relation"] == "r"
    assert payload["description"] == "desc"
    assert payload["layer_band"] == "syntax"
    assert payload["pair_count"] == 1
    assert payload["pairs"] == [["a", "b"]]
    assert "extracted" in payload  # timestamp, don't pin the value


def test_writer_dedup_ignores_relation_field(tmp_path: Path):
    """Two triples with the same (subject, object) but different relations
    still collapse because the writer only keys on (subject, object)."""
    out = tmp_path / "out.json"
    n = TripleWriter().write(
        triples=_triples(
            ("a", "is_a", "b"),
            ("a", "related_to", "b"),  # same subject+object
        ),
        output_path=str(out),
        relation="is_a",
        source="test",
        description="",
        layer_band="knowledge",
    )
    assert n == 1
