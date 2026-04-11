"""Shared contract between the morphology downloader and extractor."""

from __future__ import annotations

from typing import ClassVar

from ...base import DatasetMeta, NLTKRawLayout


META = DatasetMeta(
    name="morphology",
    category="linguistics",
    version="1.0",
    license="MIT (lemminflect) + CC (Brown)",
    url="https://github.com/bjascob/LemmInflect",
    layer_band="syntax",
    description="Inflectional morphology pairs (plural, past, comparative, ...)",
)


class MorphologyRawLayout(NLTKRawLayout):
    NLTK_PACKAGES: ClassVar[list[tuple[str, str]]] = [
        ("brown",            "corpora/brown"),
        ("universal_tagset", "taggers/universal_tagset"),
        ("wordnet",          "corpora/wordnet"),
        ("omw-1.4",          "corpora/omw-1.4"),
    ]
