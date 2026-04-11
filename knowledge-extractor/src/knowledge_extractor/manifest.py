"""Manifest helpers — stats summarisation and verification."""

from __future__ import annotations

import json
from pathlib import Path


def load_manifest(path: Path) -> dict:
    with open(path) as fh:
        return json.load(fh)


def walk_dataset_manifests(data_dir: Path):
    for manifest_path in data_dir.rglob("manifest.json"):
        if manifest_path.parent == data_dir:
            continue
        yield manifest_path, load_manifest(manifest_path)


def summarise(data_dir: Path) -> dict:
    categories: dict[str, dict] = {}
    datasets = 0
    total = 0
    for _, m in walk_dataset_manifests(data_dir):
        cat = m.get("category", "uncategorised")
        slot = categories.setdefault(
            cat,
            {
                "datasets": [],
                "layer_band": m.get("layer_band", ""),
                "total_pairs": 0,
            },
        )
        slot["datasets"].append(m["dataset"])
        slot["total_pairs"] += m.get("total_pairs", 0)
        datasets += 1
        total += m.get("total_pairs", 0)
    return {
        "categories": categories,
        "totals": {
            "categories": len(categories),
            "datasets": datasets,
            "total_pairs": total,
        },
    }


def verify(data_dir: Path) -> list[str]:
    """Return a list of human-readable issues found in the data tree."""
    issues: list[str] = []
    for manifest_path, m in walk_dataset_manifests(data_dir):
        base = manifest_path.parent
        for rel_name, rel_info in m.get("relations", {}).items():
            f = base / rel_info["file"]
            if not f.exists():
                issues.append(f"missing file: {f}")
                continue
            try:
                with open(f) as fh:
                    data = json.load(fh)
            except Exception as e:
                issues.append(f"unreadable {f}: {e}")
                continue
            if data.get("pair_count") != len(data.get("pairs", [])):
                issues.append(f"pair_count mismatch in {f}")
            if rel_info["pairs"] != len(data.get("pairs", [])):
                issues.append(f"manifest/file pair mismatch for {rel_name} in {base}")
    return issues
