#!/usr/bin/env python3
"""Assembles the v0 C8 tokenizer-training corpus: prose + math/structured + code.

This is a PROTOTYPE-SCALE mixture to unblock real TOK-1 experimentation now,
not the final frozen C8 (mixture proportions here are provisional, dedup/
repeated-identifier-cap/C3-exclusion are NOT yet implemented -- disclosed in
the manifest, not silently skipped).

Domains:
  prose            streamed from roneneldan/TinyStories, same pinned hub
                    revision as the C2 eval stream, seeded sample
  math_structured   sampled from cn7/cn8 corpora (cell-native-architectures,
                    referenced in place, not copied) -- extracts the "text"
                    field only
  code             the full v0 code corpus already built by
                    build_code_corpus.py (c8_code_corpus.jsonl)

Run: python3 tokenizer/v12/assemble_c8_corpus.py
"""
import json
import random
from pathlib import Path

V12_ROOT = Path(__file__).resolve().parent
REPO_ROOT = V12_ROOT.parent.parent

HUB_SHA = "f54c09fd23315a6f9c86f9dc80f725de7d8f9c64"  # same pinned revision as C2 eval stream
SEED = 20260719
N_PROSE = 1500
N_MATH = 4000

CN_DATASETS = Path("/Users/christopherhay/chris-source/cell80/experiments/cell-native-architectures/artifacts/datasets")
MATH_FILES = ["cn7_corpus_train.jsonl", "cn8_corpus_b.jsonl", "cn8_corpus_atok.jsonl", "cn8_corpus_aex.jsonl"]

OUT_JSONL = V12_ROOT / "c8_corpus_v0.jsonl"
OUT_TXT = V12_ROOT / "c8_corpus_v0.txt"
OUT_MANIFEST = V12_ROOT / "c8_manifest.json"


def sample_prose(n, seed):
    from datasets import load_dataset
    ds = load_dataset("roneneldan/TinyStories", split="train", streaming=True, revision=HUB_SHA)
    ds = ds.shuffle(seed=seed, buffer_size=10000)
    rows = []
    for i, ex in enumerate(ds):
        if i >= n:
            break
        rows.append({"domain": "prose", "source": "roneneldan/TinyStories", "text": ex["text"]})
    return rows


def sample_math(n, seed):
    rng = random.Random(seed)
    all_texts = []
    per_file_counts = {}
    for fname in MATH_FILES:
        path = CN_DATASETS / fname
        texts = []
        with path.open() as f:
            for line in f:
                row = json.loads(line)
                if "text" in row:
                    texts.append(row["text"])
        per_file_counts[fname] = len(texts)
        all_texts.extend((fname, t) for t in texts)
    rng.shuffle(all_texts)
    chosen = all_texts[:n]
    return [{"domain": "math_structured", "source": f"cell-native-architectures/{fname}", "text": t} for fname, t in chosen], per_file_counts


def load_code():
    rows = []
    with (V12_ROOT / "c8_code_corpus.jsonl").open() as f:
        for line in f:
            r = json.loads(line)
            rows.append({"domain": "code", "source": r["path"], "text": r["text"]})
    return rows


def main():
    prose_rows = sample_prose(N_PROSE, SEED)
    math_rows, math_file_counts = sample_math(N_MATH, SEED)
    code_rows = load_code()

    all_rows = prose_rows + math_rows + code_rows
    rng = random.Random(SEED)
    rng.shuffle(all_rows)

    with OUT_JSONL.open("w") as f:
        for r in all_rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    # flat training-input txt for SentencePiece: one "sentence" per line;
    # internal newlines (only in code rows) are flattened to spaces for this
    # v0 -- consistent with v11's own metaspace normalization treating all
    # whitespace runs as a single boundary (see roundtrip finding).
    with OUT_TXT.open("w") as f:
        for r in all_rows:
            f.write(r["text"].replace("\n", " ").replace("\r", " ") + "\n")

    domain_bytes = {}
    for r in all_rows:
        b = len(r["text"].encode("utf-8"))
        domain_bytes[r["domain"]] = domain_bytes.get(r["domain"], 0) + b
    total_bytes = sum(domain_bytes.values())

    manifest = {
        "role": "v0 C8 tokenizer-training corpus -- PROTOTYPE SCALE, provisional mixture proportions",
        "not_yet_implemented": ["normalization spec", "dedup", "C3-slice exclusion", "repeated-identifier cap"],
        "sampling_seed": SEED,
        "domains": {
            "prose": {
                "source": "roneneldan/TinyStories", "hub_sha": HUB_SHA, "streaming": True,
                "shuffle_buffer": 10000, "seed": SEED, "n_requested": N_PROSE,
                "n_actual": len(prose_rows), "bytes": domain_bytes.get("prose", 0),
            },
            "math_structured": {
                "source_repo": str(CN_DATASETS), "source_files": MATH_FILES,
                "source_row_counts": math_file_counts, "n_sampled": len(math_rows),
                "sampling_seed": SEED, "bytes": domain_bytes.get("math_structured", 0),
            },
            "code": {
                "source": "tokenizer/v12/c8_code_corpus.jsonl (this repo, see build_code_corpus.py)",
                "n_rows": len(code_rows), "bytes": domain_bytes.get("code", 0),
            },
        },
        "mixture_proportions_actual": {k: round(v / total_bytes, 4) for k, v in domain_bytes.items()},
        "total_rows": len(all_rows),
        "total_bytes": total_bytes,
        "output_jsonl": str(OUT_JSONL.relative_to(REPO_ROOT)),
        "output_txt_for_spm_training": str(OUT_TXT.relative_to(REPO_ROOT)),
    }
    OUT_MANIFEST.write_text(json.dumps(manifest, indent=2))
    print(json.dumps({k: v for k, v in manifest.items() if k not in ("domains",)}, indent=2))
    print(json.dumps(manifest["domains"], indent=2))


if __name__ == "__main__":
    main()
