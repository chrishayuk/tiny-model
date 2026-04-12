"""End-to-end + data integrity checks for knowledge/countries.

The dataset is hand-curated so the tests are mostly shape / integrity
assertions plus a few spot-checks on specific countries to catch typos
in the data table.
"""

from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path

import pytest

from knowledge_extractor.knowledge.countries import (
    CountriesDownloader,
    CountriesExtractor,
)
from knowledge_extractor.knowledge.countries._data import COUNTRIES
from knowledge_extractor.knowledge.countries.model import SCALAR_RELATIONS
from knowledge_extractor.runner import PipelineRunner


# ---------- data integrity --------------------------------------------


def test_no_duplicate_names():
    names = [c["name"] for c in COUNTRIES]
    dups = [n for n, count in Counter(names).items() if count > 1]
    assert dups == []


def test_no_duplicate_alpha2_codes():
    codes = [c["alpha2"] for c in COUNTRIES]
    dups = [c for c, count in Counter(codes).items() if count > 1]
    assert dups == []


def test_no_duplicate_alpha3_codes():
    codes = [c["alpha3"] for c in COUNTRIES]
    dups = [c for c, count in Counter(codes).items() if count > 1]
    assert dups == []


@pytest.mark.parametrize("country", COUNTRIES, ids=lambda c: c["alpha2"])
def test_country_has_required_fields(country):
    for key, _relation in SCALAR_RELATIONS:
        assert country.get(key), f"{country['name']} missing {key}"
    assert country.get("languages"), f"{country['name']} missing languages"
    assert isinstance(country["languages"], list)
    assert all(isinstance(lang, str) and lang for lang in country["languages"])
    assert "un_member" in country


@pytest.mark.parametrize("country", COUNTRIES, ids=lambda c: c["alpha2"])
def test_iso_code_shapes(country):
    assert re.fullmatch(r"[A-Z]{2}", country["alpha2"])
    assert re.fullmatch(r"[A-Z]{3}", country["alpha3"])
    assert re.fullmatch(r"[0-9]{3}", country["numeric"])
    assert country["calling_code"].startswith("+")
    assert country["tld"].startswith(".")


def test_reasonable_coverage():
    """v1 target: at least 60 countries spanning every continent."""
    assert len(COUNTRIES) >= 60
    continents = {c["continent"] for c in COUNTRIES}
    assert {"Africa", "Asia", "Europe", "North America", "Oceania", "South America"} <= continents


def test_g20_coverage():
    """Every G20 country must be present — that's the probe baseline."""
    g20 = {
        "United States", "United Kingdom", "China", "Japan", "Germany",
        "France", "Italy", "Canada", "Russia", "Brazil", "India", "Mexico",
        "Australia", "South Korea", "Indonesia", "Saudi Arabia", "Turkey",
        "South Africa", "Argentina",
    }
    names = {c["name"] for c in COUNTRIES}
    missing = g20 - names
    assert missing == set(), f"missing G20 members: {missing}"


# ---------- downloader -------------------------------------------------


def test_downloader_is_noop(tmp_path: Path):
    d = CountriesDownloader()
    layout = d.layout(tmp_path)
    assert layout.verify() is True  # always ready
    d.download(tmp_path)  # should not raise
    assert d.is_downloaded(tmp_path) is True


# ---------- extractor --------------------------------------------------


def test_extractor_spot_check_united_kingdom():
    """Pin a single country's full triple set so a data edit that breaks
    this pops up immediately."""
    e = CountriesExtractor()
    triples = [t for t in e.extract({}) if t.subject == "United Kingdom"]
    by_relation = {t.relation: t.object for t in triples}
    assert by_relation["iso_alpha2"] == "GB"
    assert by_relation["iso_alpha3"] == "GBR"
    assert by_relation["iso_numeric"] == "826"
    assert by_relation["capital"] == "London"
    assert by_relation["continent"] == "Europe"
    assert by_relation["currency"] == "GBP"
    assert by_relation["tld"] == ".uk"
    assert by_relation["calling_code"] == "+44"
    assert by_relation["un_member"] == "yes"
    # Every UK triple should share the same provenance
    provs = {t.provenance for t in triples}
    assert provs == {"iso3166:GBR"}


def test_extractor_spot_check_multi_language():
    """Switzerland has 4 official languages — one triple per language."""
    e = CountriesExtractor()
    languages = {
        t.object
        for t in e.extract({})
        if t.subject == "Switzerland" and t.relation == "official_language"
    }
    assert languages == {"German", "French", "Italian", "Romansh"}


def test_extractor_un_member_only_when_true():
    """Taiwan and Vatican City are not UN members; no un_member triple."""
    e = CountriesExtractor()
    un_triples = {t.subject for t in e.extract({}) if t.relation == "un_member"}
    assert "Taiwan" not in un_triples
    assert "Vatican City" not in un_triples
    assert "United Kingdom" in un_triples


def test_extractor_relation_set():
    e = CountriesExtractor()
    relations = {t.relation for t in e.extract({})}
    expected = {rel for _, rel in SCALAR_RELATIONS}
    expected |= {"official_language", "un_member"}
    assert relations == expected


def test_extractor_triple_count_minimum():
    """At least 60 countries × ~11 scalar + 1 lang + maybe 1 UN ≈ 780+."""
    e = CountriesExtractor()
    triples = list(e.extract({}))
    assert len(triples) >= 700


# ---------- end-to-end pipeline ---------------------------------------


def test_countries_pipeline_end_to_end(tmp_path: Path):
    output_dir = tmp_path / "extracted"
    raw_dir = tmp_path / "raw"
    runner = PipelineRunner(
        {"output_dir": str(output_dir), "raw_dir": str(raw_dir)}
    )
    manifest = runner.run_dataset(CountriesExtractor())
    assert manifest["dataset"] == "countries"
    assert manifest["category"] == "knowledge"
    assert manifest["total_pairs"] >= 700

    # Spot-check the capital relation file
    capital_file = output_dir / "knowledge" / "countries" / "capital.json"
    assert capital_file.exists()
    payload = json.loads(capital_file.read_text())
    pair_dict = dict(payload["pairs"])
    # Normaliser lowercases syntax-band content, but this is layer_band=knowledge
    # so the permissive profile keeps proper nouns intact
    assert "United Kingdom" in pair_dict or "united kingdom" in pair_dict
