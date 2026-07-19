#!/usr/bin/env python3
"""TOK-2: real model-training panel for the v12 tokenizer funnel.

Generalizes train_tinystories.py to train the SAME TinyModel architecture
(dim=512, 20L, 8H, 4KV, ffn=2048, max_seq=256 -- identical to v11's own
config, only vocab_size/embedding differ) on any validated v-tokenizers
candidate, with a RAW-BYTE-MATCHED training budget instead of a fixed
token count.

Why byte-matched, not token-matched: commitment C9 in the v12 design doc
is explicit -- "never: constant tokens-per-parameter across tokenizers".
v11's original training (see model/v11/artifacts/training_results.json)
used a fixed 16M/8M TOKEN budget. Different tokenizers compress
differently, so a fixed token count gives each candidate a DIFFERENT
amount of raw text -- not a fair comparison. This script instead:
  1. Takes v11's ORIGINAL real byte exposure as the reference (16M tokens
     phase1 / 8M tokens phase3, at v11's REAL measured TinyStories
     compression -- see TINYSTORIES_COMPRESSION below for how that was
     measured), and
  2. Converts that SAME byte budget into a token count for whichever
     candidate is selected, using THAT candidate's own real measured
     TinyStories compression.
So every model sees the same amount of raw text, not the same count of
differently-sized tokens -- each candidate just needs a different number
of (its own) tokens to cover it.

Reports BPB (bits per byte) as the primary comparable metric, not raw
token-level cross-entropy loss -- loss-per-token isn't comparable across
tokenizers with different bytes/token; BPB is (MAI-Thinking-1's own
evaluation discipline, per the 2026-07-19 external review, uses the same
principle).

v11 itself is tokenized via native SentencePiece against the REAL
v11.model, matching exactly how its existing trained checkpoint
(model_full.pt/model_compiled.pt) was actually produced -- not the
"canonical tokenizer.json" path decided elsewhere in this funnel, since
re-tokenizing it differently would make BPB not comparable to the
already-existing real weights. v12 candidates are loaded via
HFWrappedSPBackend-equivalent (real tokenizers.Tokenizer + byte_fallback
+ non-collapsing Metaspace), the same validated fix from the v-tokenizers
hardening pass -- required for real training, not just an eval nicety:
without it, an SP-family candidate would need <unk>-avoidance some other
way or training would waste supervision on drops.

Usage (from tiny-model repo root):
  uv run --project model/v11-train python model/v11-train/train_tok2.py --candidate v11
  uv run --project model/v11-train python model/v11-train/train_tok2.py --candidate bpe_sp_16000_v1_tcoreseed_bytefallback
  uv run --project model/v11-train python model/v11-train/train_tok2.py --candidate unigram_sp_18000_v2_tcoreseed_bytefallback
"""

from __future__ import annotations

import argparse
import json
import math
import sys
import time
from pathlib import Path

import torch
import torch.nn.functional as F
from torch.utils.data import DataLoader, IterableDataset

from tiny_model_v11 import TinyModel, load_config

REPO = Path(__file__).resolve().parents[2]  # tiny-model/
V11_ARTIFACT_DIR = REPO / "model" / "v11"
V_TOKENIZERS = REPO.parent / "v-tokenizers"
CHRIS_EXPERIMENTS_V11_MODEL = REPO.parent / "chris-experiments" / "compilation" / "15_v11_model" / "v11_tokenizer" / "v11.model"

HUB_SHA = "f54c09fd23315a6f9c86f9dc80f725de7d8f9c64"  # same pinned TinyStories revision used throughout this funnel
SEED = 42

# v11's ORIGINAL real training (model/v11/artifacts/training_results.json):
# 16,000,000 tokens phase1 + 8,000,000 tokens phase3.
V11_ORIGINAL_TOKENS_PHASE1 = 16_000_000
V11_ORIGINAL_TOKENS_PHASE3 = 8_000_000

# Real compression (tokens/byte), measured 2026-07-19 directly against an
# 8000-story TinyStories sample (hub_sha above, seed=999, shuffle_buffer
# 10000, 7,330,796 bytes) -- NOT the earlier v11/corpus proxy sample, since
# domain match to the actual training corpus matters for a byte-budget
# conversion. Recorded here, not computed live, so every training run
# uses the exact same reference numbers regardless of dataset shuffling
# noise on a later re-measurement.
TINYSTORIES_COMPRESSION = {
    "v11": 0.2978,
    "bpe_sp_16000_v1_tcoreseed_bytefallback": 0.3984,
    "unigram_sp_18000_v2_tcoreseed_bytefallback": 0.2871,
}

V11_REFERENCE_BYTES_PHASE1 = V11_ORIGINAL_TOKENS_PHASE1 / TINYSTORIES_COMPRESSION["v11"]
V11_REFERENCE_BYTES_PHASE3 = V11_ORIGINAL_TOKENS_PHASE3 / TINYSTORIES_COMPRESSION["v11"]

BATCH_SIZE = 4
LR = 3e-4


class NativeSPTokenizer:
    """v11 only -- native SentencePieceProcessor against the real v11.model,
    matching exactly how the existing model_full.pt/model_compiled.pt were
    actually trained (see module docstring for why this isn't the
    canonical-tokenizer.json path used elsewhere in this funnel)."""

    def __init__(self, model_path):
        import sentencepiece as spm
        self.sp = spm.SentencePieceProcessor()
        self.sp.load(str(model_path))
        self.pad_token_id = self.sp.pad_id()
        self.bos_token_id = self.sp.bos_id()
        self.eos_token_id = self.sp.eos_id()
        self.vocab_size = self.sp.get_piece_size()

    def encode(self, text, add_special_tokens=True, max_length=None, truncation=False):
        ids = self.sp.encode(text)
        if add_special_tokens and self.bos_token_id >= 0:
            ids = [self.bos_token_id] + ids
        if truncation and max_length is not None and len(ids) > max_length:
            ids = ids[:max_length]
        return ids


class HFWrappedTokenizer:
    """v12 candidates -- wraps a byte_fallback-trained SentencePiece model's
    pieces+scores in a real tokenizers.Tokenizer (Unigram model + explicit
    non-collapsing Metaspace + ByteFallback decoder) instead of native
    SentencePieceProcessor.encode()/decode(). Same validated backend as
    v-tokenizers/v12/training/evaluate_candidate.py::HFWrappedSPBackend."""

    def __init__(self, model_path):
        import sentencepiece as spm
        from tokenizers import Tokenizer, decoders, models, pre_tokenizers

        sp = spm.SentencePieceProcessor(model_file=str(model_path))
        vocab = [(sp.id_to_piece(i), sp.get_score(i)) for i in range(sp.vocab_size())]
        model = models.Unigram(vocab, unk_id=sp.unk_id(), byte_fallback=True)
        self.tok = Tokenizer(model)
        self.tok.pre_tokenizer = pre_tokenizers.Metaspace(replacement="▁", prepend_scheme="always", split=True)
        self.tok.decoder = decoders.Sequence(
            [decoders.ByteFallback(), decoders.Metaspace(replacement="▁", prepend_scheme="always")]
        )
        self.pad_token_id = self.tok.token_to_id("<pad>")
        self.bos_token_id = self.tok.token_to_id("<s>")
        self.eos_token_id = self.tok.token_to_id("</s>")
        self.vocab_size = self.tok.get_vocab_size()

    def encode(self, text, add_special_tokens=True, max_length=None, truncation=False):
        ids = self.tok.encode(text).ids
        if add_special_tokens and self.bos_token_id is not None and self.bos_token_id >= 0:
            ids = [self.bos_token_id] + ids
        if truncation and max_length is not None and len(ids) > max_length:
            ids = ids[:max_length]
        return ids


def load_tokenizer(candidate):
    if candidate == "v11":
        if not CHRIS_EXPERIMENTS_V11_MODEL.exists():
            raise FileNotFoundError(
                f"v11.model not found at {CHRIS_EXPERIMENTS_V11_MODEL} -- this is the real "
                "native SentencePiece file v11 was originally trained against (see "
                "v-tokenizers memory for provenance); it lives in a third repo, not this one "
                "or v-tokenizers."
            )
        return NativeSPTokenizer(CHRIS_EXPERIMENTS_V11_MODEL)
    model_path = V_TOKENIZERS / "v12" / "training" / "candidates" / candidate / f"{candidate}.model"
    if not model_path.exists():
        raise FileNotFoundError(f"candidate model not found at {model_path}")
    return HFWrappedTokenizer(model_path)


class TinyStoriesDataset(IterableDataset):
    def __init__(self, tokenizer, max_seq, max_tokens, seed=42):
        self.tok = tokenizer
        self.max_seq = max_seq
        self.max_tokens = max_tokens
        self.seed = seed

    def __iter__(self):
        from datasets import load_dataset
        ds = load_dataset("roneneldan/TinyStories", split="train", streaming=True, revision=HUB_SHA)
        ds = ds.shuffle(seed=self.seed, buffer_size=10000)
        tokens_seen = 0
        buffer = []
        for sample in ds:
            ids = self.tok.encode(sample["text"], add_special_tokens=True,
                                    max_length=self.max_seq * 2, truncation=True)
            buffer.extend(ids)
            while len(buffer) >= self.max_seq:
                chunk = buffer[:self.max_seq]
                buffer = buffer[self.max_seq:]
                tokens_seen += len(chunk)
                if tokens_seen > self.max_tokens:
                    return
                yield torch.tensor(chunk, dtype=torch.long)


def collate_fn(batch):
    return torch.stack(batch)


def make_model(device, vocab_size, config):
    return TinyModel(
        vocab_size=vocab_size,
        dim=config.dim,
        n_layers=config.n_layers,
        ffn_dim=config.ffn_dim,
        n_heads=config.n_heads,
        n_kv_heads=config.n_kv_heads,
        max_seq=config.max_seq,
    ).to(device)


def train(model, loader, device, max_tokens, vocab_size, compression, lr, label, token_limit_seconds=None):
    """compression: candidate's tokens/byte, used to convert the running
    nats/token loss into bits/byte (BPB) for reporting -- see module
    docstring for the conversion. token_limit_seconds: if set, stop after
    this much wall-clock time regardless of max_tokens (used by the
    timing smoke test, not real training runs)."""
    optimizer = torch.optim.AdamW(
        [p for p in model.parameters() if p.requires_grad],
        lr=lr, weight_decay=0.01,
    )
    trainable = sum(p.numel() for p in model.parameters() if p.requires_grad)
    total = sum(p.numel() for p in model.parameters())
    print(f"\n  Training: {label}")
    print(f"  Trainable: {trainable:,} / {total:,} ({trainable / total:.1%})")
    print(f"  LR: {lr}  Target tokens: {max_tokens:,}")

    model.train()
    t0 = time.time()
    tokens_done = 0
    epoch_loss = 0
    n_batches = 0
    for batch in loader:
        batch = batch.to(device)
        optimizer.zero_grad()
        logits = model(batch)
        loss = F.cross_entropy(
            logits[:, :-1, :].contiguous().view(-1, vocab_size),
            batch[:, 1:].contiguous().view(-1),
            ignore_index=0,
        )
        loss.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
        optimizer.step()
        epoch_loss += loss.item()
        n_batches += 1
        tokens_done += batch.numel()
        elapsed = time.time() - t0
        if n_batches % 50 == 0:
            avg = epoch_loss / n_batches
            bpb = (avg / math.log(2)) * compression
            tps = tokens_done / elapsed
            eta = (max_tokens - tokens_done) / tps if tps > 0 else 0
            print(f"    {tokens_done / 1e6:.2f}M/{max_tokens / 1e6:.1f}M  "
                  f"loss={avg:.4f}  bpb={bpb:.4f}  {tps:.0f} tok/s  ETA={eta / 60:.1f}min")
            sys.stdout.flush()
        if tokens_done >= max_tokens:
            break
        if token_limit_seconds is not None and elapsed >= token_limit_seconds:
            print(f"  [timing smoke test] stopping at {elapsed:.0f}s wall-clock, "
                  f"{tokens_done:,} tokens done")
            break
    avg_loss = epoch_loss / max(n_batches, 1)
    bpb = (avg_loss / math.log(2)) * compression
    elapsed = time.time() - t0
    tps = tokens_done / elapsed if elapsed > 0 else 0
    print(f"  Done: loss={avg_loss:.4f} bpb={bpb:.4f}, {elapsed:.0f}s, "
          f"{tokens_done / 1e6:.2f}M tokens, {tps:.0f} tok/s")
    return {"loss": avg_loss, "bpb": bpb, "elapsed_s": elapsed, "tokens_done": tokens_done, "tokens_per_sec": tps}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--candidate", required=True, choices=list(TINYSTORIES_COMPRESSION.keys()))
    ap.add_argument("--timing-smoke-test-seconds", type=float, default=None,
                     help="if set, run phase1 only for this many seconds and report throughput, don't do a full run or save weights")
    args = ap.parse_args()

    device = torch.device("mps" if torch.backends.mps.is_available() else "cpu")
    compression = TINYSTORIES_COMPRESSION[args.candidate]
    phase1_tokens = round(V11_REFERENCE_BYTES_PHASE1 * compression)
    phase3_tokens = round(V11_REFERENCE_BYTES_PHASE3 * compression)

    print("=" * 70)
    print(f"  TOK-2: TinyModel + {args.candidate}")
    print("=" * 70)
    print(f"  Device: {device}")
    print(f"  Reference bytes (from v11's real original training): "
          f"phase1={V11_REFERENCE_BYTES_PHASE1/1e6:.1f}M phase3={V11_REFERENCE_BYTES_PHASE3/1e6:.1f}M")
    print(f"  This candidate's compression: {compression:.4f} tok/byte")
    print(f"  -> byte-matched token budget: phase1={phase1_tokens:,} phase3={phase3_tokens:,}")

    config = load_config(V11_ARTIFACT_DIR)
    tok = load_tokenizer(args.candidate)
    print(f"  vocab_size = {tok.vocab_size}")

    torch.manual_seed(SEED)
    model = make_model(device, tok.vocab_size, config)
    n_params = sum(p.numel() for p in model.parameters())
    print(f"  Parameters: {n_params:,}")

    dataset1 = TinyStoriesDataset(tok, config.max_seq, phase1_tokens, seed=SEED)
    loader1 = DataLoader(dataset1, batch_size=BATCH_SIZE, collate_fn=collate_fn)
    result1 = train(model, loader1, device, phase1_tokens, tok.vocab_size, compression, LR,
                     label=f"Phase1 ({args.candidate})",
                     token_limit_seconds=args.timing_smoke_test_seconds)

    if args.timing_smoke_test_seconds is not None:
        print(json.dumps({"candidate": args.candidate, "smoke_test": True, **result1}, indent=2))
        return

    out_dir = V_TOKENIZERS / "v12" / "training" / "tok2_runs" / args.candidate
    out_dir.mkdir(parents=True, exist_ok=True)
    torch.save(model.state_dict(), out_dir / "model_full.pt")

    results = {
        "candidate": args.candidate,
        "phase1": result1,
        "vocab_size": tok.vocab_size,
        "n_params": n_params,
        "phase1_tokens_target": phase1_tokens,
        "phase3_tokens_target": phase3_tokens,
        "reference_bytes_phase1": V11_REFERENCE_BYTES_PHASE1,
        "compression_used": compression,
        "arch": config.to_dict(),
    }
    with open(out_dir / "training_results.json", "w") as f:
        json.dump(results, f, indent=2)
    print(f"\nsaved {out_dir}")


if __name__ == "__main__":
    main()
