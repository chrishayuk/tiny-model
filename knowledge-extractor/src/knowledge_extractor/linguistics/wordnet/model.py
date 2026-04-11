"""Shared contract between the WordNet downloader and extractor."""

from __future__ import annotations

from typing import ClassVar

from ...base import DatasetMeta, NLTKRawLayout


META = DatasetMeta(
    name="wordnet",
    category="linguistics",
    version="3.0",
    license="Princeton WordNet License",
    url="https://wordnet.princeton.edu/",
    layer_band="syntax",
    description="Lexical database of English synsets and relations",
)


class WordNetRawLayout(NLTKRawLayout):
    NLTK_PACKAGES: ClassVar[list[tuple[str, str]]] = [
        ("wordnet", "corpora/wordnet"),
        ("omw-1.4", "corpora/omw-1.4"),
    ]
