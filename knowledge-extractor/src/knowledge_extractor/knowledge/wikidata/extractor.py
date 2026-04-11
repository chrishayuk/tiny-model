"""Reads Wikidata raw SPARQL dumps from ``raw_dir`` and yields triples.

Pure-transform: no network. Filters out Q-id fallbacks (rows where the
endpoint returned the entity ID because no English label was available)
and self-loops.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Iterator

from ...base import BaseExtractor, DatasetMeta, RawTriple
from ...paths import default_raw_dir
from .model import META, PROPERTIES, WikidataPropertyDump, WikidataRawLayout


def _is_qid_fallback(label: str) -> bool:
    return len(label) > 1 and label.startswith("Q") and label[1:].isdigit()


class WikidataExtractor(BaseExtractor):
    def meta(self) -> DatasetMeta:
        return META

    def extract(self, config: dict) -> Iterator[RawTriple]:
        base_raw = Path(config.get("raw_dir") or default_raw_dir())
        layout = WikidataRawLayout(raw_dir=base_raw / META.category / META.name)

        for prop in PROPERTIES:
            path = layout.property_path(prop.pid)
            if not path.exists():
                continue

            try:
                raw = json.loads(path.read_text())
                dump = WikidataPropertyDump.model_validate(raw)
            except Exception as e:
                print(f"[wikidata] {prop.pid} unreadable: {type(e).__name__}: {e}")
                continue

            seen: set[tuple[str, str]] = set()
            for row in dump.bindings:
                a = row.get("itemLabel", {}).get("value", "").strip()
                b = row.get("valueLabel", {}).get("value", "").strip()
                if not a or not b or a == b:
                    continue
                if _is_qid_fallback(a) or _is_qid_fallback(b):
                    continue
                key = (a, b)
                if key in seen:
                    continue
                seen.add(key)
                yield RawTriple(
                    subject=a,
                    relation=prop.relation,
                    object=b,
                    provenance=f"wikidata:{prop.pid}",
                )
