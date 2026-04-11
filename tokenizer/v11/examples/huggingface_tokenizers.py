"""HuggingFace tokenizers library (Rust-backed).

Install:
    pip install tokenizers

Loads the v11 build artefact directly from tokenizer.json — no special code
path, this is the standard HuggingFace tokenizers entry point.
"""
from pathlib import Path

from tokenizers import Tokenizer

from _samples import SAMPLES

TOKENIZER_JSON = Path(__file__).resolve().parents[1] / "artifacts" / "tokenizer.json"


def main() -> None:
    tok = Tokenizer.from_file(str(TOKENIZER_JSON))
    print(f"loaded: {tok}")
    print(f"vocab_size={tok.get_vocab_size()}")
    print()

    for name, text in SAMPLES:
        enc = tok.encode(text)
        back = tok.decode(enc.ids)
        print(f"[{name}] {text}")
        print(f"  pieces ({len(enc.tokens)}): {enc.tokens}")
        print(f"  ids:    {enc.ids}")
        print(f"  decode: {back}")
        print()


if __name__ == "__main__":
    main()
