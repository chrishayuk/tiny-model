#!/usr/bin/env python3
"""Held-out BPB evaluation for TOK-2 candidates -- the fair, decision-quality
number, as distinct from the training-loop loss reported by train_tok2.py.

Why this exists: train_tok2.py reports the running loss on streamed,
never-repeated training data -- a reasonable online signal, but not a clean
apples-to-apples comparison, since different candidates consume different
numbers of documents (different byte-matched token budgets) from the same
seeded stream, so their "current batch at the end of training" differs in
content. This script instead evaluates every candidate's FINAL saved
checkpoint against the exact SAME fixed held-out set of TinyStories
documents -- disjoint from all training runs (different seed), matching
commitment C3's "frozen held-out slice" principle.

Run (from tiny-model repo root):
  uv run --project model/v11-train python model/v11-train/eval_held_out.py
"""

from __future__ import annotations

import json
import math
from pathlib import Path

import torch
import torch.nn.functional as F

from tiny_model_v11 import TinyModel, load_config
from train_tok2 import (
    CHRIS_EXPERIMENTS_V11_MODEL,
    HUB_SHA,
    V_TOKENIZERS,
    V11_ARTIFACT_DIR,
    HFWrappedTokenizer,
    NativeSPTokenizer,
    load_tokenizer,
    make_model,
)

REPO = Path(__file__).resolve().parent.parent.parent
HELD_OUT_SEED = 777  # distinct from training SEED=42 in train_tok2.py / train_tinystories.py -- guarantees no overlap regardless of per-candidate budget differences
N_HELD_OUT_STORIES = 2000
MAX_SEQ = 256

CHECKPOINTS = {
    "v11": {
        "candidate": "v11",
        "path": V11_ARTIFACT_DIR / "artifacts" / "model_full.pt",
        "vocab_size": 71261,
    },
    "bpe_sp_16000_v1_tcoreseed_bytefallback": {
        "candidate": "bpe_sp_16000_v1_tcoreseed_bytefallback",
        "path": V_TOKENIZERS / "v12" / "training" / "tok2_runs" / "bpe_sp_16000_v1_tcoreseed_bytefallback" / "model_full.pt",
        "vocab_size": 16000,
    },
    "unigram_sp_18000_v2_tcoreseed_bytefallback": {
        "candidate": "unigram_sp_18000_v2_tcoreseed_bytefallback",
        "path": V_TOKENIZERS / "v12" / "training" / "tok2_runs" / "unigram_sp_18000_v2_tcoreseed_bytefallback" / "model_full.pt",
        "vocab_size": 18000,
    },
    "unigram_sp_16000_v2_tcoreseed_bytefallback": {
        "candidate": "unigram_sp_16000_v2_tcoreseed_bytefallback",
        "path": V_TOKENIZERS / "v12" / "training" / "tok2_runs" / "unigram_sp_16000_v2_tcoreseed_bytefallback" / "model_full.pt",
        "vocab_size": 16000,
    },
}


def load_held_out_texts():
    from datasets import load_dataset
    ds = load_dataset("roneneldan/TinyStories", split="train", streaming=True, revision=HUB_SHA)
    ds = ds.shuffle(seed=HELD_OUT_SEED, buffer_size=10000)
    texts = []
    for i, ex in enumerate(ds):
        if i >= N_HELD_OUT_STORIES:
            break
        texts.append(ex["text"])
    return texts


@torch.no_grad()
def eval_checkpoint(name, spec, texts, device, config):
    if not spec["path"].exists():
        print(f"  [skip] {name}: checkpoint not found at {spec['path']}")
        return None

    tok = load_tokenizer(spec["candidate"])
    assert tok.vocab_size == spec["vocab_size"], f"{name}: expected vocab {spec['vocab_size']}, tokenizer reports {tok.vocab_size}"

    total_bytes = sum(len(t.encode("utf-8")) for t in texts)
    all_ids = []
    for t in texts:
        all_ids.extend(tok.encode(t, add_special_tokens=True))
    total_tokens_real = len(all_ids)
    compression = total_tokens_real / total_bytes

    model = make_model(device, tok.vocab_size, config)
    state = torch.load(spec["path"], map_location=device)
    model.load_state_dict(state)
    model.eval()

    chunks = [all_ids[i:i + MAX_SEQ] for i in range(0, len(all_ids) - MAX_SEQ, MAX_SEQ)]
    total_loss, n_chunks = 0.0, 0
    batch_size = 8
    for i in range(0, len(chunks), batch_size):
        batch = chunks[i:i + batch_size]
        batch = torch.tensor(batch, dtype=torch.long, device=device)
        logits = model(batch)
        loss = F.cross_entropy(
            logits[:, :-1, :].contiguous().view(-1, tok.vocab_size),
            batch[:, 1:].contiguous().view(-1),
            ignore_index=0,
        )
        total_loss += loss.item() * batch.size(0)
        n_chunks += batch.size(0)

    avg_loss = total_loss / n_chunks
    bpb = (avg_loss / math.log(2)) * compression
    return {
        "name": name,
        "held_out_loss": avg_loss,
        "held_out_bpb": bpb,
        "held_out_compression": compression,
        "n_chunks": n_chunks,
        "n_stories": len(texts),
        "total_bytes": total_bytes,
    }


def main():
    device = torch.device("mps" if torch.backends.mps.is_available() else "cpu")
    config = load_config(V11_ARTIFACT_DIR)

    print(f"Held-out set: {N_HELD_OUT_STORIES} TinyStories, seed={HELD_OUT_SEED} "
          f"(disjoint from all training runs, which use seed=42)")
    texts = load_held_out_texts()
    total_bytes = sum(len(t.encode("utf-8")) for t in texts)
    print(f"  {len(texts)} stories, {total_bytes:,} bytes\n")

    results = {}
    for name, spec in CHECKPOINTS.items():
        print(f"Evaluating: {name}")
        r = eval_checkpoint(name, spec, texts, device, config)
        if r:
            results[name] = r
            print(f"  held_out_loss={r['held_out_loss']:.4f}  held_out_bpb={r['held_out_bpb']:.4f}")
        print()

    out_path = V_TOKENIZERS / "v12" / "training" / "tok2_runs" / "held_out_eval.json"
    with open(out_path, "w") as f:
        json.dump({"seed": HELD_OUT_SEED, "n_stories": len(texts), "results": results}, f, indent=2)
    print(f"saved {out_path}")


if __name__ == "__main__":
    main()
