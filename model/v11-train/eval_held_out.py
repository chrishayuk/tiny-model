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
documents, matching commitment C3's "frozen held-out slice" principle.

CONTAMINATION FIX (2026-07-19): an earlier version of this script used a
different seed (777 vs training's 42) and claimed this "guaranteed no
overlap" -- that claim was wrong and unverified. HF's streaming
.shuffle(seed, buffer_size=10000) only does a local buffered pseudo-shuffle,
not a true partition of the dataset; a different seed does NOT guarantee a
disjoint "first N" subset, especially when N is the same order of magnitude
as the buffer. Checked empirically: 63/2000 (3.15%) of the original
seed=777 held-out set really did overlap with the first 200k documents of
the seed=42 training stream. Fixed properly: computes the EXACT set of
document hashes the shared byte-matched phase1 budget (53,727,676 bytes --
the same budget every v12 candidate trains to) consumes from the seed=42
stream, then explicitly excludes any of those hashes from the held-out
set, topping back up to N_HELD_OUT_STORIES with fresh seed=777 documents
that are verified NOT in the training-consumed set. v11 is a separate,
unresolved case: its original training script (train_tinystories.py) never
pinned a dataset revision, so its exact training-time document set can't be
reconstructed from today's hub state -- this is a real, disclosed
limitation, not silently assumed clean. See v11-replication note below.

Run (from tiny-model repo root):
  uv run --project model/v11-train python model/v11-train/eval_held_out.py
"""

from __future__ import annotations

import hashlib
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
HELD_OUT_SEED = 777  # distinct from training SEED=42 -- NOT sufficient alone, see contamination fix above; explicit hash-exclusion is what actually matters
N_HELD_OUT_STORIES = 2000
MAX_SEQ = 256
# shared byte-matched phase1 budget every v12 candidate trains to (see
# train_tok2.py V11_REFERENCE_BYTES_PHASE1) -- defines the exact boundary
# of what the seed=42 training stream has consumed, for exclusion.
TRAINING_CONSUMPTION_BYTES = 53_727_676
TRAINING_SEED = 42
TRAINING_BUFFER_SIZE = 10000


def compute_training_consumed_hashes():
    """The exact sha256 hashes of every document the seed=42 stream yields
    up to the shared byte budget -- i.e. what every v12 phase1 candidate
    actually trained on, regardless of how many TOKENS that byte count
    happened to produce for each one."""
    from datasets import load_dataset
    ds = load_dataset("roneneldan/TinyStories", split="train", streaming=True, revision=HUB_SHA)
    ds = ds.shuffle(seed=TRAINING_SEED, buffer_size=TRAINING_BUFFER_SIZE)
    hashes = set()
    cum_bytes = 0
    for ex in ds:
        b = ex["text"].encode("utf-8")
        cum_bytes += len(b)
        hashes.add(hashlib.sha256(b).hexdigest())
        if cum_bytes >= TRAINING_CONSUMPTION_BYTES:
            break
    return hashes

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
    print("Computing exact training-consumed document hashes (seed=42, byte-matched boundary)...")
    consumed = compute_training_consumed_hashes()
    print(f"  {len(consumed):,} documents actually consumed by the shared byte-matched phase1 budget")

    from datasets import load_dataset
    ds = load_dataset("roneneldan/TinyStories", split="train", streaming=True, revision=HUB_SHA)
    ds = ds.shuffle(seed=HELD_OUT_SEED, buffer_size=10000)
    texts = []
    skipped = 0
    for ex in ds:
        if len(texts) >= N_HELD_OUT_STORIES:
            break
        h = hashlib.sha256(ex["text"].encode("utf-8")).hexdigest()
        if h in consumed:
            skipped += 1
            continue
        texts.append(ex["text"])
    print(f"  skipped {skipped} seed=777 documents that were also in the training-consumed set "
          f"(this is the real, measured contamination the earlier version of this script missed)")
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

    print(f"Held-out set: up to {N_HELD_OUT_STORIES} TinyStories, seed={HELD_OUT_SEED}, "
          f"VERIFIED excluded from the seed=42/byte-matched training-consumed set")
    print("NOTE -- v11 caveat: this exclusion is verified against the v12 candidates' training "
          "consumption (pinned hub_sha, seed=42, byte-matched budget, fully reproducible). v11's "
          "ORIGINAL training (train_tinystories.py) never pinned a dataset revision, so its exact "
          "training-time document set cannot be reconstructed from today's hub state -- v11's "
          "held-out cleanliness here is NOT independently verified, only assumed. A v11 replication "
          "under this same pinned-revision harness is needed to close that gap.\n")
    texts = load_held_out_texts()
    total_bytes = sum(len(t.encode("utf-8")) for t in texts)
    print(f"  {len(texts)} verified-clean stories, {total_bytes:,} bytes\n")

    results = {}
    for name, spec in CHECKPOINTS.items():
        print(f"Evaluating: {name}")
        r = eval_checkpoint(name, spec, texts, device, config)
        if r:
            results[name] = r
            print(f"  held_out_loss={r['held_out_loss']:.4f}  held_out_bpb={r['held_out_bpb']:.4f}")
        print()

    out_path = V_TOKENIZERS / "v12" / "training" / "tok2_runs" / "held_out_eval_verified_clean.json"
    with open(out_path, "w") as f:
        json.dump({
            "seed": HELD_OUT_SEED,
            "n_stories": len(texts),
            "total_bytes": total_bytes,
            "verified_excluded_from_v12_training_consumption": True,
            "v11_cleanliness_verified": False,
            "v11_caveat": "v11's original training never pinned a dataset revision; its exact "
                           "training-time document set can't be reconstructed, so this held-out "
                           "set's disjointness from v11's actual training data is NOT verified, "
                           "only assumed. Needs a v11 replication under this pinned-revision harness.",
            "results": results,
        }, f, indent=2)
    print(f"saved {out_path}")


if __name__ == "__main__":
    main()
