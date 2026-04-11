"""Shared contract between the FrameNet downloader and extractor."""

from __future__ import annotations

from typing import ClassVar

from ...base import DatasetMeta, NLTKRawLayout


META = DatasetMeta(
    name="framenet",
    category="linguistics",
    version="1.7",
    license="FrameNet Data Release License",
    url="https://framenet.icsi.berkeley.edu/",
    layer_band="syntax",
    description="Berkeley FrameNet frames, relations, elements, and lexicon",
)


class FrameNetRawLayout(NLTKRawLayout):
    NLTK_PACKAGES: ClassVar[list[tuple[str, str]]] = [
        ("framenet_v17", "corpora/framenet_v17"),
    ]
