"""Command-line entry point: ``knowledge-extractor ...``.

The pipeline is split into two phases:

* ``download`` — populate ``<raw_dir>`` for the selected datasets.
* ``extract``  — read ``<raw_dir>`` and write triples under ``<output>``.
* ``run``      — download followed by extract. Convenience for the common case.

Selection flags (``--tier``, ``--category``, ``--all``, or a positional key)
are identical across all three phases.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .manifest import summarise, verify
from .paths import DEFAULT_EXTRACTED_DIR, DEFAULT_RAW_DIR
from .registry import (
    DATASETS,
    TIERS,
    instantiate_downloaders,
    instantiate_extractors,
    keys_for_category,
    try_meta,
)
from .runner import PipelineRunner


def _load_config(path: str | None, output_dir: str, raw_dir: str) -> dict:
    if not path:
        return {"output_dir": output_dir, "raw_dir": raw_dir}
    try:
        import yaml  # type: ignore
    except ImportError:
        print("ERROR: pyyaml required for --config. `uv add pyyaml`.", file=sys.stderr)
        sys.exit(2)
    with open(path) as fh:
        cfg = yaml.safe_load(fh) or {}
    cfg.setdefault("output_dir", output_dir)
    cfg.setdefault("raw_dir", raw_dir)
    return cfg


def cmd_list(args: argparse.Namespace) -> int:
    if not DATASETS:
        print("(no datasets registered)")
        return 0
    print("Available datasets:")
    for key in sorted(DATASETS):
        m = try_meta(key)
        if m is None:
            print(f"  {key:40s}  {'(unavailable)':10s}  deps missing")
            continue
        print(f"  {key:40s}  {m.layer_band:10s}  {m.description}")
    print("\nTiers:")
    for tier, keys in TIERS.items():
        active = [k for k in keys if k in DATASETS]
        print(f"  tier {tier}: {len(active)} registered ({len(keys)} planned)")
    return 0


def _resolve_keys(args: argparse.Namespace) -> list[str]:
    if args.dataset:
        return [args.dataset]
    if args.tier is not None:
        return [k for k in TIERS.get(args.tier, []) if k in DATASETS]
    if args.category:
        return keys_for_category(args.category)
    if args.all:
        return sorted(DATASETS)
    return []


def _resolve_with_config(args: argparse.Namespace) -> tuple[list[str], dict]:
    keys = _resolve_keys(args)
    if args.config:
        cfg = _load_config(args.config, args.output, args.raw_dir)
        if not keys and "datasets" in cfg:
            keys = list(cfg["datasets"])
    else:
        cfg = {"output_dir": args.output, "raw_dir": args.raw_dir}
    return keys, cfg


def _require_keys(keys: list[str], phase: str) -> bool:
    if keys:
        return True
    print(
        f"ERROR: nothing to {phase}. pass dataset, --tier, --category, --all, or --config.",
        file=sys.stderr,
    )
    return False


def cmd_download(args: argparse.Namespace) -> int:
    keys, cfg = _resolve_with_config(args)
    if not _require_keys(keys, "download"):
        return 2
    downloaders = instantiate_downloaders(keys)
    runner = PipelineRunner(cfg)
    runner.download_all(downloaders, force=args.force)
    return 0


def cmd_extract(args: argparse.Namespace) -> int:
    keys, cfg = _resolve_with_config(args)
    if not _require_keys(keys, "extract"):
        return 2
    extractors = instantiate_extractors(keys)
    runner = PipelineRunner(cfg)
    if len(extractors) == 1:
        runner.run_dataset(extractors[0])
    else:
        runner.run_all(extractors)
    return 0


def cmd_run(args: argparse.Namespace) -> int:
    keys, cfg = _resolve_with_config(args)
    if not _require_keys(keys, "run"):
        return 2
    runner = PipelineRunner(cfg)
    runner.download_all(instantiate_downloaders(keys), force=args.force)
    extractors = instantiate_extractors(keys)
    if len(extractors) == 1:
        runner.run_dataset(extractors[0])
    else:
        runner.run_all(extractors)
    return 0


def cmd_stats(args: argparse.Namespace) -> int:
    summary = summarise(Path(args.data_dir))
    print(json.dumps(summary, indent=2))
    return 0


def cmd_verify(args: argparse.Namespace) -> int:
    issues = verify(Path(args.data_dir))
    if not issues:
        print("ok")
        return 0
    for i in issues:
        print(i)
    return 1


def _add_selection_args(sp: argparse.ArgumentParser) -> None:
    sp.add_argument("dataset", nargs="?", help="e.g. linguistics/wordnet")
    sp.add_argument(
        "--output",
        default=DEFAULT_EXTRACTED_DIR,
        help=f"transformed output base dir (default: {DEFAULT_EXTRACTED_DIR})",
    )
    sp.add_argument(
        "--raw-dir",
        default=DEFAULT_RAW_DIR,
        help=f"raw downloads base dir (default: {DEFAULT_RAW_DIR})",
    )
    sp.add_argument("--tier", type=int, choices=[1, 2, 3])
    sp.add_argument("--category", choices=["linguistics", "ast", "knowledge", "domain"])
    sp.add_argument("--all", action="store_true")
    sp.add_argument("--config", help="YAML config file")


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="knowledge-extractor")
    sub = p.add_subparsers(dest="cmd", required=True)

    sp = sub.add_parser("list", help="list registered datasets")
    sp.set_defaults(func=cmd_list)

    sp = sub.add_parser("download", help="download raw sources for one or more datasets")
    _add_selection_args(sp)
    sp.add_argument("--force", action="store_true", help="re-download even if present")
    sp.set_defaults(func=cmd_download)

    sp = sub.add_parser("extract", help="extract triples from already-downloaded raw data")
    _add_selection_args(sp)
    sp.set_defaults(func=cmd_extract)

    sp = sub.add_parser("run", help="download then extract (the common case)")
    _add_selection_args(sp)
    sp.add_argument("--force", action="store_true", help="re-download even if present")
    sp.set_defaults(func=cmd_run)

    sp = sub.add_parser("stats", help="summarise data directory")
    sp.add_argument("data_dir")
    sp.set_defaults(func=cmd_stats)

    sp = sub.add_parser("verify", help="verify manifest consistency")
    sp.add_argument("data_dir")
    sp.set_defaults(func=cmd_verify)

    return p


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
