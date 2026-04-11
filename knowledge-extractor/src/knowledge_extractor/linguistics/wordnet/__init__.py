"""WordNet dataset — lexical database of English synsets and relations."""

from .downloader import WordNetDownloader
from .extractor import WordNetExtractor
from .model import WordNetRawLayout

__all__ = ["WordNetDownloader", "WordNetExtractor", "WordNetRawLayout"]
