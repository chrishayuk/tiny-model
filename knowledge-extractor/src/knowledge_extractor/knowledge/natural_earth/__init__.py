"""Natural Earth dataset — sovereignty chains + admin-1 subdivisions."""

from .downloader import NaturalEarthDownloader
from .extractor import NaturalEarthExtractor
from .model import NaturalEarthRawLayout

__all__ = ["NaturalEarthDownloader", "NaturalEarthExtractor", "NaturalEarthRawLayout"]
