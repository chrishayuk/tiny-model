#!/usr/bin/env python3
"""Per-document bootstrap on the v11-replication vs unigram_16000 held-out gap.

Why this exists: the aggregate held-out BPB numbers (v11_pinned_replication_full
0.6846 vs unigram_sp_16000 0.7058, diff=0.0212) are means over ~2150-2174
fixed-256-token CHUNKS built by concatenating all 2000 held-out stories and
re-slicing -- chunk boundaries don't respect story boundaries, so that
aggregate can't say whether the gap is a consistent per-document effect or
driven by a handful of documents. This script instead evaluates each held-out
STORY independently (batch=1, its own natural length, no cross-story mixing)
and paired-bootstraps the per-story BPB difference across the held-out set --
a cheap, real answer to "is this gap robust or is it a small-subset artifact",
without requiring new training runs or multiple seeds.

A story is dropped from this analysis if either tokenizer needs more than
MAX_SEQ tokens for it (can't fit in this model's context) -- kept the SAME
retained-story set for both models so the paired comparison stays apples-to-
apples. This is a different, complementary check to the chunk-level aggregate,
not a replacement for it.

Run (from tiny-model repo root):
  uv run --project model/v11-train python model/v11-train/bootstrap_held_out_gap.py
"""

from __future__ import annotations

import json
import math
from pathlib import Path

import torch
import torch.nn.functional as F

from tiny_model_v11 import load_config
from eval_held_out import load_held_out_texts, CHECKPOINTS
from train_tok2 import V11_ARTIFACT_DIR, V_TOKENIZERS, load_tokenizer, make_model

MAX_SEQ = 256
N_BOOTSTRAP = 10000
CI = 0.90  # 90% CI, matching this funnel's TEG convention elsewhere

A_NAME = "v11_pinned_replication_full"
B_NAME = "unigram_sp_16000_v2_tcoreseed_bytefallback"


@torch.no_grad()
def per_story_bpb(model, tok, texts, device, vocab_size):
    """Returns (kept_mask, bpb_per_story) -- bpb_per_story is None for stories
    dropped (too long for MAX_SEQ or <2 tokens)."""
    out = []
    for t in texts:
        ids = tok.encode(t, add_special_tokens=True)
        if len(ids) < 2 or len(ids) > MAX_SEQ:
            out.append(None)
            continue
        x = torch.tensor([ids], dtype=torch.long, device=device)
        logits = model(x)
        loss = F.cross_entropy(
            logits[:, :-1, :].contiguous().view(-1, vocab_size),
            x[:, 1:].contiguous().view(-1),
        )
        n_bytes = len(t.encode("utf-8"))
        compression = len(ids) / n_bytes
        bpb = (loss.item() / math.log(2)) * compression
        out.append(bpb)
    return out


def main():
    device = torch.device("mps" if torch.backends.mps.is_available() else "cpu")
    config = load_config(V11_ARTIFACT_DIR)

    print("Loading held-out texts (same verified-clean set eval_held_out.py uses)...")
    texts = load_held_out_texts()
    print(f"  {len(texts)} stories\n")

    results = {}
    for name in (A_NAME, B_NAME):
        spec = CHECKPOINTS[name]
        print(f"Evaluating per-story: {name}")
        tok = load_tokenizer(spec["candidate"])
        model = make_model(device, tok.vocab_size, config)
        state = torch.load(spec["path"], map_location=device)
        model.load_state_dict(state)
        model.eval()
        results[name] = per_story_bpb(model, tok, texts, device, tok.vocab_size)
        n_kept = sum(1 for v in results[name] if v is not None)
        print(f"  {n_kept}/{len(texts)} stories fit within MAX_SEQ={MAX_SEQ} for this tokenizer\n")

    # Keep only stories both models could score.
    paired = [
        (a, b) for a, b in zip(results[A_NAME], results[B_NAME])
        if a is not None and b is not None
    ]
    n_eff = len(paired)
    print(f"Paired, both-fit stories: {n_eff}/{len(texts)}")

    a_vals = [p[0] for p in paired]
    b_vals = [p[1] for p in paired]
    diffs = [b - a for a, b in paired]  # positive => A (v11 replication) better (lower bpb)

    mean_a = sum(a_vals) / n_eff
    mean_b = sum(b_vals) / n_eff
    mean_diff = sum(diffs) / n_eff
    n_a_wins = sum(1 for d in diffs if d > 0)
    n_b_wins = sum(1 for d in diffs if d < 0)

    print(f"\nPer-story mean BPB: {A_NAME}={mean_a:.4f}  {B_NAME}={mean_b:.4f}  diff={mean_diff:+.4f}")
    print(f"Per-story win counts: {A_NAME} lower-bpb on {n_a_wins}/{n_eff} stories "
          f"({n_a_wins/n_eff:.1%}), {B_NAME} lower-bpb on {n_b_wins}/{n_eff} "
          f"({n_b_wins/n_eff:.1%}), tied on {n_eff - n_a_wins - n_b_wins}")

    print(f"\nBootstrapping ({N_BOOTSTRAP} resamples, paired, with replacement)...")
    import random
    rng = random.Random(20260720)
    boot_means = []
    idx_range = range(n_eff)
    for _ in range(N_BOOTSTRAP):
        sample_idx = [rng.randrange(n_eff) for _ in idx_range]
        s = sum(diffs[i] for i in sample_idx) / n_eff
        boot_means.append(s)
    boot_means.sort()
    lo_pct = (1 - CI) / 2
    hi_pct = 1 - lo_pct
    lo = boot_means[int(lo_pct * N_BOOTSTRAP)]
    hi = boot_means[int(hi_pct * N_BOOTSTRAP)]
    frac_gt_zero = sum(1 for d in boot_means if d > 0) / N_BOOTSTRAP

    print(f"Bootstrap mean diff ({B_NAME} - {A_NAME}): {mean_diff:+.4f}")
    print(f"{CI:.0%} CI: [{lo:+.4f}, {hi:+.4f}]")
    print(f"Fraction of bootstrap resamples with diff > 0 (v11 replication better): {frac_gt_zero:.1%}")

    out = {
        "a_name": A_NAME,
        "b_name": B_NAME,
        "n_held_out_stories": len(texts),
        "n_paired_stories": n_eff,
        "mean_bpb_a": mean_a,
        "mean_bpb_b": mean_b,
        "mean_diff_b_minus_a": mean_diff,
        "per_story_a_wins": n_a_wins,
        "per_story_b_wins": n_b_wins,
        "per_story_ties": n_eff - n_a_wins - n_b_wins,
        "bootstrap_n": N_BOOTSTRAP,
        "bootstrap_ci_level": CI,
        "bootstrap_ci_low": lo,
        "bootstrap_ci_high": hi,
        "bootstrap_fraction_diff_gt_zero": frac_gt_zero,
        "note": "per-story (not per-chunk) evaluation, batch=1, natural story length capped "
                "at MAX_SEQ; stories requiring >MAX_SEQ tokens under either tokenizer dropped "
                "from BOTH models to keep the paired comparison apples-to-apples. Complementary "
                "to eval_held_out.py's chunk-level aggregate, not a replacement for it -- "
                "answers whether the aggregate gap is a robust per-document effect or driven "
                "by a small subset, not whether it would replicate under a different training seed.",
    }
    out_path = V_TOKENIZERS / "v12" / "training" / "tok2_runs" / "bootstrap_held_out_gap.json"
    with open(out_path, "w") as f:
        json.dump(out, f, indent=2)
    print(f"\nsaved {out_path}")


if __name__ == "__main__":
    main()
