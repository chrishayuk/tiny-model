"""End-to-end demo — extracts domain/standards and prints a summary.

Run from anywhere (paths are resolved relative to this file):

    python3 examples/run_demo.py

Why domain/standards? It's the only tier-1 extractor with zero external
dependencies — pure hand-curated IANA tables. It runs in ~50ms and
exercises the full pipeline: extract → normalise → filter → dedup → write
per-relation JSON files + manifest. Use it to sanity-check an install.

The demo writes to a scratch directory under examples/ (gitignored), so
it never touches your real datasets/extracted/ tree. For a real run:

    python3 -m knowledge_extractor.cli extract linguistics/wordnet
"""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent   # knowledge-extractor/
MONOREPO_ROOT = PROJECT_ROOT.parent                     # tiny-model/
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from knowledge_extractor.manifest import summarise, verify  # noqa: E402
from knowledge_extractor.registry import instantiate  # noqa: E402
from knowledge_extractor.runner import PipelineRunner  # noqa: E402


def main() -> int:
    output_dir = PROJECT_ROOT / "examples" / "_demo_output"
    raw_dir = MONOREPO_ROOT / "datasets" / "raw"
    if output_dir.exists():
        shutil.rmtree(output_dir)

    print("1. running extractor: domain/standards")
    print("-" * 60)
    runner = PipelineRunner({"output_dir": str(output_dir), "raw_dir": str(raw_dir)})
    runner.run_all(instantiate(["domain/standards"]))

    print("\n2. verifying manifest consistency")
    print("-" * 60)
    issues = verify(output_dir)
    if issues:
        for i in issues:
            print(f"  x {i}")
        return 1
    print("  ok")

    print("\n3. dataset manifest")
    print("-" * 60)
    manifest_path = output_dir / "domain" / "standards" / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    print(f"  dataset:     {manifest['dataset']}")
    print(f"  category:    {manifest['category']}")
    print(f"  layer_band:  {manifest['layer_band']}")
    print(f"  raw:         {manifest['raw_triples']}")
    print(f"  kept:        {manifest['kept_triples']}")
    print(f"  filter_rate: {manifest['filter_rate']}")
    print(f"  relations:")
    for rel, info in manifest["relations"].items():
        print(f"    {rel:15s} {info['pairs']:4d} pairs  ->  {info['file']}")

    print("\n4. sample pairs from http_status.json")
    print("-" * 60)
    status = json.loads((output_dir / "domain" / "standards" / "http_status.json").read_text())
    for a, b in status["pairs"][:8]:
        print(f"  {a:4s}  {b}")

    print("\n5. global summary")
    print("-" * 60)
    print(json.dumps(summarise(output_dir), indent=2))

    print(f"\noutput written to: {output_dir}")
    print(f"raw cache:         {raw_dir}")
    print("delete the demo output with: rm -rf examples/_demo_output")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
