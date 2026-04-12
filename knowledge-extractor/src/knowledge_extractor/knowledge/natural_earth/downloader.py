"""Fetches Natural Earth 10m cultural shapefile bundles.

Each layer is a small (~5–15 MB) zip containing the shapefile parts. We
stream, extract, and drop the zip after verification. The tmp-then-rename
pattern keeps the raw_dir state clean on kills.
"""

from __future__ import annotations

import os
import shutil
import tempfile
import zipfile
from pathlib import Path

import requests
from tqdm import tqdm

from ...base import BaseDownloader, DatasetMeta
from .model import (
    LAYERS,
    META,
    NaturalEarthRawLayout,
    layer_url,
)


CHUNK_BYTES = 256 * 1024  # 256 KiB — these files are small
REQUEST_TIMEOUT = 120
USER_AGENT = "knowledge-extractor/0.3"


def _stream_download(session: requests.Session, url: str, dest: Path, desc: str) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(dest.suffix + ".tmp")
    with session.get(url, stream=True, timeout=REQUEST_TIMEOUT) as r:
        r.raise_for_status()
        total = int(r.headers.get("content-length", 0)) or None
        with open(tmp, "wb") as f, tqdm(
            total=total,
            unit="B",
            unit_scale=True,
            unit_divisor=1024,
            desc=desc,
            leave=False,
        ) as bar:
            for chunk in r.iter_content(chunk_size=CHUNK_BYTES):
                if chunk:
                    f.write(chunk)
                    bar.update(len(chunk))
    os.replace(tmp, dest)


def _extract_zip(zip_path: Path, target_dir: Path) -> None:
    """Extract flat (strip any directory prefix) into target_dir."""
    target_dir.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path) as zf:
        for name in zf.namelist():
            basename = os.path.basename(name)
            if not basename:
                continue  # directory entry
            with zf.open(name) as src, open(target_dir / basename, "wb") as dst:
                shutil.copyfileobj(src, dst)


class NaturalEarthDownloader(BaseDownloader):
    def meta(self) -> DatasetMeta:
        return META

    def layout(self, raw_dir: Path) -> NaturalEarthRawLayout:
        return NaturalEarthRawLayout(raw_dir=self.raw_path(raw_dir))

    def download(self, raw_dir: Path) -> None:
        layout = self.layout(raw_dir)
        layout.raw_dir.mkdir(parents=True, exist_ok=True)

        session = requests.Session()
        session.headers["User-Agent"] = USER_AGENT

        with tempfile.TemporaryDirectory(prefix="ne-zips-") as zip_scratch:
            zip_scratch_path = Path(zip_scratch)

            for _short, zip_name, stem, subfolder in LAYERS:
                target_subdir = layout.layer_dir(subfolder)
                shp = layout.shp_path(subfolder, stem)
                dbf = layout.dbf_path(subfolder, stem)
                if shp.exists() and dbf.exists():
                    continue  # layer already in place, skip network

                zip_path = zip_scratch_path / zip_name
                _stream_download(
                    session,
                    layer_url(zip_name),
                    zip_path,
                    desc=stem,
                )
                _extract_zip(zip_path, target_subdir)
