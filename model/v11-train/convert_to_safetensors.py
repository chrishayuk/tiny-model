#!/usr/bin/env python3
"""Convert a TinyModel .pt checkpoint to HF-safetensors layout.

Produces a directory consumable by `larql extract-index`:

    <output>/
      model.safetensors     # native TinyModel keys (no remap)
      config.json           # model_type="tinymodel" + arch fields
      tokenizer.json        # copied from ../../../tokenizer/v11/artifacts/

Native key layout is matched directly by `TinyModelArch` in
`larql-models/src/architectures/tinymodel.rs` — no tensor renaming.

Usage:
    uv run --project model/v11-train python \\
      model/v11-train/convert_to_safetensors.py \\
      --artifact-dir model/v11 \\
      --checkpoint model_compiled.pt \\
      --output   model/v11/safetensors
"""

from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

import torch
from safetensors.torch import save_file

from tiny_model_v11 import load_config


def strip_buffers(state: dict) -> dict:
    """Drop non-parameter buffers (rope_freqs) and tied weights
    (lm_head aliases embed). Safetensors refuses to serialize memory-
    shared tensors; the HF loader reconstructs lm_head from embed
    when `tie_word_embeddings: true`."""
    dropped = {"lm_head.weight"}
    return {
        k: v for k, v in state.items()
        if not k.endswith("rope_freqs") and k not in dropped
    }


def hf_config(arch, extras: dict | None = None) -> dict:
    """HF-style config.json that detect_from_json parses into ModelConfig.

    Fields align with larql-models/src/detect.rs::parse_model_config:
      model_type, hidden_size, num_hidden_layers, intermediate_size,
      num_attention_heads, num_key_value_heads, head_dim, vocab_size,
      max_position_embeddings, rope_theta.
    """
    cfg = {
        "model_type": "tinymodel",
        "architectures": ["TinyModel"],
        "hidden_size": arch.dim,
        "num_hidden_layers": arch.n_layers,
        "intermediate_size": arch.ffn_dim,
        "num_attention_heads": arch.n_heads,
        "num_key_value_heads": arch.n_kv_heads,
        "head_dim": arch.dim // arch.n_heads,
        "vocab_size": arch.vocab_size,
        "max_position_embeddings": arch.max_seq,
        "rope_theta": 10000.0,
        "tie_word_embeddings": True,
        "torch_dtype": "float32",
    }
    if extras:
        cfg.update(extras)
    return cfg


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--artifact-dir", type=Path, required=True,
                    help="TinyModel artefact dir (contains config.json + artifacts/)")
    ap.add_argument("--checkpoint", default="model_compiled.pt",
                    help="Filename under artifact-dir/artifacts/ to convert")
    ap.add_argument("--output", type=Path, required=True,
                    help="Destination HF-safetensors directory")
    ap.add_argument("--tokenizer",
                    default=None,
                    help="Path to tokenizer.json (default: <repo>/tokenizer/v11/artifacts/tokenizer.json)")
    args = ap.parse_args()

    artifact_dir = args.artifact_dir.resolve()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)

    config = load_config(artifact_dir)
    ckpt_path = artifact_dir / "artifacts" / args.checkpoint
    print(f"[load] {ckpt_path}")
    state = torch.load(str(ckpt_path), map_location="cpu", weights_only=True)
    state = strip_buffers(state)
    state = {k: v.contiguous().cpu() for k, v in state.items()}
    print(f"       {len(state)} tensors, "
          f"{sum(v.numel() for v in state.values()):,} params total")

    # Sample keys (for sanity): should start "embed.weight", "layers.0.attn.q_proj.weight", …
    sample = list(state.keys())[:4]
    print(f"[keys] e.g. {sample}")

    safetensors_path = output / "model.safetensors"
    print(f"[save] {safetensors_path}")
    save_file(state, str(safetensors_path))

    cfg = hf_config(config, extras={"tinymodel_version": config.version})
    config_path = output / "config.json"
    print(f"[save] {config_path}")
    config_path.write_text(json.dumps(cfg, indent=2) + "\n")

    # Tokenizer
    if args.tokenizer is not None:
        tok_src = Path(args.tokenizer)
    else:
        repo_root = artifact_dir.parents[1]  # <tiny-model>/
        tok_src = repo_root / "tokenizer" / "v11" / "artifacts" / "tokenizer.json"
    if tok_src.exists():
        tok_dst = output / "tokenizer.json"
        print(f"[copy] {tok_src} → {tok_dst}")
        shutil.copy(tok_src, tok_dst)
    else:
        print(f"[warn] tokenizer.json not found at {tok_src}; "
              "extract-index will require one alongside the model")

    print(f"\n[done] HF-safetensors layout at: {output}")
    print("Next:")
    print(f"  larql extract-index {output} --output {output.parent / 'vindex'} --level all")


if __name__ == "__main__":
    main()
