"""Shared I/O helpers: atomic writes for JSON and raw bytes.

Used by the triple writer and by downloaders that stash raw artifacts
on disk. The temp-file-then-rename pattern guarantees readers never see
a half-written file.
"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any


def _atomic_replace(path: Path, write: callable) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(
        prefix=path.name + ".", suffix=".tmp", dir=str(path.parent)
    )
    try:
        with os.fdopen(fd, "wb") as fh:
            write(fh)
        os.replace(tmp_name, path)
    except Exception:
        if os.path.exists(tmp_name):
            os.unlink(tmp_name)
        raise


def atomic_write_json(path: Path, payload: Any) -> None:
    """Atomically write ``payload`` as pretty-printed JSON to ``path``."""
    def _write(fh):
        data = json.dumps(payload, indent=2, ensure_ascii=False).encode("utf-8")
        fh.write(data)

    _atomic_replace(path, _write)


def atomic_write_bytes(path: Path, data: bytes) -> None:
    """Atomically write raw bytes to ``path``."""
    _atomic_replace(path, lambda fh: fh.write(data))
