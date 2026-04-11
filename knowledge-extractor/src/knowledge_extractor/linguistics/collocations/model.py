"""Shared contract between the collocations downloader and extractor.

The Brown corpus is the only dependency — collocations are derived at
extract time using NLTK's ``BigramCollocationFinder`` and a POS-tagged
bigram pass for adjective-noun and verb-object pairs.
"""

from __future__ import annotations

from typing import ClassVar

from ...base import DatasetMeta, NLTKRawLayout


META = DatasetMeta(
    name="collocations",
    category="linguistics",
    version="brown-1.0",
    license="CC (Brown corpus)",
    url="https://en.wikipedia.org/wiki/Brown_Corpus",
    layer_band="syntax",
    description="Brown-corpus collocations: bigram PMI, adjective-noun, verb-object",
)


class CollocationsRawLayout(NLTKRawLayout):
    NLTK_PACKAGES: ClassVar[list[tuple[str, str]]] = [
        ("brown",            "corpora/brown"),
        ("universal_tagset", "taggers/universal_tagset"),
    ]
