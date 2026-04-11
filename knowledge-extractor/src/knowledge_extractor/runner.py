"""Pipeline runner — orchestrates extraction for one or more datasets."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from .base import BaseDownloader, BaseExtractor, RawTriple
from .filter import Filter
from .normaliser import Normaliser
from .paths import default_extracted_dir, default_raw_dir, setup_nltk_data_dir
from .tokeniser_check import TokeniserCheck
from .writer import TripleWriter


class PipelineRunner:
    def __init__(self, config: dict):
        self.config = config
        self.output_dir = Path(config.get("output_dir") or default_extracted_dir())
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.raw_dir = Path(config.get("raw_dir") or default_raw_dir())
        self.raw_dir.mkdir(parents=True, exist_ok=True)
        setup_nltk_data_dir(self.raw_dir)
        self.normaliser = Normaliser(profile=config.get("normaliser_profile"))
        tok_cfg = config.get("tokeniser_check")
        tokeniser = None
        if tok_cfg:
            if isinstance(tok_cfg, str):
                tokeniser = TokeniserCheck(tok_cfg)
            else:
                tokeniser = TokeniserCheck(
                    tok_cfg["model"], max_tokens=tok_cfg.get("max_tokens", 3)
                )
        self.filter = Filter(config.get("filter", {}), tokeniser=tokeniser)
        self.writer = TripleWriter()

    def download_dataset(self, downloader: BaseDownloader, *, force: bool = False) -> None:
        """Phase 1: populate raw_dir for a single dataset. Idempotent."""
        meta = downloader.meta()
        label = f"{meta.category}/{meta.name}"
        if not force and downloader.is_downloaded(self.raw_dir):
            print(f"[{label}] download: already present, skipping")
            return
        print(f"[{label}] downloading...")
        downloader.download(self.raw_dir)
        print(f"[{label}] download: complete")

    def download_all(
        self, downloaders: list[BaseDownloader], *, force: bool = False
    ) -> None:
        for d in downloaders:
            self.download_dataset(d, force=force)

    def run_dataset(self, extractor: BaseExtractor) -> dict:
        meta = extractor.meta()
        dataset_dir = extractor.output_path(str(self.output_dir))
        dataset_dir.mkdir(parents=True, exist_ok=True)

        print(f"[{meta.category}/{meta.name}] extracting...")

        ds_config = dict(self.config.get(meta.name) or {})
        ds_config.setdefault("raw_dir", self.raw_dir)

        by_relation: dict[str, list[RawTriple]] = {}
        raw_count = 0
        kept_count = 0

        for raw in extractor.extract(ds_config):
            raw_count += 1
            if not raw.source:
                raw.source = meta.name
            if not raw.layer_band:
                raw.layer_band = meta.layer_band

            normed = self.normaliser.normalise(raw)
            if normed is None:
                continue
            if not self.filter.accept(normed):
                continue

            kept_count += 1
            by_relation.setdefault(normed.relation, []).append(normed)

        relation_stats: dict[str, dict] = {}
        written_total = 0
        for relation, triples in sorted(by_relation.items()):
            filename = f"{relation}.json"
            filepath = dataset_dir / filename
            written = self.writer.write(
                triples=triples,
                output_path=str(filepath),
                relation=relation,
                source=meta.name,
                description=f"{relation} from {meta.name}",
                layer_band=meta.layer_band,
            )
            relation_stats[relation] = {"file": filename, "pairs": written}
            written_total += written

        manifest = {
            "dataset": meta.name,
            "category": meta.category,
            "version": meta.version,
            "license": meta.license,
            "url": meta.url,
            "layer_band": meta.layer_band,
            "description": meta.description,
            "extracted": datetime.now(timezone.utc).isoformat(),
            "extractor": type(extractor).__name__,
            "raw_triples": raw_count,
            "kept_triples": kept_count,
            "filter_rate": f"{kept_count / raw_count * 100:.1f}%" if raw_count else "0%",
            "relations": relation_stats,
            "total_pairs": written_total,
        }
        with open(dataset_dir / "manifest.json", "w") as fh:
            json.dump(manifest, fh, indent=2, ensure_ascii=False)

        print(
            f"  {written_total:,} triples across {len(by_relation)} relations → {dataset_dir}"
        )
        return manifest

    def run_all(self, extractors: list[BaseExtractor]) -> dict:
        stats: dict[str, dict] = {}
        for ext in extractors:
            m = self.run_dataset(ext)
            stats[f"{m['category']}/{m['dataset']}"] = m
        self._write_global_manifest(stats)
        return stats

    def _write_global_manifest(self, all_stats: dict) -> None:
        categories: dict[str, dict] = {}
        for _, s in all_stats.items():
            cat = s["category"]
            slot = categories.setdefault(
                cat,
                {"datasets": [], "layer_band": s["layer_band"], "total_pairs": 0},
            )
            slot["datasets"].append(s["dataset"])
            slot["total_pairs"] += s["total_pairs"]

        grand_total = sum(c["total_pairs"] for c in categories.values())
        manifest = {
            "version": "1.0",
            "extracted": datetime.now(timezone.utc).isoformat(),
            "categories": categories,
            "totals": {
                "categories": len(categories),
                "datasets": len(all_stats),
                "total_pairs": grand_total,
            },
        }
        with open(self.output_dir / "manifest.json", "w") as fh:
            json.dump(manifest, fh, indent=2, ensure_ascii=False)

        print(f"\nglobal: {grand_total:,} triples across {len(all_stats)} datasets")
