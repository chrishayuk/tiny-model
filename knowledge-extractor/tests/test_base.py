"""Contracts in base.py: pydantic models + abstract classes."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from knowledge_extractor.base import (
    BaseDownloader,
    BaseExtractor,
    DatasetMeta,
    NLTKBackedDownloader,
    NLTKRawLayout,
    RawLayout,
    RawTriple,
)


# ---------- RawTriple --------------------------------------------------


def test_raw_triple_requires_keyword_args():
    t = RawTriple(subject="a", relation="r", object="b")
    assert t.subject == "a"
    assert t.confidence == 1.0
    assert t.layer_band == "knowledge"


def test_raw_triple_rejects_extras():
    with pytest.raises(ValidationError):
        RawTriple(subject="a", relation="r", object="b", bogus="x")  # type: ignore[call-arg]


def test_raw_triple_rejects_positional_args():
    with pytest.raises(TypeError):
        RawTriple("a", "r", "b")  # type: ignore[call-arg,misc]


# ---------- DatasetMeta ------------------------------------------------


def test_dataset_meta_defaults():
    m = DatasetMeta(name="x", category="y")
    assert m.layer_band == "knowledge"
    assert m.description == ""


# ---------- RawLayout --------------------------------------------------


def test_raw_layout_default_verify(tmp_path: Path):
    layout = RawLayout(raw_dir=tmp_path)
    assert layout.verify() is True
    layout_missing = RawLayout(raw_dir=tmp_path / "does-not-exist")
    assert layout_missing.verify() is False


class _FakeLayout(NLTKRawLayout):
    NLTK_PACKAGES = [("bogus", "corpora/bogus")]


def test_nltk_raw_layout_verify_missing(tmp_path: Path):
    layout = _FakeLayout(raw_dir=tmp_path, nltk_data_dir=tmp_path / "nltk")
    # No nltk data present: verify should be False, not raise
    assert layout.verify() is False


# ---------- BaseDownloader / BaseExtractor abstract ---------------------


def test_base_downloader_is_abstract():
    with pytest.raises(TypeError):
        BaseDownloader()  # type: ignore[abstract]


def test_base_extractor_is_abstract():
    with pytest.raises(TypeError):
        BaseExtractor()  # type: ignore[abstract]


class _DirCreatingDownloader(BaseDownloader):
    def meta(self) -> DatasetMeta:
        return DatasetMeta(name="noop", category="test")

    def download(self, raw_dir: Path) -> None:
        self.raw_path(raw_dir).mkdir(parents=True, exist_ok=True)


def test_raw_path_is_pure(tmp_path: Path):
    """raw_path() returns a path but must not create the directory — the
    is_downloaded() default check depends on existence meaning downloaded."""
    d = _DirCreatingDownloader()
    p = d.raw_path(tmp_path)
    assert p == tmp_path / "test" / "noop"
    assert not p.exists()


def test_base_downloader_is_downloaded_default(tmp_path: Path):
    """Default layout() returns a bare RawLayout; is_downloaded() delegates
    to RawLayout.verify(), which is true iff the dataset dir exists."""
    d = _DirCreatingDownloader()
    assert d.is_downloaded(tmp_path) is False
    d.download(tmp_path)
    assert d.is_downloaded(tmp_path) is True


# ---------- NLTKBackedDownloader shape ---------------------------------


class _FakeNLTKDownloader(NLTKBackedDownloader):
    NLTK_PACKAGES = [("bogus", "corpora/bogus")]
    LAYOUT_CLASS = _FakeLayout

    def meta(self) -> DatasetMeta:
        return DatasetMeta(name="fake-nltk", category="test")


def test_nltk_downloader_layout_points_at_shared_nltk_dir(tmp_path: Path):
    d = _FakeNLTKDownloader()
    layout = d.layout(tmp_path)
    assert isinstance(layout, _FakeLayout)
    assert layout.nltk_data_dir == tmp_path / "nltk"
    assert layout.raw_dir == tmp_path / "test" / "fake-nltk"
