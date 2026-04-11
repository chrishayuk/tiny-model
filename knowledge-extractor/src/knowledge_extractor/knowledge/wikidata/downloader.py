"""Fetches raw SPARQL responses for the curated Wikidata property set.

One file per property, written atomically. Re-running skips properties
whose file already exists; use ``--force`` to refetch. Retries with backoff
on 429/5xx and halves the LIMIT on truncated JSON responses (the public
endpoint can cut off large streamed replies).
"""

from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

from ...base import BaseDownloader, DatasetMeta
from ...io_utils import atomic_write_json
from .model import (
    META,
    PROPERTIES,
    SPARQL_ENDPOINT,
    USER_AGENT,
    WikidataPropertyDump,
    WikidataRawLayout,
)


DEFAULT_LIMIT = 20000
DEFAULT_LABEL_MAX = 25
REQUEST_TIMEOUT = 120
RETRY_BACKOFFS = (5, 15, 45)
DEFAULT_SLEEP_BETWEEN = 1.0


def _build_query(pid: str, limit: int, label_max: int) -> str:
    return f"""
SELECT ?itemLabel ?valueLabel WHERE {{
  ?item wdt:{pid} ?value .
  ?item rdfs:label ?itemLabel . FILTER(LANG(?itemLabel) = "en")
  ?value rdfs:label ?valueLabel . FILTER(LANG(?valueLabel) = "en")
  FILTER(STRLEN(?itemLabel) <= {label_max})
  FILTER(STRLEN(?valueLabel) <= {label_max})
}}
LIMIT {limit}
""".strip()


def _run_sparql(
    session: requests.Session, pid: str, limit: int, label_max: int
) -> tuple[list[dict], str, int]:
    """Run a SPARQL query with retries; halve LIMIT on JSON-decode failures.

    Returns ``(bindings, final_query, final_limit)`` so the caller can record
    exactly what was executed in the property dump.
    """
    last_err: Exception | None = None
    current_limit = limit
    query = _build_query(pid, current_limit, label_max)
    for backoff in (0,) + RETRY_BACKOFFS:
        if backoff:
            time.sleep(backoff)
        query = _build_query(pid, current_limit, label_max)
        try:
            r = session.get(
                SPARQL_ENDPOINT,
                params={"query": query, "format": "json"},
                timeout=REQUEST_TIMEOUT,
            )
            if r.status_code == 429 or r.status_code >= 500:
                last_err = RuntimeError(f"HTTP {r.status_code}")
                continue
            r.raise_for_status()
            try:
                bindings = r.json().get("results", {}).get("bindings", [])
                return bindings, query, current_limit
            except json.JSONDecodeError as je:
                last_err = je
                if current_limit > 1000:
                    current_limit = max(1000, current_limit // 2)
                continue
        except Exception as e:
            last_err = e
    raise RuntimeError(f"SPARQL query failed after retries: {last_err}")


class WikidataDownloader(BaseDownloader):
    def meta(self) -> DatasetMeta:
        return META

    def layout(self, raw_dir: Path) -> WikidataRawLayout:
        return WikidataRawLayout(raw_dir=self.raw_path(raw_dir))

    def download(self, raw_dir: Path) -> None:
        layout = self.layout(raw_dir)
        limit = DEFAULT_LIMIT
        label_max = DEFAULT_LABEL_MAX

        session = requests.Session()
        session.headers.update(
            {
                "User-Agent": USER_AGENT,
                "Accept": "application/sparql-results+json",
            }
        )

        for prop in PROPERTIES:
            target = layout.property_path(prop.pid)
            if target.exists():
                continue

            try:
                bindings, query, final_limit = _run_sparql(
                    session, prop.pid, limit, label_max
                )
            except Exception as e:
                print(f"[wikidata] {prop.pid} {prop.relation}: {type(e).__name__}: {e}")
                continue

            dump = WikidataPropertyDump(
                pid=prop.pid,
                relation=prop.relation,
                category=prop.category,
                description=prop.description,
                query=query,
                limit=final_limit,
                label_max=label_max,
                downloaded_at=datetime.now(timezone.utc).isoformat(),
                bindings=bindings,
            )
            atomic_write_json(target, dump.model_dump())
            # Politeness sleep only on successful fetch, not on cache skip.
            time.sleep(DEFAULT_SLEEP_BETWEEN)
