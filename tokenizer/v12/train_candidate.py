#!/usr/bin/env python3
"""Trains one real TOK-1 grid candidate on the v0 C8 corpus.

The first genuinely-trained TOK-1 candidate tokenizer in this funnel --
real SentencePiece training, not simulated. Emits both the native .model
and a vocab.json in the same {"pieces":[...], "special": {...}} shape
tokenizer_bench.py already reads, so census/intrinsics run against it
unmodified.

Run: python3 tokenizer/v12/train_candidate.py --algorithm unigram --vocab-size 4000
"""
import argparse
import json
from pathlib import Path

import sentencepiece as spm

V12_ROOT = Path(__file__).resolve().parent
CORPUS_TXT = V12_ROOT / "c8_corpus_v0.txt"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--algorithm", choices=["unigram", "bpe"], default="unigram")
    ap.add_argument("--vocab-size", type=int, default=4000)
    ap.add_argument("--candidate-id", default=None)
    args = ap.parse_args()

    candidate_id = args.candidate_id or f"{args.algorithm}_sp_{args.vocab_size}_v0"
    out_dir = V12_ROOT / "candidates" / candidate_id
    out_dir.mkdir(parents=True, exist_ok=True)
    model_prefix = str(out_dir / candidate_id)

    spm.SentencePieceTrainer.train(
        input=str(CORPUS_TXT),
        model_prefix=model_prefix,
        vocab_size=args.vocab_size,
        model_type=args.algorithm,
        character_coverage=0.9995,
        split_digits=True,  # C6: single-char digits
        pad_id=0, unk_id=1, bos_id=2, eos_id=3,
        pad_piece="<pad>", unk_piece="<unk>", bos_piece="<s>", eos_piece="</s>",
        input_sentence_size=0,  # use all lines
        shuffle_input_sentence=True,
        seed_sentencepiece_size=1000000,
    )

    sp = spm.SentencePieceProcessor(model_file=model_prefix + ".model")
    pieces = [{"id": i, "text": sp.id_to_piece(i), "score": sp.get_score(i)} for i in range(sp.vocab_size())]
    vocab_json = {
        "version": 1,
        "special": {"pad_id": 0, "unk_id": 1, "bos_id": 2, "eos_id": 3},
        "pieces": pieces,
    }
    vocab_path = out_dir / f"{candidate_id}.vocab.json"
    vocab_path.write_text(json.dumps(vocab_json))

    print(json.dumps({
        "candidate_id": candidate_id,
        "algorithm": args.algorithm,
        "requested_vocab_size": args.vocab_size,
        "actual_vocab_size": sp.vocab_size(),
        "model_path": str(model_prefix + ".model"),
        "vocab_json_path": str(vocab_path),
    }, indent=2))


if __name__ == "__main__":
    main()
