"""Path helpers: default dirs, env var override, raw_path_for."""

from __future__ import annotations

from pathlib import Path

from knowledge_extractor.paths import (
    DEFAULT_EXTRACTED_DIR,
    DEFAULT_RAW_DIR,
    default_extracted_dir,
    default_raw_dir,
    raw_path_for,
)


def test_defaults():
    # With no env override, defaults resolve to the canonical project dirs
    assert default_raw_dir() == Path(DEFAULT_RAW_DIR)
    assert default_extracted_dir() == Path(DEFAULT_EXTRACTED_DIR)


def test_env_override_raw(monkeypatch):
    monkeypatch.setenv("KNOWLEDGE_RAW_DIR", "/mnt/big-disk/raw")
    assert default_raw_dir() == Path("/mnt/big-disk/raw")


def test_env_override_extracted(monkeypatch):
    monkeypatch.setenv("KNOWLEDGE_EXTRACTED_DIR", "/mnt/big-disk/extracted")
    assert default_extracted_dir() == Path("/mnt/big-disk/extracted")


def test_raw_path_for():
    # raw_path_for is pure — no mkdir side effect
    p = raw_path_for("/tmp/raw", "linguistics", "wordnet")
    assert p == Path("/tmp/raw/linguistics/wordnet")
    assert not p.exists()
