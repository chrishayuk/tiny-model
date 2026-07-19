#!/usr/bin/env python3
"""Train TinyModel v11 on TinyStories.

Two phases:
  Phase 2: full training from scratch on 16M TinyStories tokens
           (arch defaults from tiny_model_v11; lr=3e-4)
  Phase 3: freeze FFN + norms + embed; retrain attention on 8M tokens
           at lr=1.5e-4 (the "compiled" checkpoint)

Writes into `<repo>/model/v11/artifacts/`:
    model_full.pt        — after Phase 2
    model_compiled.pt    — after Phase 3
    training_results.json

Dependencies:
  - tiny_model_v11 (sibling v11-core package)
  - sentencepiece, torch, datasets
  - ../../../v-tokenizers/v11/artifacts/v11.model (sibling repo; NOTE this
    exact file has never actually lived in either repo, see V11_TOKENIZER
    comment below for the real location)

Usage (from tiny-model repo root):
  uv run --project model/v11-train python model/v11-train/train_tinystories.py
"""

from __future__ import annotations

import json
import math
import os
import sys
import time
from pathlib import Path

import sentencepiece as spm
import torch
import torch.nn.functional as F
from torch.utils.data import DataLoader, IterableDataset

from tiny_model_v11 import TinyModel, load_config

# ── Paths ─────────────────────────────────────────────────────────────
REPO = Path(__file__).resolve().parents[2]  # tiny-model/
V11_ARTIFACT_DIR = REPO / "model" / "v11"
# v11 moved 2026-07-19 into the sibling v-tokenizers repo. NOTE: this path
# was already stale before the move -- no v11.model (native SentencePiece
# format) has ever actually lived under tokenizer/v11/artifacts/ in this
# repo (only tokenizer.json/v11.vocab.bin/v11.vocab.json, the HF-exported
# forms). The real v11.model lives in a third repo entirely:
# chris-experiments/compilation/15_v11_model/v11_tokenizer/v11.model
# (sha256 4ffbfc87...c1dc8e6) -- pass --tokenizer explicitly pointing
# there if this script needs to actually run.
V11_TOKENIZER = REPO.parent / "v-tokenizers" / "v11" / "artifacts" / "v11.model"
OUTPUT_DIR = V11_ARTIFACT_DIR / "artifacts"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# ── Training config ───────────────────────────────────────────────────
CONFIG = load_config(V11_ARTIFACT_DIR)
BATCH_SIZE = 4
LR = 3e-4
SEED = 42
TOKENS_PHASE1 = 16_000_000
TOKENS_PHASE3 = 8_000_000


class V11Tokenizer:
    def __init__(self, model_path):
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

    def decode(self, ids, skip_special_tokens=True):
        if skip_special_tokens:
            skip = {self.pad_token_id, self.bos_token_id, self.eos_token_id}
            ids = [i for i in ids if i not in skip]
        return self.sp.decode(ids)


class TinyStoriesDataset(IterableDataset):
    def __init__(self, tokenizer, max_seq, max_tokens, seed=42):
        self.tok = tokenizer
        self.max_seq = max_seq
        self.max_tokens = max_tokens
        self.seed = seed

    def __iter__(self):
        from datasets import load_dataset
        ds = load_dataset("roneneldan/TinyStories", split="train", streaming=True)
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


def make_model(device, vocab_size):
    return TinyModel(
        vocab_size=vocab_size,
        dim=CONFIG.dim,
        n_layers=CONFIG.n_layers,
        ffn_dim=CONFIG.ffn_dim,
        n_heads=CONFIG.n_heads,
        n_kv_heads=CONFIG.n_kv_heads,
        max_seq=CONFIG.max_seq,
    ).to(device)


def train(model, loader, device, max_tokens, vocab_size, lr=LR, label=""):
    optimizer = torch.optim.AdamW(
        [p for p in model.parameters() if p.requires_grad],
        lr=lr, weight_decay=0.01,
    )
    trainable = sum(p.numel() for p in model.parameters() if p.requires_grad)
    total = sum(p.numel() for p in model.parameters())
    print(f"\n  Training: {label}")
    print(f"  Trainable: {trainable:,} / {total:,} ({trainable / total:.1%})")
    print(f"  LR: {lr}")

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
        if n_batches % 200 == 0:
            avg = epoch_loss / n_batches
            elapsed = time.time() - t0
            tps = tokens_done / elapsed
            eta = (max_tokens - tokens_done) / tps if tps > 0 else 0
            print(f"    {tokens_done / 1e6:.1f}M/{max_tokens / 1e6:.0f}M  "
                  f"loss={avg:.4f}  {tps:.0f} tok/s  ETA={eta / 60:.0f}min")
            sys.stdout.flush()
        if tokens_done >= max_tokens:
            break
    avg_loss = epoch_loss / max(n_batches, 1)
    print(f"  Done: loss={avg_loss:.4f}, {time.time() - t0:.0f}s, "
          f"{tokens_done / 1e6:.1f}M tokens")
    return avg_loss


def compile_ffn(trained_model, device, vocab_size):
    print("\n  Compiling FFN (fresh attention + copied FFN/embed/norms)…")
    torch.manual_seed(SEED + 100)
    compiled = make_model(device, vocab_size)
    with torch.no_grad():
        for li in range(CONFIG.n_layers):
            compiled.layers[li].ffn.gate.weight.data.copy_(
                trained_model.layers[li].ffn.gate.weight.data)
            compiled.layers[li].ffn.up.weight.data.copy_(
                trained_model.layers[li].ffn.up.weight.data)
            compiled.layers[li].ffn.down.weight.data.copy_(
                trained_model.layers[li].ffn.down.weight.data)
            compiled.layers[li].attn_norm.weight.data.copy_(
                trained_model.layers[li].attn_norm.weight.data)
            compiled.layers[li].ffn_norm.weight.data.copy_(
                trained_model.layers[li].ffn_norm.weight.data)
        compiled.embed.weight.data.copy_(trained_model.embed.weight.data)
        compiled.norm.weight.data.copy_(trained_model.norm.weight.data)
    return compiled


def freeze_ffn(model):
    for layer in model.layers:
        for p in layer.ffn.parameters():
            p.requires_grad = False
        for p in layer.attn_norm.parameters():
            p.requires_grad = False
        for p in layer.ffn_norm.parameters():
            p.requires_grad = False
    for p in model.embed.parameters():
        p.requires_grad = False
    for p in model.norm.parameters():
        p.requires_grad = False


def main():
    print("=" * 70)
    print("  TinyModel v11: TinyStories + v11 SentencePiece (71K)")
    print("=" * 70)

    device = torch.device("mps" if torch.backends.mps.is_available() else "cpu")
    print(f"\n  Device: {device}")
    print(f"  Output: {OUTPUT_DIR}")
    print(f"  Config: dim={CONFIG.dim} L={CONFIG.n_layers} "
          f"ffn={CONFIG.ffn_dim} heads={CONFIG.n_heads} kv={CONFIG.n_kv_heads}")

    print(f"\n[tokenizer] loading v11 SP from {V11_TOKENIZER}")
    tok = V11Tokenizer(V11_TOKENIZER)
    print(f"  vocab_size = {tok.vocab_size}")

    print(f"\n{'=' * 70}")
    print(f"  PHASE 2: full training ({TOKENS_PHASE1 / 1e6:.0f}M tokens)")
    print(f"{'=' * 70}")
    torch.manual_seed(SEED)
    model = make_model(device, tok.vocab_size)
    n_params = sum(p.numel() for p in model.parameters())
    print(f"  Parameters: {n_params:,}")

    dataset1 = TinyStoriesDataset(tok, CONFIG.max_seq, TOKENS_PHASE1, seed=SEED)
    loader1 = DataLoader(dataset1, batch_size=BATCH_SIZE, collate_fn=collate_fn)
    loss1 = train(model, loader1, device, TOKENS_PHASE1, tok.vocab_size, label="Full v11")

    torch.save(model.state_dict(), OUTPUT_DIR / "model_full.pt")
    print(f"  saved {OUTPUT_DIR / 'model_full.pt'}")

    print(f"\n{'=' * 70}")
    print(f"  PHASE 3: frozen FFN + retrain attention "
          f"({TOKENS_PHASE3 / 1e6:.0f}M tokens @ lr={LR * 0.5})")
    print(f"{'=' * 70}")
    compiled = compile_ffn(model, device, tok.vocab_size)
    freeze_ffn(compiled)
    dataset3 = TinyStoriesDataset(tok, CONFIG.max_seq, TOKENS_PHASE3, seed=SEED + 1)
    loader3 = DataLoader(dataset3, batch_size=BATCH_SIZE, collate_fn=collate_fn)
    loss3 = train(compiled, loader3, device, TOKENS_PHASE3, tok.vocab_size,
                   lr=LR * 0.5, label="Attention-only on frozen FFN")

    torch.save(compiled.state_dict(), OUTPUT_DIR / "model_compiled.pt")
    print(f"  saved {OUTPUT_DIR / 'model_compiled.pt'}")

    results = {
        "loss_full": loss1,
        "loss_compiled": loss3,
        "tokenizer": str(V11_TOKENIZER),
        "vocab_size": tok.vocab_size,
        "n_params": n_params,
        "tokens_phase1": TOKENS_PHASE1,
        "tokens_phase3": TOKENS_PHASE3,
        "arch": CONFIG.to_dict(),
    }
    with open(OUTPUT_DIR / "training_results.json", "w") as f:
        json.dump(results, f, indent=2)

    print(f"\n{'=' * 70}\n  SUMMARY\n{'=' * 70}")
    print(f"  Phase 2 full:       loss={loss1:.4f}")
    print(f"  Phase 3 frozen FFN: loss={loss3:.4f}")
    print(f"  Δ (improvement):    {loss1 - loss3:+.4f}")


if __name__ == "__main__":
    main()
