"""Collocations dataset — statistically significant word pairings from Brown."""

from .downloader import CollocationsDownloader
from .extractor import CollocationsExtractor
from .model import CollocationsRawLayout

__all__ = ["CollocationsDownloader", "CollocationsExtractor", "CollocationsRawLayout"]
