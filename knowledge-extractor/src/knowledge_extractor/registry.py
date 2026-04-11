"""Central dataset registry and tier definitions.

Each dataset has two components — a downloader and an extractor — registered
as ``"module.path:ClassName"`` strings and imported lazily. A partial install
(e.g. NLTK present but tree-sitter missing) can still `list` everything;
import errors surface only when a specific extractor is loaded.
"""

from __future__ import annotations

import importlib
from typing import Type, TypedDict

from .base import BaseDownloader, BaseExtractor


class DatasetSpec(TypedDict):
    downloader: str   # "module.path:ClassName"
    extractor: str    # "module.path:ClassName"


def _pair(pkg: str, base: str) -> DatasetSpec:
    """Build a spec for a dataset whose downloader and extractor live in
    ``knowledge_extractor.<pkg>.{downloader,extractor}`` with class names
    ``{base}Downloader`` and ``{base}Extractor``."""
    return {
        "downloader": f"knowledge_extractor.{pkg}.downloader:{base}Downloader",
        "extractor":  f"knowledge_extractor.{pkg}.extractor:{base}Extractor",
    }


DATASETS: dict[str, DatasetSpec] = {
    "linguistics/wordnet":      _pair("linguistics.wordnet", "WordNet"),
    "linguistics/morphology":   _pair("linguistics.morphology", "Morphology"),
    "linguistics/framenet":     _pair("linguistics.framenet", "FrameNet"),
    "linguistics/verbnet":      _pair("linguistics.verbnet", "VerbNet"),
    "linguistics/collocations": _pair("linguistics.collocations", "Collocations"),
    "knowledge/wikidata":       _pair("knowledge.wikidata", "Wikidata"),
    "ast/treesitter":            _pair("ast.treesitter", "TreeSitter"),
    "domain/standards":         _pair("domain.standards", "Standards"),
}


TIERS: dict[int, list[str]] = {
    1: [
        "linguistics/wordnet",
        "linguistics/morphology",
        "linguistics/framenet",
        "linguistics/verbnet",
        "linguistics/collocations",
        "ast/treesitter",
        "knowledge/wikidata",
        "domain/standards",
    ],
    2: [],
    3: [],
}


class ExtractorImportError(RuntimeError):
    """Raised when a dataset component's module or deps cannot be imported."""


def _load(spec: str) -> type:
    module_path, _, class_name = spec.partition(":")
    try:
        module = importlib.import_module(module_path)
    except ImportError as e:
        raise ExtractorImportError(
            f"cannot import {module_path}: {e}. "
            f"install optional deps or check pyproject.toml."
        ) from e
    try:
        return getattr(module, class_name)
    except AttributeError as e:
        raise ExtractorImportError(f"{module_path} has no class {class_name}") from e


def _get_spec(key: str) -> DatasetSpec:
    spec = DATASETS.get(key)
    if spec is None:
        known = ", ".join(sorted(DATASETS)) or "(none)"
        raise KeyError(f"unknown dataset: {key}. known: {known}")
    return spec


def load_extractor_class(key: str) -> Type[BaseExtractor]:
    return _load(_get_spec(key)["extractor"])


def load_downloader_class(key: str) -> Type[BaseDownloader]:
    return _load(_get_spec(key)["downloader"])


def instantiate_extractors(keys: list[str]) -> list[BaseExtractor]:
    return [load_extractor_class(k)() for k in keys]


def instantiate_downloaders(keys: list[str]) -> list[BaseDownloader]:
    return [load_downloader_class(k)() for k in keys]


def try_meta(key: str):
    """Return metadata for `key` or None if it can't be imported.

    Tries the extractor first (that's what users actually run); falls back to
    the downloader if the extractor can't import.
    """
    for loader in (load_extractor_class, load_downloader_class):
        try:
            return loader(key)().meta()
        except Exception:
            continue
    return None


def keys_for_category(category: str) -> list[str]:
    return [k for k in DATASETS if k.split("/", 1)[0] == category]
