# v11 — Knowledge-First Tokenizer

A pure-Rust tokenizer whose vocabulary is **assembled from the structure of
knowledge** — tree-sitter AST grammars for ~77 programming languages,
WordNet lemmas ranked by wordfreq Zipf, Wikidata proper nouns, hand-curated
morphemes, Greek letters, math symbols, and function words — not discovered
from BPE merges on a corpus.

Every token is a potential compilation target. Priority concepts (language
keywords, type names, scientific terms, acronyms, Greek letters) are
guaranteed to be a single piece, so compilation into a knowledge graph's
edges costs one edge per target instead of two to five.

See [SPEC.md](SPEC.md) for the full design document.

## Why v11

| tokenizer      | vocab     | single-token hits | pct  |
|----------------|-----------|-------------------|------|
| **v11**        | **~71K**  | **81/81**         | **100%** |
| gemma-3-4b-pt  | 262K      | 76/81             | 94%  |
| llama-3.2-1b   | 128K      | 74/81             | 91%  |
| tiktoken cl100k| 100K      | 74/81             | 91%  |
| tiktoken o200k | 200K      | 74/81             | 91%  |
| mistral-7b     | 32K       | 58/81             | 72%  |
| v10c 32K       | 32K       | 27/81             | 33%  |

v11 is the only tokenizer hitting 100% on the priority target suite
(Python + Rust + JS/TS + C + Java + Go keywords, technical acronyms, Greek,
scientific terms). Gemma at 10× the vocab size misses five items, notably
Rust stdlib types (`Vec`, `Option`, `Result`).

## Runtime characteristics

- **Pure Rust**, no C++ FFI. Drop-in from Cargo.
- **Byte-identical** to `transformers.AutoTokenizer.from_pretrained("v11/artifacts")`
  — the native encoder is a faithful port of HuggingFace's Unigram
  `encode_optimized` (trie-based Viterbi with shortest-first prefix
  iteration and strict `>` tiebreak).
- **~3M tokens/sec** encode throughput on a single Apple M3 thread (release
  build).
- **~28M tokens/sec** decode.
- **Metaspace pre-tokenization** matching HF `Metaspace(prepend_scheme=always, split=true)`.
- **Unknown chars → `<unk>` with `min_score - 10` penalty** (no byte fallback
  at runtime — the `<0xNN>` pieces are in-vocab but never matched in
  practice, kept for SentencePiece compatibility).

## Crate layout

| Crate        | Role                                              | Binary       |
|--------------|---------------------------------------------------|--------------|
| `v11-core`   | Shared types + trie + Viterbi encoder             | lib          |
| `v11-builder`| Assembles vocab, writes binary + HF artefacts     | `v11-build`  |
| `v11-cli`    | Encode/decode from the command line               | `v11`        |
| `v11-bench`  | Encode/decode throughput benchmark                | `v11-bench`  |
| `v11-demos`  | Sample `demo-basic` / `demo-code` binaries        | multiple     |
| `v11-python` | PyO3 bindings for `import v11` in Python          | cdylib       |

## Build the tokenizer from scratch

Regenerates everything under `v11/artifacts/` — vocab binary, `tokenizer.json`,
`tokenizer_config.json`, `special_tokens_map.json`, model card.

```bash
# 1. (only when nltk / wordfreq versions change)
cd v11 && python preprocess_wordnet.py

# 2. build the Rust artefacts
cd ..
cargo run -p v11-builder --release -- \
    --config v11/config.json \
    --output v11/artifacts/

# 3. verify
cargo test --workspace
cargo run -p v11-demos --release --bin demo-code
cargo run -p v11-bench --release
```

## CLI

```bash
# Encode text
cargo run -p v11-cli --release -- encode --text "def fibonacci(n):"

# Encode with piece strings
cargo run -p v11-cli --release -- encode --show-pieces --text "The capital of France is Paris"

# Decode ids
cargo run -p v11-cli --release -- decode --ids "1680,66356,728,34311,276,321,286,322,317"

# Info about the loaded tokenizer
cargo run -p v11-cli --release -- info
```

The CLI auto-discovers `v11/artifacts/v11.vocab.bin`. Override with
`--model <path>`.

## Python bindings

```bash
cd v11-python
maturin build --release
pip install target/wheels/v11_tokenizer-*.whl
```

```python
import v11
tok = v11.Tokenizer.from_file("v11/artifacts/v11.vocab.bin")
ids = tok.encode("def fibonacci(n):")
text = tok.decode(ids)
```

See [v11-python/README.md](../v11-python/README.md) for the full API.

## HuggingFace compatibility

The `artifacts/` directory is a drop-in HF tokenizer:

```python
from transformers import AutoTokenizer
tok = AutoTokenizer.from_pretrained("./v11/artifacts")

# or
from tokenizers import Tokenizer
tok = Tokenizer.from_file("./v11/artifacts/tokenizer.json")
```

All three loading paths — native Rust, HF `tokenizers`, HF `transformers` —
produce **byte-identical** ids. See [examples/](examples/) for runnable
demos and [examples/compare_all.py](examples/compare_all.py) for the
cross-check.

## Testing & linting

The workspace is `clippy`- and `rustfmt`-clean with `-D warnings`:

```bash
cargo fmt --check
cargo clippy --all-targets -- -D warnings
cargo test --workspace
```

`v11-core` ships 14 unit tests covering the Viterbi edge cases (ties,
unknowns, Unicode, empty input, multi-whitespace, capacity, special-token
stripping, decode roundtrip). Run with:

```bash
cargo test -p v11-core
```

## Release process

1. `python v11/preprocess_wordnet.py` (only when data changes)
2. `cargo run -p v11-builder --release -- --config v11/config.json --output v11/artifacts/`
3. `cargo test --workspace && cargo clippy --all-targets -- -D warnings`
4. `cargo run -p v11-bench --release` (sanity check)
5. `cargo run -p v11-demos --release --bin demo-code` (priority coverage check)
6. Publish the `v11/artifacts/` directory to the model hub of your choice.

## License

Apache 2.0
