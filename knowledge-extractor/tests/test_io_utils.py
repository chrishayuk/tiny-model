"""Atomic write helpers: happy path, overwrite, and failure cleanup."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from knowledge_extractor import io_utils
from knowledge_extractor.io_utils import atomic_write_bytes, atomic_write_json


def test_atomic_write_json_writes_pretty(tmp_path: Path):
    target = tmp_path / "sub" / "out.json"
    atomic_write_json(target, {"hello": "world", "n": 1})
    assert target.exists()
    loaded = json.loads(target.read_text())
    assert loaded == {"hello": "world", "n": 1}
    # Pretty-printed (indent=2) and UTF-8 — non-ASCII stays unescaped
    atomic_write_json(target, {"ünicøde": "ok"})
    text = target.read_text()
    assert "ünicøde" in text


def test_atomic_write_json_overwrites(tmp_path: Path):
    target = tmp_path / "out.json"
    atomic_write_json(target, {"v": 1})
    atomic_write_json(target, {"v": 2})
    assert json.loads(target.read_text())["v"] == 2


def test_atomic_write_bytes(tmp_path: Path):
    target = tmp_path / "raw.bin"
    atomic_write_bytes(target, b"\x00\x01\x02hello")
    assert target.read_bytes() == b"\x00\x01\x02hello"


def test_atomic_write_cleans_up_on_failure(tmp_path: Path):
    target = tmp_path / "out.json"

    class BadValue:
        pass

    with pytest.raises(TypeError):
        atomic_write_json(target, {"bad": BadValue()})

    # No .tmp file should be left behind
    leftover = [p for p in tmp_path.iterdir() if p.name.endswith(".tmp")]
    assert leftover == []
    assert not target.exists()


def test_atomic_write_cleans_up_on_replace_failure(tmp_path: Path):
    """If os.replace fails we still remove the tmp file."""
    target = tmp_path / "out.json"
    with patch("knowledge_extractor.io_utils.os.replace", side_effect=OSError("boom")):
        with pytest.raises(OSError):
            atomic_write_json(target, {"v": 1})
    leftover = [p for p in tmp_path.iterdir() if p.name.endswith(".tmp")]
    assert leftover == []
