# tiny-model-v11 (core)

TinyModel v11 architecture. Decoder-only transformer, Gemma-shaped:

- RMSNorm
- RoPE
- Grouped-query attention (GQA)
- Gated FFN (SiLU(gate) * up → down)
- Tied embeddings

This package contains the architecture **only**. Weights live under
`../v11/artifacts/`, training scripts under `../v11-train/`.

## Usage

```python
from tiny_model_v11 import TinyModel, load_from_artifacts

# Construct by hand
model = TinyModel(vocab_size=71261, dim=512, n_layers=20,
                  ffn_dim=2048, n_heads=8, n_kv_heads=4, max_seq=256)

# Or load weights + config from a v11 artefact dir
model = load_from_artifacts("/path/to/tiny-model/model/v11")
```

## Versioning

- `v11`, `v11a`, `v11b`, … share this core (same arch, different weights).
- A new core (`v12-core`) lands only when the architecture actually changes.
