"""Fetches the Geofabrik Great Britain PBF extract.

~2 GB streaming download with a tqdm byte-progress bar and HTTP Range
resume support (Geofabrik honours ``Range:`` so a killed download picks
up at the .tmp sibling's current size). The final file is renamed into
place atomically so a killed run never leaves a corrupted target.
"""

from __future__ import annotations

import os
from pathlib import Path

import requests
from tqdm import tqdm

from ...base import BaseDownloader, DatasetMeta
from .model import GEOFABRIK_URL, META, MIN_PBF_BYTES, OsmGbRawLayout


CHUNK_BYTES = 1024 * 1024  # 1 MiB
REQUEST_TIMEOUT = 600
USER_AGENT = "knowledge-extractor/0.3"


class OsmGbDownloader(BaseDownloader):
    def meta(self) -> DatasetMeta:
        return META

    def layout(self, raw_dir: Path) -> OsmGbRawLayout:
        return OsmGbRawLayout(raw_dir=self.raw_path(raw_dir))

    def download(self, raw_dir: Path) -> None:
        layout = self.layout(raw_dir)
        target = layout.pbf_path()
        if target.exists() and target.stat().st_size >= MIN_PBF_BYTES:
            return

        tmp = target.with_suffix(target.suffix + ".tmp")
        tmp.parent.mkdir(parents=True, exist_ok=True)
        # Resume partial downloads: if a previous run died mid-transfer the
        # .tmp will still be here. Geofabrik supports Range requests.
        resume_from = tmp.stat().st_size if tmp.exists() else 0

        session = requests.Session()
        session.headers["User-Agent"] = USER_AGENT
        headers: dict[str, str] = {}
        if resume_from:
            headers["Range"] = f"bytes={resume_from}-"

        with session.get(
            GEOFABRIK_URL,
            stream=True,
            timeout=REQUEST_TIMEOUT,
            headers=headers,
        ) as r:
            # If the server can't honour the range request it sends 200 and
            # the whole file — restart the .tmp from scratch in that case.
            if resume_from and r.status_code == 200:
                resume_from = 0
            r.raise_for_status()

            content_length = int(r.headers.get("content-length", 0))
            total = (content_length + resume_from) if content_length else None

            mode = "ab" if resume_from else "wb"
            with open(tmp, mode) as f, tqdm(
                total=total,
                initial=resume_from,
                unit="B",
                unit_scale=True,
                unit_divisor=1024,
                desc="osm-gb",
                miniters=1,
            ) as bar:
                for chunk in r.iter_content(chunk_size=CHUNK_BYTES):
                    if chunk:
                        f.write(chunk)
                        bar.update(len(chunk))

        os.replace(tmp, target)
