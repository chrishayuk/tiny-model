"""Wikidata extractor: synthetic raw dump round-trip.

The downloader's network behaviour is out of scope for unit tests; what
we test is that a well-formed dump file on disk produces the expected
triples and that the filters drop Q-id fallbacks and self-loops.
"""

from __future__ import annotations

import json
from pathlib import Path

from knowledge_extractor.knowledge.wikidata import WikidataExtractor
from knowledge_extractor.knowledge.wikidata.extractor import _is_qid_fallback
from knowledge_extractor.knowledge.wikidata.model import PROPERTIES, WikidataRawLayout


def test_is_qid_fallback_detects_qid_pattern():
    assert _is_qid_fallback("Q12345") is True
    assert _is_qid_fallback("Q1") is True
    assert _is_qid_fallback("Quebec") is False      # letters after the Q
    assert _is_qid_fallback("Q") is False           # bare Q, no digits
    assert _is_qid_fallback("") is False
    assert _is_qid_fallback("12345") is False       # no Q prefix


def _write_fake_dump(raw_dir: Path, pid: str, bindings: list[dict]) -> None:
    target_dir = raw_dir / "knowledge" / "wikidata"
    target_dir.mkdir(parents=True, exist_ok=True)
    (target_dir / f"{pid}.json").write_text(
        json.dumps(
            {
                "pid": pid,
                "relation": "capital",  # override below via PROPERTIES lookup
                "category": "geography",
                "description": "test",
                "query": "SELECT ... LIMIT 100",
                "limit": 100,
                "label_max": 25,
                "downloaded_at": "2026-04-11T00:00:00+00:00",
                "bindings": bindings,
            }
        )
    )


def test_extractor_empty_raw_dir_yields_nothing(tmp_path: Path):
    e = WikidataExtractor()
    assert list(e.extract({"raw_dir": str(tmp_path)})) == []


def test_extractor_capital_relation_from_synthetic_dump(tmp_path: Path):
    # P36 is "capital" in PROPERTIES
    p36 = next(p for p in PROPERTIES if p.pid == "P36")
    assert p36.relation == "capital"

    bindings = [
        {"itemLabel": {"value": "France"}, "valueLabel": {"value": "Paris"}},
        {"itemLabel": {"value": "Germany"}, "valueLabel": {"value": "Berlin"}},
        # Q-id fallback — dropped
        {"itemLabel": {"value": "Q12345"}, "valueLabel": {"value": "London"}},
        # self-loop — dropped
        {"itemLabel": {"value": "Same"}, "valueLabel": {"value": "Same"}},
        # empty label — dropped
        {"itemLabel": {"value": ""}, "valueLabel": {"value": "Rome"}},
    ]
    _write_fake_dump(tmp_path, "P36", bindings)

    e = WikidataExtractor()
    triples = list(e.extract({"raw_dir": str(tmp_path)}))
    # Only the first two survive
    assert len(triples) == 2
    objects_by_subject = {t.subject: t.object for t in triples}
    assert objects_by_subject == {"France": "Paris", "Germany": "Berlin"}
    for t in triples:
        assert t.relation == "capital"
        assert t.provenance == "wikidata:P36"


def test_extractor_dedupes_within_a_dump(tmp_path: Path):
    bindings = [
        {"itemLabel": {"value": "France"}, "valueLabel": {"value": "Paris"}},
        {"itemLabel": {"value": "France"}, "valueLabel": {"value": "Paris"}},
    ]
    _write_fake_dump(tmp_path, "P36", bindings)
    e = WikidataExtractor()
    triples = list(e.extract({"raw_dir": str(tmp_path)}))
    assert len(triples) == 1


def test_raw_layout_verify_false_when_no_files(tmp_path: Path):
    layout = WikidataRawLayout(raw_dir=tmp_path)
    assert layout.verify() is False
