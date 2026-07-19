#!/usr/bin/env python3
"""Trains a real byte-level BPE candidate (the byte_level_bpe grid family)
using the `tokenizers` library, on the same v0 C8 corpus. SentencePiece's
unigram/bpe model types (used by train_candidate.py) aren't byte-level;
this is a structurally different tokenizer family so it gets its own
trainer, emitting the same vocab.json shape tokenizer_bench.py reads.

Run: python3 tokenizer/v12/training/train_byte_level_bpe.py --vocab-size 4000
"""
import argparse
import json
from pathlib import Path

from tokenizers import ByteLevelBPETokenizer

TRAINING_DIR = Path(__file__).resolve().parent
V12_ROOT = TRAINING_DIR.parent
CORPUS_TXT = V12_ROOT / "corpus" / "c8_corpus_v0.txt"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--vocab-size", type=int, default=4000)
    args = ap.parse_args()

    candidate_id = f"byte_level_bpe_{args.vocab_size}_v0"
    out_dir = TRAINING_DIR / "candidates" / candidate_id
    out_dir.mkdir(parents=True, exist_ok=True)

    tok = ByteLevelBPETokenizer()
    tok.train(
        files=[str(CORPUS_TXT)],
        vocab_size=args.vocab_size,
        special_tokens=["<pad>", "<unk>", "<s>", "</s>"],
    )
    tok.save_model(str(out_dir))

    vocab = tok.get_vocab()  # {piece_str: id}
    id_to_text = {v: k for k, v in vocab.items()}
    pieces = [{"id": i, "text": id_to_text[i], "score": 0.0} for i in sorted(id_to_text)]
    vocab_json = {
        "version": 1,
        "special": {"pad_id": vocab["<pad>"], "unk_id": vocab["<unk>"], "bos_id": vocab["<s>"], "eos_id": vocab["</s>"]},
        "pieces": pieces,
    }
    vocab_path = out_dir / f"{candidate_id}.vocab.json"
    vocab_path.write_text(json.dumps(vocab_json))

    print(json.dumps({
        "candidate_id": candidate_id,
        "algorithm": "byte_level_bpe",
        "requested_vocab_size": args.vocab_size,
        "actual_vocab_size": len(vocab),
        "vocab_json_path": str(vocab_path),
    }, indent=2))


if __name__ == "__main__":
    main()
