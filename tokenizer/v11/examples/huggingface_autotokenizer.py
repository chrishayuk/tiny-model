"""HuggingFace transformers AutoTokenizer.

Install:
    pip install transformers tokenizers

Loads the v11 artifacts directory like any published HF tokenizer — consuming
tokenizer.json + tokenizer_config.json + special_tokens_map.json.
"""
from pathlib import Path

from transformers import AutoTokenizer

from _samples import SAMPLES

BUILD_DIR = Path(__file__).resolve().parents[1] / "artifacts"


def main() -> None:
    tok = AutoTokenizer.from_pretrained(str(BUILD_DIR))
    print(f"loaded: {type(tok).__name__}")
    print(f"vocab_size={tok.vocab_size}")
    print(f"pad={tok.pad_token} ({tok.pad_token_id})  "
          f"bos={tok.bos_token} ({tok.bos_token_id})  "
          f"eos={tok.eos_token} ({tok.eos_token_id})  "
          f"unk={tok.unk_token} ({tok.unk_token_id})")
    print()

    for name, text in SAMPLES:
        enc = tok(text, add_special_tokens=False)
        pieces = tok.convert_ids_to_tokens(enc["input_ids"])
        back = tok.decode(enc["input_ids"], skip_special_tokens=True)
        print(f"[{name}] {text}")
        print(f"  pieces ({len(pieces)}): {pieces}")
        print(f"  ids:    {enc['input_ids']}")
        print(f"  decode: {back}")
        print()


if __name__ == "__main__":
    main()
