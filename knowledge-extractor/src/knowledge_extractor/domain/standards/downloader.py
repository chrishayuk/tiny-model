"""Standards has no external source — downloader is a no-op."""

from __future__ import annotations

from pathlib import Path

from ...base import BaseDownloader, DatasetMeta
from .model import META, StandardsRawLayout


class StandardsDownloader(BaseDownloader):
    def meta(self) -> DatasetMeta:
        return META

    def layout(self, raw_dir: Path) -> StandardsRawLayout:
        return StandardsRawLayout(raw_dir=self.raw_path(raw_dir))

    def download(self, raw_dir: Path) -> None:
        # Nothing to download — the authoritative tables live in model.py.
        self.raw_path(raw_dir)
