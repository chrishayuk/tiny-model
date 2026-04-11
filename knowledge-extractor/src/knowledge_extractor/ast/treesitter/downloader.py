"""Fetches tree-sitter grammar files from GitHub raw.

One ``grammar.json`` + ``node-types.json`` per language into
``<raw_dir>/ast/treesitter/<lang>/``. Tries ``master`` then ``main`` as
the branch name. Skips files that are already present — presence is the
only state we track.
"""

from __future__ import annotations

from pathlib import Path

import requests

from ...base import BaseDownloader, DatasetMeta
from ...io_utils import atomic_write_bytes
from .model import (
    BRANCHES,
    META,
    RAW_URL,
    TreeSitterLanguage,
    TreeSitterRawLayout,
    languages_for_tier,
)


REQUEST_TIMEOUT = 30
USER_AGENT = "knowledge-extractor-ast/0.3"


def _fetch_file(
    session: requests.Session,
    lang: TreeSitterLanguage,
    filename: str,
    target: Path,
) -> bool:
    if target.exists():
        return True
    path = f"{lang.src.rstrip('/')}/{filename}"
    for branch in BRANCHES:
        url = RAW_URL.format(owner=lang.owner, repo=lang.repo, branch=branch, path=path)
        try:
            r = session.get(url, timeout=REQUEST_TIMEOUT)
        except Exception:
            continue
        if r.status_code == 200:
            atomic_write_bytes(target, r.content)
            return True
    return False


class TreeSitterDownloader(BaseDownloader):
    def meta(self) -> DatasetMeta:
        return META

    def layout(self, raw_dir: Path) -> TreeSitterRawLayout:
        return TreeSitterRawLayout(raw_dir=self.raw_path(raw_dir))

    def download(self, raw_dir: Path, *, max_tier: int | None = None) -> None:
        layout = self.layout(raw_dir)
        session = requests.Session()
        session.headers.update({"User-Agent": USER_AGENT})

        for lang in languages_for_tier(max_tier):
            grammar_ok = _fetch_file(
                session, lang, "grammar.json", layout.grammar_path(lang.name)
            )
            node_ok = _fetch_file(
                session, lang, "node-types.json", layout.node_types_path(lang.name)
            )
            if not (grammar_ok or node_ok):
                print(f"[treesitter] {lang.name}: could not fetch grammar files")
