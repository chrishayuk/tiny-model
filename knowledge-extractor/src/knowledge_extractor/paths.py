"""Canonical dataset path resolution and NLTK redirection.

The project splits datasets into two trees, both outside the code repo:

* ``<repo>/datasets/raw/``        — everything downloaded, untouched
* ``<repo>/datasets/extracted/``  — transformed JSON triples (the output)

Paths default to those names relative to the current working directory, so
users run the CLI from the monorepo root. They can be overridden per-call
(``--raw-dir``, ``--output``) or via env vars (``KNOWLEDGE_RAW_DIR``,
``KNOWLEDGE_EXTRACTED_DIR``).

NLTK is also redirected here so every download lands inside ``raw/nltk/``
instead of ``~/nltk_data``. This is the single-source-of-truth rule: if it
was downloaded for this project, it lives under ``datasets/raw/``.
"""

from __future__ import annotations

import os
from pathlib import Path


DEFAULT_RAW_DIR = "datasets/raw"
DEFAULT_EXTRACTED_DIR = "datasets/extracted"


def default_raw_dir() -> Path:
    return Path(os.environ.get("KNOWLEDGE_RAW_DIR", DEFAULT_RAW_DIR))


def default_extracted_dir() -> Path:
    return Path(os.environ.get("KNOWLEDGE_EXTRACTED_DIR", DEFAULT_EXTRACTED_DIR))


def raw_path_for(raw_dir: Path | str, category: str, name: str) -> Path:
    """Standard per-dataset raw cache: ``<raw>/<category>/<name>/``."""
    return Path(raw_dir) / category / name


def setup_nltk_data_dir(raw_dir: Path | str) -> Path:
    """Point NLTK at ``<raw>/nltk/`` for both lookup and downloads.

    Safe to call repeatedly. Returns the resolved NLTK data directory.
    Importing nltk itself is deferred until this function runs so that
    projects without NLTK installed don't pay the import cost.
    """
    nltk_dir = Path(raw_dir) / "nltk"
    nltk_dir.mkdir(parents=True, exist_ok=True)

    try:
        import nltk  # type: ignore
    except ImportError:
        return nltk_dir

    nltk_dir_str = str(nltk_dir)
    if nltk_dir_str not in nltk.data.path:
        nltk.data.path.insert(0, nltk_dir_str)
    os.environ["NLTK_DATA"] = nltk_dir_str
    return nltk_dir
