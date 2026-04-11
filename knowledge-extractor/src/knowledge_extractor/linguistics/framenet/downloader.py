"""Fetches the FrameNet 1.7 corpus via NLTK."""

from __future__ import annotations

from typing import ClassVar

from ...base import DatasetMeta, NLTKBackedDownloader, NLTKRawLayout
from .model import META, FrameNetRawLayout


class FrameNetDownloader(NLTKBackedDownloader):
    NLTK_PACKAGES: ClassVar[list[tuple[str, str]]] = FrameNetRawLayout.NLTK_PACKAGES
    LAYOUT_CLASS: ClassVar[type[NLTKRawLayout]] = FrameNetRawLayout

    def meta(self) -> DatasetMeta:
        return META
