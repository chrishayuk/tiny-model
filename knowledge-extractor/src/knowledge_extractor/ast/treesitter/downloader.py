"""Fetches tree-sitter grammar files from GitHub raw.

One ``grammar.json`` + ``node-types.json`` per language into
``<raw_dir>/ast/treesitter/<lang>/``. Tries ``master`` then ``main`` as
the branch name. Skips files that are already present — presence is the
only state we track.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

import requests

from ...base import BaseDownloader, DatasetMeta
from .model import (
    BRANCHES,
    GRAMMAR_FILES,
    META,
    RAW_URL,
    TreeSitterLanguage,
    TreeSitterRawLayout,
    languages_for_tier,
)


REQUEST_TIMEOUT = 30
USER_AGENT = "larql-ast-downloader/0.3"


def _atomic_write_bytes(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(
        prefix=path.name + ".", suffix=".tmp", dir=str(path.parent)
    )
    try:
        with os.fdopen(fd, "wb") as fh:
            fh.write(data)
        os.replace(tmp_name, path)
    except Exception:
        if os.path.exists(tmp_name):
            os.unlink(tmp_name)
        raise


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
            _atomic_write_bytes(target, r.content)
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
