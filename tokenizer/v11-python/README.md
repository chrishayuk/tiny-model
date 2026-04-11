# v11-tokenizer — Python bindings

Pure-Rust knowledge-first tokenizer, exposed as a Python module via PyO3.

## Install

From source:

```bash
cd tiny-model/tokenizer/v11-python
maturin develop --release
```

Then from any Python script in the same venv:

```python
import v11

tok = v11.Tokenizer.from_file("../v11/artifacts/v11.vocab.bin")
print(tok)                                         # <v11.Tokenizer vocab_size=71260>
print(tok.vocab_size)                              # 71260
print(tok.pad_id, tok.unk_id, tok.bos_id, tok.eos_id)  # 0 1 2 3

ids = tok.encode("def fibonacci(n):")
pieces = tok.encode_pieces("def fibonacci(n):")
text = tok.decode(ids)
```

## API

| method | returns | notes |
|---|---|---|
| `Tokenizer.from_file(path)` | `Tokenizer` | Load from a `.vocab.bin` file |
| `tok.encode(text)` | `list[int]` | Tokenize to ids |
| `tok.encode_pieces(text)` | `list[str]` | Tokenize to piece strings |
| `tok.decode(ids)` | `str` | Reverse to text |
| `tok.id_to_piece(id)` | `str \| None` | Look up a single id |
| `tok.piece_to_id(piece)` | `int \| None` | Look up a single piece |
| `tok.vocab_size` | `int` | Total pieces |
| `tok.pad_id`, `unk_id`, `bos_id`, `eos_id` | `int` | Special token ids |
| `len(tok)` | `int` | Same as `vocab_size` |

## Performance

Encode throughput on a single thread (release build):

```
~9.3M tokens/sec
~28 MB/sec
```

That's roughly 10-40× faster than the Python `sentencepiece` package
on comparable inputs, because the longest-match is a single
Aho-Corasick pass with no C++ FFI hops.

## Build a wheel for distribution

```bash
maturin build --release
ls target/wheels/
# v11_tokenizer-0.1.0-cp312-abi3-macosx_11_0_arm64.whl
```

## License

Apache 2.0
