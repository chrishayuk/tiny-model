# v10c Tokenizer Spec

A 32K SentencePiece BPE tokenizer trained on TinyStories plus a small
world-facts supplement. Built for the v10c experiment in
`larql/experiments/06_backprop_insert/` after v10a's approach of clamping
Gemma's 256K vocab via `min(id, 31999)` silently aliased rare tokens
(Cairo, Athens, Vienna, Yen, Pound, …) to id 31999, making fact
compilation impossible for any out-of-clamp token.

Source of truth: `larql/experiments/06_backprop_insert/experiment_v10c_tinystories.py`
(`train_tokenizer`, `build_supplement_corpus`, `SPTokenizer`).

Artifacts (already trained):
- `larql/experiments/06_backprop_insert/results_v10c_tinystories/v10c_tokenizer.model` (767 KB)
- `larql/experiments/06_backprop_insert/results_v10c_tinystories/v10c_tokenizer.vocab` (486 KB, 32000 lines)

## Parameters

| Field | Value |
|---|---|
| Library | `sentencepiece` (`spm.SentencePieceTrainer`) |
| Model type | `bpe` |
| Vocab size | `32000` |
| Character coverage | `0.9995` |
| Max sentence length | `4096` |
| `pad_id` | `0` |
| `unk_id` | `1` |
| `bos_id` | `2` |
| `eos_id` | `3` |
| Threads | `os.cpu_count()` |

## Training corpus

Two concatenated sources written to a single temp file, one document
per line:

1. **TinyStories.** First 50,000 documents from
   `roneneldan/TinyStories` (HF `datasets`, streaming, `split="train"`),
   roughly ~25 MB of text. Provides base English coverage.
2. **World-facts supplement** (`build_supplement_corpus`). ~5 MB of
   templated sentences produced by iterating 20 times over fixed lists
   and emitting patterns such as:
   - `The capital of {country} is {capital}.`
   - `{capital} is the capital city of {country}.`
   - `People in {country} live in cities like {capital}.`
   - `In {country} the language is {language}.`
   - `Most people who live in {country} speak {language}.`
   - `{language} is spoken throughout {country}.`
   - `The currency of {country} is the {currency}.`
   - `When visiting {country}, you pay with money called the {currency}.`
   - `The dominant colour is {colour}.`
   - `Looking at the picture, the dominant colour appears to be {colour}.`

   The fixed lists live in `experiment_v10c_tinystories.py`:
   `COUNTRIES` (52), `CAPITALS` (49), `LANGUAGES` (30),
   `CURRENCIES` (18), `COLOURS` (13). Country↔capital,
   country↔language, and country↔currency rows are paired via `zip`,
   so only the prefix of `COUNTRIES` that matches each shorter list
   participates in those templates.

The supplement is not a knowledge base — it exists purely to force
BPE to allocate single merges for each entity name. Without it,
names like `Cairo` or `Yen` would be split into sub-pieces and could
not be taught as atomic facts downstream.

## Build procedure

```python
import os, tempfile, sentencepiece as spm
from datasets import load_dataset

ds = load_dataset("roneneldan/TinyStories", split="train", streaming=True)
sample_texts = []
for i, sample in enumerate(ds):
    sample_texts.append(sample["text"])
    if i >= 50_000:
        break

supplement = build_supplement_corpus()  # from experiment_v10c_tinystories.py

with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False) as f:
    for txt in sample_texts:
        f.write(txt + "\n")
    f.write(supplement)
    corpus_path = f.name

spm.SentencePieceTrainer.train(
    input=corpus_path,
    model_prefix="v10c_tokenizer",
    vocab_size=32000,
    character_coverage=0.9995,
    model_type="bpe",
    pad_id=0, unk_id=1, bos_id=2, eos_id=3,
    max_sentence_length=4096,
    num_threads=os.cpu_count(),
)
os.unlink(corpus_path)
```

Outputs: `v10c_tokenizer.model` and `v10c_tokenizer.vocab`.

The builder is idempotent: if the `.model` file already exists at the
target path, `train_tokenizer` returns without retraining.

## Coverage check

After training, the build verifies that leading-space variants of
target entity names encode to a single id:

```python
sp = spm.SentencePieceProcessor(); sp.load(path)
for w in [" Paris", " Madrid", " Cairo", " Athens", " Vienna",
          " Tokyo", " Yen", " Euro", " Pound", " French", " Spanish"]:
    assert len(sp.encode(w)) == 1, w
```

A `✗` on any of these means the supplement was too small or the
vocab too tight for that token; bump supplement repetitions before
raising `vocab_size`.

## Runtime wrapper

`SPTokenizer` in `experiment_v10c_tinystories.py` is a minimal
HF-shaped adapter:

- `__init__(model_path)` loads the `.model`, sets
  `pad_token_id=0`, `bos_token_id=2`, `eos_token_id=3`.
- `encode(text, add_special_tokens=True, max_length=None, truncation=False)`
  returns `sp.encode(text)`, optionally prepending BOS, optionally
  truncating to `max_length`. Note: EOS is **not** appended.
- `decode(ids, skip_special_tokens=True)` strips `{0, 2, 3}` before
  `sp.decode`.

No attention mask, no padding helpers, no batch encode — callers
handle those.

## Downstream contract

Any model trained against this tokenizer must use `vocab_size=32000`
and the id assignments above (`pad=0`, `unk=1`, `bos=2`, `eos=3`). The
v10c experiment pairs it with a TinyGemma at `DIM=512`, `N_LAYERS=20`,
`N_HEADS=8`, `N_KV_HEADS=4`, `FFN_DIM=2048`, `MAX_SEQ=256`.
