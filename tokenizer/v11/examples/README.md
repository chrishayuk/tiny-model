# v11 Python examples

Three ways to use the v11 tokenizer from Python — all load the same
artefact directory and produce identical ids.

| Script | Backend | Load from |
|---|---|---|
| `python_bindings.py` | Native PyO3 (fastest) | `artifacts/v11.vocab.bin` |
| `huggingface_tokenizers.py` | `tokenizers` (Rust) | `artifacts/tokenizer.json` |
| `huggingface_autotokenizer.py` | `transformers.AutoTokenizer` | `artifacts/` directory |
| `compare_all.py` | All three, cross-checked | — |

## Setup

```bash
# native bindings
cd ../../v11-python
maturin build --release
pip install target/wheels/v11_tokenizer-*.whl

# hf libraries
pip install tokenizers transformers
```

## Run

```bash
cd v11/examples
python python_bindings.py
python huggingface_tokenizers.py
python huggingface_autotokenizer.py
python compare_all.py
```

All three backends segment `def fibonacci(n):` into the same nine pieces
(`▁def`, `▁fib`, `on`, `acc`, `i`, `(`, `n`, `)`, `:`) with the same ids.
