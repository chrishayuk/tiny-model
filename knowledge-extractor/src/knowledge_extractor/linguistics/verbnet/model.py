"""Shared contract between the VerbNet downloader and extractor."""

from __future__ import annotations

from typing import ClassVar

from ...base import DatasetMeta, NLTKRawLayout


META = DatasetMeta(
    name="verbnet",
    category="linguistics",
    version="3.3",
    license="VerbNet License",
    url="https://verbs.colorado.edu/verbnet/",
    layer_band="syntax",
    description="Verb classes with thematic roles and syntactic frames",
)


class VerbNetRawLayout(NLTKRawLayout):
    NLTK_PACKAGES: ClassVar[list[tuple[str, str]]] = [
        ("verbnet", "corpora/verbnet"),
    ]
