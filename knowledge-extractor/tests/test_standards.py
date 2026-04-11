"""End-to-end test for the hand-curated standards dataset.

Runs the full pipeline (download no-op + extract + normaliser + filter +
writer) against the real StandardsExtractor. No network, no NLTK, no
external files — the whole dataset is embedded in model.py.
"""

from __future__ import annotations

import json
from pathlib import Path

from knowledge_extractor.domain.standards import (
    StandardsDownloader,
    StandardsExtractor,
)
from knowledge_extractor.domain.standards.model import TABLES
from knowledge_extractor.runner import PipelineRunner


def test_standards_downloader_is_noop(tmp_path: Path):
    d = StandardsDownloader()
    layout = d.layout(tmp_path)
    assert layout.verify() is True  # standards never needs a download
    d.download(tmp_path)  # should not raise
    assert d.is_downloaded(tmp_path) is True


def test_standards_extractor_emits_all_relations():
    e = StandardsExtractor()
    triples = list(e.extract({}))
    emitted_relations = {t.relation for t in triples}
    expected_relations = {name for name, _ in TABLES}
    assert emitted_relations == expected_relations


def test_standards_triple_count_matches_tables():
    """Every row in every table should yield exactly one triple."""
    e = StandardsExtractor()
    triples = list(e.extract({}))
    total_rows = sum(len(table) for _, table in TABLES)
    assert len(triples) == total_rows


def test_standards_pipeline_end_to_end(tmp_path: Path):
    """Full PipelineRunner round trip: extract → normalise → filter →
    write → manifest."""
    output_dir = tmp_path / "extracted"
    raw_dir = tmp_path / "raw"
    runner = PipelineRunner(
        {"output_dir": str(output_dir), "raw_dir": str(raw_dir)}
    )
    manifest = runner.run_dataset(StandardsExtractor())
    assert manifest["dataset"] == "standards"
    assert manifest["category"] == "domain"
    assert manifest["total_pairs"] > 100  # 127 today; don't pin exact
    assert len(manifest["relations"]) == len(TABLES)

    # Every relation file should exist with a valid triple-file schema
    for rel_name, _ in TABLES:
        f = output_dir / "domain" / "standards" / f"{rel_name}.json"
        assert f.exists()
        payload = json.loads(f.read_text())
        assert payload["relation"] == rel_name
        assert payload["source"] == "standards"
        assert payload["pair_count"] == len(payload["pairs"])
        for pair in payload["pairs"]:
            assert len(pair) == 2
