"""Native v11 Python bindings (PyO3).

Install:
    cd tiny-model/tokenizer/v11-python
    maturin build --release
    pip install target/wheels/v11_tokenizer-*.whl
"""
from pathlib import Path

import v11

from _samples import SAMPLES

VOCAB = Path(__file__).resolve().parents[1] / "artifacts" / "v11.vocab.bin"


def main() -> None:
    tok = v11.Tokenizer.from_file(str(VOCAB))
    print(f"loaded: {tok}")
    print(f"vocab_size={tok.vocab_size}  pad={tok.pad_id} unk={tok.unk_id} bos={tok.bos_id} eos={tok.eos_id}")
    print()

    for name, text in SAMPLES:
        ids = tok.encode(text)
        pieces = tok.encode_pieces(text)
        back = tok.decode(ids)
        print(f"[{name}] {text}")
        print(f"  pieces ({len(pieces)}): {pieces}")
        print(f"  ids:    {ids}")
        print(f"  decode: {back}")
        print()


if __name__ == "__main__":
    main()
