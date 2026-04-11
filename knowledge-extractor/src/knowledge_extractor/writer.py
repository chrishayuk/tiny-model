"""Atomic JSON triple writer with dedup."""

from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

from .base import RawTriple


def _atomic_write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(
        prefix=path.name + ".", suffix=".tmp", dir=str(path.parent)
    )
    try:
        with os.fdopen(fd, "w") as fh:
            json.dump(payload, fh, indent=2, ensure_ascii=False)
        os.replace(tmp_name, path)
    except Exception:
        if os.path.exists(tmp_name):
            os.unlink(tmp_name)
        raise


def _dedupe(triples: Iterable[RawTriple]) -> list[list[str]]:
    seen: set[tuple[str, str]] = set()
    out: list[list[str]] = []
    for t in triples:
        key = (t.subject, t.object)
        if key in seen:
            continue
        seen.add(key)
        out.append([t.subject, t.object])
    return out


class TripleWriter:
    def write(
        self,
        triples: Iterable[RawTriple],
        output_path: str,
        relation: str,
        source: str,
        description: str,
        layer_band: str,
    ) -> int:
        pairs = _dedupe(triples)
        payload = {
            "source": source,
            "relation": relation,
            "description": description,
            "layer_band": layer_band,
            "extracted": datetime.now(timezone.utc).isoformat(),
            "pair_count": len(pairs),
            "pairs": pairs,
        }
        _atomic_write_json(Path(output_path), payload)
        return len(pairs)
