"""Registry integrity — every registered dataset must load its downloader
and extractor classes, and every tier entry must be a known dataset."""

from __future__ import annotations

import pytest

from knowledge_extractor.base import BaseDownloader, BaseExtractor
from knowledge_extractor.registry import (
    DATASETS,
    TIERS,
    load_downloader_class,
    load_extractor_class,
    try_meta,
)


@pytest.mark.parametrize("key", sorted(DATASETS))
def test_every_dataset_loads(key: str):
    D = load_downloader_class(key)
    E = load_extractor_class(key)
    assert issubclass(D, BaseDownloader), f"{key}: {D} is not BaseDownloader"
    assert issubclass(E, BaseExtractor), f"{key}: {E} is not BaseExtractor"


@pytest.mark.parametrize("key", sorted(DATASETS))
def test_every_dataset_meta(key: str):
    m = try_meta(key)
    assert m is not None, f"{key} failed to produce DatasetMeta"
    # The registry key format is "<category>/<name>"
    category, _, name = key.partition("/")
    assert m.category == category
    # ast/treesitter → meta.name is "treesitter"; knowledge/osm-gb → "osm-gb"
    assert m.name == name


def test_every_tier_entry_is_a_known_dataset():
    for tier, keys in TIERS.items():
        for k in keys:
            assert k in DATASETS, f"tier {tier}: {k!r} not in DATASETS"


def test_tier_1_contents():
    """Pin the tier 1 line-up so accidental drops are caught."""
    expected = {
        "linguistics/wordnet",
        "linguistics/morphology",
        "linguistics/framenet",
        "linguistics/verbnet",
        "linguistics/collocations",
        "ast/treesitter",
        "knowledge/wikidata",
        "knowledge/countries",
        "domain/standards",
    }
    assert set(TIERS[1]) == expected


def test_tier_2_contents():
    """Spatial-cluster progress: osm-gb was first, natural-earth is second."""
    assert "knowledge/osm-gb" in TIERS[2]
    assert "knowledge/natural-earth" in TIERS[2]


def test_unknown_key_raises():
    with pytest.raises(KeyError):
        load_downloader_class("nope/nothing")
    with pytest.raises(KeyError):
        load_extractor_class("nope/nothing")
