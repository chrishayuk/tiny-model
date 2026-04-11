"""Cross-check all three loading paths produce identical ids."""
from pathlib import Path

import v11
from tokenizers import Tokenizer as HFTokenizer
from transformers import AutoTokenizer

from _samples import SAMPLES

ROOT = Path(__file__).resolve().parents[1]
BUILD = ROOT / "artifacts"


def main() -> None:
    native = v11.Tokenizer.from_file(str(BUILD / "v11.vocab.bin"))
    hf = HFTokenizer.from_file(str(BUILD / "tokenizer.json"))
    auto = AutoTokenizer.from_pretrained(str(BUILD))

    ok = True
    for name, text in SAMPLES:
        a = native.encode(text)
        b = hf.encode(text).ids
        c = auto(text, add_special_tokens=False)["input_ids"]
        match = a == b == c
        ok &= match
        flag = "OK  " if match else "FAIL"
        print(f"[{flag}] {name}: native={len(a)} hf={len(b)} auto={len(c)}")
        if not match:
            print(f"    native: {a}")
            print(f"    hf:     {b}")
            print(f"    auto:   {c}")

    print()
    print("all three paths agree" if ok else "MISMATCH")


if __name__ == "__main__":
    main()
