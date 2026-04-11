"""v11 leanness report.

Four checks per SPEC.md §9:
  1. Chars/token per corpus domain (prose/science, prose/tech, code/*).
  2. Unk rate per domain.
  3. Top surface forms that hit unk (shows what the vocab is missing).
  4. Cross-tokenizer compression comparison — v11 vs
     gemma-3-4b-pt / llama-3.2-1b / tiktoken o200k / mistral-7b — on the
     same prose+code mix. Reports chars/token so high is better.

All checks run against the same native v11 loader the training uses,
so the numbers are representative of training-time behaviour.

Optional — install the comparison tokenizers once:
    pip install tiktoken transformers tokenizers
    # then `huggingface-cli login` and accept gemma-3 / llama-3 licences
"""
from __future__ import annotations

from collections import Counter
from pathlib import Path

import v11

ROOT = Path(__file__).resolve().parents[1]
CORPUS = ROOT / "corpus"
VOCAB = ROOT / "artifacts" / "v11.vocab.bin"


def load_domain(subdir: Path) -> list[str]:
    texts = []
    for p in sorted(subdir.rglob("*")):
        if p.is_file() and p.suffix != ".md":
            try:
                texts.append(p.read_text(errors="ignore"))
            except Exception:
                pass
    return texts


def score_domain(tok: "v11.Tokenizer", texts: list[str]) -> tuple[int, int, int, Counter]:
    total_chars = 0
    total_tokens = 0
    unk_tokens = 0
    unk_surface: Counter = Counter()
    unk_id = tok.unk_id
    for t in texts:
        ids = tok.encode(t)
        total_chars += len(t)
        total_tokens += len(ids)
        for i, tid in enumerate(ids):
            if tid == unk_id:
                unk_tokens += 1
                # Best-effort: surface char from decode of neighbourhood
                snippet = tok.decode([ids[max(0, i - 1)], tid, ids[min(len(ids) - 1, i + 1)]])
                unk_surface[snippet.strip()[:20]] += 1
    return total_chars, total_tokens, unk_tokens, unk_surface


def run_native_per_domain(tok: "v11.Tokenizer") -> None:
    print("=" * 64)
    print("1-3. v11 native — per-domain chars/token and unk rate")
    print("=" * 64)
    print(f"{'domain':<28} {'chars':>10} {'tokens':>10} {'c/t':>6}  {'unk%':>6}")
    print("-" * 64)

    grand_chars = 0
    grand_tokens = 0
    grand_unk = 0
    all_unk: Counter = Counter()

    for category in ["prose", "code"]:
        cat_dir = CORPUS / category
        if not cat_dir.exists():
            continue
        for subdir in sorted(cat_dir.iterdir()):
            if not subdir.is_dir():
                continue
            texts = load_domain(subdir)
            if not texts:
                continue
            c, t, u, unks = score_domain(tok, texts)
            grand_chars += c
            grand_tokens += t
            grand_unk += u
            all_unk.update(unks)
            label = f"{category}/{subdir.name}"
            ct = c / max(t, 1)
            unkpct = 100 * u / max(t, 1)
            flag = ""
            if category == "prose" and subdir.name in {"science", "tech"} and ct < 3.0:
                flag = "  < 3.0 TARGET MISS"
            elif unkpct > 2.0:
                flag = "  > 2% UNK TARGET MISS"
            print(f"{label:<28} {c:>10} {t:>10} {ct:>6.2f}  {unkpct:>5.2f}%{flag}")

    print("-" * 64)
    total_ct = grand_chars / max(grand_tokens, 1)
    total_unk = 100 * grand_unk / max(grand_tokens, 1)
    print(f"{'TOTAL':<28} {grand_chars:>10} {grand_tokens:>10} {total_ct:>6.2f}  {total_unk:>5.2f}%")

    if all_unk:
        print("\nTop surface forms hitting <unk> (context trigrams):")
        for surface, count in all_unk.most_common(20):
            if surface:
                print(f"  {count:>5}  {surface!r}")


COMPARE_TEXT = """
The mitochondrion is the powerhouse of the eukaryotic cell, responsible
for aerobic respiration. Adenosine triphosphate (ATP) is synthesized via
oxidative phosphorylation. The electron transport chain couples redox
reactions to proton pumping across the inner membrane.

def fibonacci(n):
    if n < 2:
        return n
    return fibonacci(n - 1) + fibonacci(n - 2)

fn main() {
    let v: Vec<Option<Result<i32, String>>> = vec![];
    let total: u64 = (1..=100).sum();
    println!("{}", total);
}

The HTTP/2 specification (RFC 7540) defines a binary framing layer over
TCP. A SQL JOIN operation combines rows from two or more tables based
on a related column. REST APIs typically use JSON for payload encoding.
"""


def run_cross_tokenizer_compare() -> None:
    print()
    print("=" * 64)
    print("4. Cross-tokenizer compression on a mixed prose+code sample")
    print("=" * 64)
    text = COMPARE_TEXT.strip()
    char_len = len(text)
    print(f"sample: {char_len} chars (science prose + Python + Rust + tech prose)")
    print()
    print(f"{'tokenizer':<30} {'vocab':>9} {'tokens':>8} {'c/t':>7}")
    print("-" * 64)

    rows = []

    # v11 native
    tok = v11.Tokenizer.from_file(str(VOCAB))
    ids = tok.encode(text)
    rows.append(("v11 (this)", tok.vocab_size, len(ids)))

    tokenizers_to_try = [
        ("tiktoken cl100k", "cl100k_base", "tiktoken"),
        ("tiktoken o200k", "o200k_base", "tiktoken"),
        ("gemma-3-4b-pt", "google/gemma-3-4b-pt", "hf"),
        ("llama-3.2-1b", "meta-llama/Llama-3.2-1B", "hf"),
        ("mistral-7b", "mistralai/Mistral-7B-v0.1", "hf"),
    ]
    for label, model_id, kind in tokenizers_to_try:
        try:
            if kind == "tiktoken":
                import tiktoken

                enc = tiktoken.get_encoding(model_id)
                ids = enc.encode(text)
                rows.append((label, enc.n_vocab, len(ids)))
            else:
                from transformers import AutoTokenizer

                t = AutoTokenizer.from_pretrained(model_id)
                ids = t.encode(text, add_special_tokens=False)
                rows.append((label, t.vocab_size, len(ids)))
        except Exception as e:
            msg = str(e).split("\n", 1)[0][:40]
            rows.append((label, 0, 0))
            print(f"{label:<30} {'--':>9} {'--':>8} {'--':>7}  (skipped: {msg})")

    # Sort by chars/token descending (excluding skipped)
    scored = [r for r in rows if r[2] > 0]
    scored.sort(key=lambda r: -len(text) / r[2])
    for label, vocab, tokens in scored:
        ct = char_len / tokens
        marker = " ★" if label.startswith("v11") else ""
        print(f"{label:<30} {vocab:>9} {tokens:>8} {ct:>7.2f}{marker}")


def main() -> None:
    tok = v11.Tokenizer.from_file(str(VOCAB))
    print(f"v11 native: {tok.vocab_size} pieces, unk={tok.unk_id}")
    print()
    run_native_per_domain(tok)
    run_cross_tokenizer_compare()


if __name__ == "__main__":
    main()
