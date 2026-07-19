#!/usr/bin/env python3
"""Builds the pure_byte (Branch B) vocab: deterministic, no training needed.
256 byte values + 4 specials = 260 tokens. Each byte value b in [0,256) is
represented by its single-byte UTF-8-unsafe form via the standard
"latin-1 surrogate" trick tokenizer_bench.py's trie already handles as
literal characters, matching how real byte-level tokenizers expose a byte
alphabet as printable/escaped single characters.

Run: python3 tokenizer/v12/training/build_pure_byte_vocab.py
"""
import json
from pathlib import Path

TRAINING_DIR = Path(__file__).resolve().parent
OUT_DIR = TRAINING_DIR / "candidates" / "pure_byte_v0"
OUT_DIR.mkdir(parents=True, exist_ok=True)


def main():
    pieces = [
        {"id": 0, "text": "<pad>", "score": 0.0},
        {"id": 1, "text": "<unk>", "score": 0.0},
        {"id": 2, "text": "<s>", "score": 0.0},
        {"id": 3, "text": "</s>", "score": 0.0},
    ]
    for b in range(256):
        # latin-1 round-trips every byte value to a single unicode code point 1:1
        pieces.append({"id": 4 + b, "text": chr(b), "score": 0.0})

    vocab_json = {
        "version": 1,
        "special": {"pad_id": 0, "unk_id": 1, "bos_id": 2, "eos_id": 3},
        "pieces": pieces,
    }
    path = OUT_DIR / "pure_byte_v0.vocab.json"
    path.write_text(json.dumps(vocab_json))
    print(json.dumps({"candidate_id": "pure_byte_v0", "algorithm": "pure_byte", "vocab_size": len(pieces), "path": str(path)}, indent=2))


if __name__ == "__main__":
    main()
