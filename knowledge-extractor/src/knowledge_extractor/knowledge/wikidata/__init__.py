"""Wikidata dataset — SPARQL-extracted factual triples."""

from .downloader import WikidataDownloader
from .extractor import WikidataExtractor
from .model import WikidataRawLayout

__all__ = ["WikidataDownloader", "WikidataExtractor", "WikidataRawLayout"]
