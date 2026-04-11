"""Fetches the VerbNet corpus via NLTK."""

from __future__ import annotations

from typing import ClassVar

from ...base import DatasetMeta, NLTKBackedDownloader, NLTKRawLayout
from .model import META, VerbNetRawLayout


class VerbNetDownloader(NLTKBackedDownloader):
    NLTK_PACKAGES: ClassVar[list[tuple[str, str]]] = VerbNetRawLayout.NLTK_PACKAGES
    LAYOUT_CLASS: ClassVar[type[NLTKRawLayout]] = VerbNetRawLayout

    def meta(self) -> DatasetMeta:
        return META
