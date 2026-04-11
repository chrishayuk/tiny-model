"""Shared contract between the Wikidata downloader and extractor.

The downloader fetches one JSON file per curated SPARQL property into
``<raw_dir>/knowledge/wikidata/<pid>.json``. Each file is a small envelope
around the untouched ``bindings`` list from the SPARQL endpoint, so
re-filtering is a pure-extract operation and never requires re-querying.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from ...base import DatasetMeta, RawLayout


META = DatasetMeta(
    name="wikidata",
    category="knowledge",
    version="sparql-2026-04",
    license="CC0 (Wikidata)",
    url="https://www.wikidata.org/",
    layer_band="knowledge",
    description="Factual triples from a curated set of Wikidata SPARQL properties",
)


SPARQL_ENDPOINT = "https://query.wikidata.org/sparql"
USER_AGENT = "knowledge-extractor-downloader/0.3 (https://github.com/chrishayuk/larql)"


class WikidataProperty(BaseModel):
    """A single SPARQL property in the curated registry."""

    model_config = ConfigDict(extra="forbid")

    pid: str
    category: str
    relation: str
    description: str


PROPERTIES: list[WikidataProperty] = [
    # Geography
    WikidataProperty(pid="P36",   category="geography",     relation="capital",            description="Capital city of a country or territory"),
    WikidataProperty(pid="P17",   category="geography",     relation="country",            description="Sovereign state of an entity"),
    WikidataProperty(pid="P30",   category="geography",     relation="continent",          description="Continent an entity is in"),
    WikidataProperty(pid="P47",   category="geography",     relation="shares_border",      description="Entities sharing a land border"),
    WikidataProperty(pid="P131",  category="geography",     relation="located_in",         description="Administrative territorial entity"),
    WikidataProperty(pid="P1376", category="geography",     relation="capital_of",         description="Entity of which this is the capital"),
    WikidataProperty(pid="P150",  category="geography",     relation="contains",           description="Contains administrative territorial entity"),
    # People
    WikidataProperty(pid="P106",  category="people",        relation="occupation",         description="Occupation of a person"),
    WikidataProperty(pid="P27",   category="people",        relation="citizenship",        description="Country of citizenship"),
    WikidataProperty(pid="P19",   category="people",        relation="birthplace",         description="Place of birth"),
    WikidataProperty(pid="P20",   category="people",        relation="deathplace",         description="Place of death"),
    WikidataProperty(pid="P22",   category="people",        relation="father",             description="Father of a person"),
    WikidataProperty(pid="P25",   category="people",        relation="mother",             description="Mother of a person"),
    WikidataProperty(pid="P26",   category="people",        relation="spouse",             description="Spouse of a person"),
    WikidataProperty(pid="P40",   category="people",        relation="child",              description="Child of a person"),
    WikidataProperty(pid="P69",   category="people",        relation="educated_at",        description="Educational institution attended"),
    # Culture
    WikidataProperty(pid="P175",  category="culture",       relation="performer",          description="Performer of a work"),
    WikidataProperty(pid="P86",   category="culture",       relation="composer",           description="Composer of a work"),
    WikidataProperty(pid="P57",   category="culture",       relation="director",           description="Director of a film or play"),
    WikidataProperty(pid="P161",  category="culture",       relation="cast_member",        description="Cast member in a film or show"),
    WikidataProperty(pid="P170",  category="culture",       relation="creator",            description="Creator of a work"),
    WikidataProperty(pid="P50",   category="culture",       relation="author",             description="Author of a written work"),
    WikidataProperty(pid="P136",  category="culture",       relation="genre",              description="Genre of a work"),
    WikidataProperty(pid="P264",  category="culture",       relation="record_label",       description="Record label of a musical work"),
    # Organisations
    WikidataProperty(pid="P112",  category="organisations", relation="founded_by",         description="Founder of an organisation"),
    WikidataProperty(pid="P159",  category="organisations", relation="headquarters",       description="Headquarters location"),
    WikidataProperty(pid="P452",  category="organisations", relation="industry",           description="Industry of an organisation"),
    WikidataProperty(pid="P169",  category="organisations", relation="ceo",                description="Chief executive officer"),
    WikidataProperty(pid="P127",  category="organisations", relation="owned_by",           description="Owner of an entity"),
    WikidataProperty(pid="P749",  category="organisations", relation="parent_org",         description="Parent organisation"),
    # Science
    WikidataProperty(pid="P31",   category="science",       relation="instance_of",        description="Class this entity is an instance of"),
    WikidataProperty(pid="P279",  category="science",       relation="subclass_of",        description="Superclass of this class"),
    WikidataProperty(pid="P361",  category="science",       relation="part_of",            description="Larger thing this entity is a part of"),
    WikidataProperty(pid="P527",  category="science",       relation="has_part",           description="Components of this entity"),
    # Politics
    WikidataProperty(pid="P6",    category="politics",      relation="head_of_government", description="Head of government"),
    WikidataProperty(pid="P35",   category="politics",      relation="head_of_state",      description="Head of state"),
    WikidataProperty(pid="P194",  category="politics",      relation="legislative_body",   description="Legislative body of a state"),
    WikidataProperty(pid="P37",   category="politics",      relation="official_language",  description="Official language of an entity"),
    WikidataProperty(pid="P38",   category="politics",      relation="currency",           description="Currency used"),
    WikidataProperty(pid="P122",  category="politics",      relation="basic_form_of_govt", description="Form of government"),
    # Sport
    WikidataProperty(pid="P54",   category="sport",         relation="member_of_team",     description="Sports team a person plays for"),
    WikidataProperty(pid="P118",  category="sport",         relation="league",             description="League a team plays in"),
    WikidataProperty(pid="P1532", category="sport",         relation="country_for_sport",  description="Country represented in sport"),
    WikidataProperty(pid="P641",  category="sport",         relation="sport",              description="Sport this entity is associated with"),
]


class WikidataPropertyDump(BaseModel):
    """Envelope for one property's raw SPARQL response on disk."""

    model_config = ConfigDict(extra="forbid")

    pid: str
    relation: str
    category: str
    description: str
    query: str
    limit: int
    label_max: int
    downloaded_at: str
    bindings: list[dict[str, Any]] = Field(default_factory=list)


class WikidataRawLayout(RawLayout):
    """Raw layout for Wikidata.

    Each curated property is stored as ``<raw_dir>/<pid>.json`` — presence
    of the file is the download marker. ``verify()`` returns True when
    every property in :data:`PROPERTIES` has a file.
    """

    def property_path(self, pid: str) -> Path:
        return self.raw_dir / f"{pid}.json"

    def verify(self) -> bool:
        if not self.raw_dir.exists():
            return False
        return all(self.property_path(p.pid).exists() for p in PROPERTIES)
