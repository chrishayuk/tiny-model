# v11 Tokenizer Specification

**Knowledge-First Tokenizer**

Version 0.1.0

---

## 1. Objective

v11 is a pure-Rust longest-match tokenizer whose vocabulary is
**assembled from the structure of knowledge** — tree-sitter AST
grammars for ~77 programming languages, WordNet lemmas ranked by
wordfreq Zipf, Wikidata proper nouns, hand-curated morphemes, Greek
letters, math symbols, and function words — not discovered from BPE
merges on a corpus.

Every token is designed to be a potential **compilation target**.
Priority concepts (language keywords, type names, scientific terms,
acronyms, Greek letters) are guaranteed to be a single piece.
Compilation into a knowledge graph's edges costs one edge per
target instead of two to five.

The trade-off is explicit and accepted: v11 gives up chars/token
compression ratio relative to production tokenizers trained on
trillion-token corpora, in exchange for **100% single-token coverage
on the priority target suite**.

## 2. Benchmark results

Single-token coverage on priority targets (81 = 9 Python + 16 Rust +
10 JS/TS + 9 C + 9 Java + 8 Go + 8 Acronyms + 6 Greek + 6 Scientific):

| tokenizer | vocab | hits | pct |
|---|---|---|---|
| **v11 (this)** | **~25K target** | **81/81** | **100%** |
| gemma-3-4b-pt | 262K | 76/81 | 94% |
| llama-3.2-1b | 128K | 74/81 | 91% |
| tiktoken cl100k | 100K | 74/81 | 91% |
| tiktoken o200k | 200K | 74/81 | 91% |
| mistral-7b | 32K | 58/81 | 72% |
| v10c 32K | 32K | 27/81 | 33% |

v11 is the only tokenizer hitting 100%. Gemma at 10× the vocab size
misses 5, notably Rust stdlib types (`Vec`, `Option`, `Result`) and
two other items. Llama / tiktoken miss scientific terms. Mistral
misses Greek entirely.

## 3. Vocabulary assembly

Layered construction — earlier layers are guaranteed to survive any
budget trim:

| Layer | Source | Approx size | Role |
|---|---|---|---|
| L0_infra | Hand-curated Unicode | ~330 | Digits, ASCII punct, code operators, Greek upper+lower, ~170 math chars (operators/relations/logic/sets/arrows/fractions), currency, legal marks, ASCII a-z + A-Z |
| L1_function_words | Curated stopwords | ~119 | Prepositions, pronouns, modals, determiners that WordNet skips |
| L2_morphemes | Curated prefixes/suffixes | ~100 | `un`, `re`, `pre`, `post`, `photo`, `bio`, `tion`, `ment`, etc. |
| L3_code_priority | tree-sitter AST | ~1100 | Deep extraction (keywords + delimiters + sequences + supertypes + top parent_child children) for 10 priority languages |
| L4_code_extras | config.language_extras | ~130 | Stdlib type names tree-sitter doesn't dump: C primitive types, Rust numeric widths + stdlib types, JS built-ins |
| L5_code_other | tree-sitter AST | ~4400 | Deep extraction (same rules) for the other ~67 tree-sitter languages |
| L6_acronyms | Curated technical acronyms | ~45 | JSON, HTTP, SQL, REST, YAML, etc. |
| L7_lemmas | nltk WordNet + wordfreq Zipf ≥ 2.5 | ~27K | English lemmas sorted by frequency, top-3K interleaved with their TitleCase variants for class/type naming conventions |
| L8_entities | Wikidata domain files | ~2K | Single-word proper nouns from geography/science/people/organisations/politics/culture/sport domains |

Total base vocabulary ~35K. With plain + ▁-prefixed forms for
word-like tokens, the user_defined_symbols list runs to ~70K. The
final SP vocab_size is set by the config and trimmed from the tail
(rare lemmas first) if over budget.

## 4. Config-driven design

Everything is declared in `v11/config.json`:
- `infra` — Unicode symbol categories
- `function_words`, `morpheme_prefixes`, `morpheme_suffixes`, `acronyms`
- `priority_languages` — deep-extraction language list
- `language_extras` — per-language stdlib supplement lists (filling
  gaps tree-sitter doesn't export)
- `layers` — assembly order + source dispatch
- `vocab_size`, `max_user_syms`, `wordnet_min_zipf`,
  `wordnet_titlecase_top_n` — tuning knobs

Rebuilding the tokenizer after a config change is a single `cargo run
-p v11-builder` invocation.

## 5. Data files

`v11/data/` holds preprocessed inputs that would otherwise require
Python + nltk + wordfreq at build time:

- `wordnet_lemmas.json` — frequency-ranked lemma list generated once
  by `preprocess_wordnet.py`. The Rust builder reads this directly,
  so the assembly pipeline has no Python dependency.

`v11/corpus/` holds the SentencePiece training corpus:

- `code/{python,rust,javascript,typescript,c,java,go}/` — small,
  idiomatic code snippets per language
- `prose/{science,history,geography,tech}/` — short prose passages
  covering the scientific + technical + biographical domains v11
  optimises for

The corpus is intentionally small — the vocabulary is defined by the
config + data files, so SP training only needs enough text to learn
segmentation rules for unknown word forms.

## 6. Rust crates

The tokenizer lives as a Cargo workspace:

| Crate | Purpose | Binary |
|---|---|---|
| `v11-core` | Shared types + vocab assembly logic | lib |
| `v11-builder` | Assembles vocab, trains SP, writes HF + SP artefacts | `v11-build` |
| `v11-cli` | Encode/decode CLI using HuggingFace tokenizers crate | `v11` |
| `v11-bench` | Performance benchmark (encode/decode throughput) | `v11-bench` |
| `v11-demos` | Sample encode/decode demos | various |
| `v11-python` | PyO3 bindings for Python use | lib (cdylib) |

All use the pure-Rust HuggingFace `tokenizers` crate for runtime —
no C++ FFI, portable builds, HF tokenizer.json format native.

## 7. HuggingFace compatibility

The builder emits a complete HF-compatible bundle at
`v11/artifacts/`:

```
v11/artifacts/
├── tokenizer.json           # HuggingFace tokenizers library format
├── tokenizer_config.json    # AutoTokenizer metadata
├── special_tokens_map.json  # pad / bos / eos / unk mapping
├── vocab.txt                # human-readable piece list
├── v11.model                # SentencePiece native format
├── v11.vocab                # SentencePiece vocab file
└── README.md                # model card
```

After build, any of the following work:

```python
# HuggingFace transformers
from transformers import AutoTokenizer
tok = AutoTokenizer.from_pretrained("./v11/artifacts")

# HuggingFace tokenizers (Rust-backed)
from tokenizers import Tokenizer
tok = Tokenizer.from_file("./v11/artifacts/tokenizer.json")

# Raw SentencePiece
import sentencepiece as spm
sp = spm.SentencePieceProcessor(model_file="./v11/artifacts/v11.model")
```

Publishing to HuggingFace Hub:

```bash
huggingface-cli upload <org>/v11-tokenizer ./v11/artifacts/
```

## 8. CLI usage

```bash
# Encode stdin or a string
echo "def fibonacci(n):" | v11 encode
v11 encode --text "The capital of France is Paris"

# Decode token IDs
v11 decode --ids "32001,5,1024,12"

# Info about the loaded tokenizer
v11 info
```

The CLI auto-discovers `v11/artifacts/tokenizer.json` or accepts
`--model <path>` for an explicit file.

## 9. Pass criteria

Before accepting a v11 build as "shipped":

- **Priority single-token coverage 100%** on all nine check categories
- **Byte fallback rate < 2%** on the training corpus
- **Chars/token > 3.0** on prose/science and prose/tech
- **No token in knowledge_vocab collides with another via lowercase
  dedup** (`Type` and `type` must coexist)
- **Every priority language keyword appears as a single token in both
  plain and ▁-prefixed forms** (word-internal + word-boundary matching)
- **`cargo test -p v11-core -p v11-builder -p v11-cli` passes**
- **HF AutoTokenizer round-trip**: encode then decode returns the
  original text modulo whitespace normalisation

## 10. Release process

1. `python preprocess_wordnet.py` — regenerate `data/wordnet_lemmas.json`
   (only when nltk/wordfreq changes)
2. `cargo run -p v11-builder -- --config v11/config.json --output v11/artifacts/`
3. `cargo test` — all v11 crates pass
4. `cargo run -p v11-bench` — performance sanity check
5. `huggingface-cli upload <org>/v11-tokenizer ./v11/artifacts/`
6. `cargo publish -p v11-core -p v11-cli` (builder keeps as internal)
