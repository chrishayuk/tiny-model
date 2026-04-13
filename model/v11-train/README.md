# v11-train

Training entrypoints for TinyModel **v11**. Outputs land in
`../v11/artifacts/`.

## Scripts

- `train_tinystories.py` — Phase 2 full training on TinyStories +
  Phase 3 frozen-FFN attention retrain. Writes `model_full.pt`,
  `model_compiled.pt`, `training_results.json`.

## Usage

```
uv sync --project model/v11-train
uv run --project model/v11-train python model/v11-train/train_tinystories.py
```

## Vindex extraction

Vindex extraction currently lives in the larql experiments repo
(`larql/experiments/15_v11_model/vindex_extract_v11.py`) because it
depends on the `compile_facts` primitive. It writes the extracted
vindex into `tiny-model/model/v11/vindex/`. When `compile_facts` moves
into `larql-python` bindings, the extractor will relocate to
`v11-train/extract_vindex.py`.
