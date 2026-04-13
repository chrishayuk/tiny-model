# TinyModel v11 artefacts

Per-weights artefacts for TinyModel **v11**. Architecture code lives in
sibling `../v11-core/` (Python package `tiny_model_v11`); training
scripts in `../v11-train/`.

## Contents

```
v11/
  config.json                     # authoritative arch + training config
  artifacts/
    model_compiled.pt             # Phase 3: frozen-FFN, attention retrained
    model_full.pt                 # Phase 2: end of full training
    train_mask.pt                 # tokenizer id mask used during training
    training_results.json         # loss summary
  vindex/                         # extracted vindex (produced by v11-train/extract_vindex.py)
```

## Loading

```python
from tiny_model_v11 import load_from_artifacts

model, config = load_from_artifacts("/path/to/tiny-model/model/v11")
# model is eval()'d and on MPS/CUDA/CPU
```

## Lineage

- Architecture: TinyModel (v11-core) — dim=512, 20L, 8H, 4KV, ffn=2048.
- Tokenizer: v11 SentencePiece, 71,261 vocab (WordNet + Wikidata + 77
  tree-sitter grammars + language_extras). Lives in `../../tokenizer/v11/`.
- Corpus: TinyStories, 16M tokens Phase 2 + 8M Phase 3.
- Variants: `v11a`, `v11b`, … land as siblings (same core, different
  weights).
