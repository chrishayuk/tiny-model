#!/usr/bin/env python3
"""Evaluates one trained TOK-1 candidate against the real target sets and
produces one row in exactly the schema g1_selection.select_survivors()
consumes. Uses each candidate's REAL tokenizer library (sentencepiece /
tokenizers / a direct byte mapping) for encode/decode -- not the harness's
approximate greedy simulator -- so compression/fertility/round-trip here
are the real thing, not an approximation.

Metrics:
  compression          tokens / byte, over ../v11/corpus (same basis as
                        the incumbent's g0-smoke/roundtrip numbers)
  t_core_fertility      tokens / target-item, over targets/t_core.jsonl
  t_cell_coverage       fraction of targets/t_cell.jsonl items that encode
                        to exactly one token (single-piece coverage)
  t_scale_fertility     tokens / target-item, over targets/t_scale.jsonl
  category_5_fraction   fraction of vocab never exercised on ../v11/corpus
                        (category-5 "accidental dead" proxy -- the real
                        C8 corpus will exercise far more of a real vocab
                        than this small sample does; still an honest,
                        comparable-across-candidates measurement)
  msi_canonical          MSI-STRICT rate (fraction of frame_battery.jsonl
                        probe x frame pairs where the operand appears as
                        an exact contiguous id subsequence) -- a
                        conservative proxy for msi_canonical, since the
                        canonicalizer's class-2 case isn't implemented yet
                        (see bench/msi/canonicalizer.py). True
                        MSI-canonical >= this number.
  round_trip_pass/unk_count   real encode->decode->compare + real UNK
                        count over ../v11/corpus, via each candidate's own
                        library -- not the Python trie approximation.

Run: python3 tokenizer/v12/training/evaluate_candidate.py --all
"""
import argparse
import json
import sys
from pathlib import Path

TRAINING_DIR = Path(__file__).resolve().parent
V12_ROOT = TRAINING_DIR.parent
REPO_ROOT = V12_ROOT.parent.parent
V11_CORPUS = REPO_ROOT / "tokenizer" / "v11" / "corpus"
TARGETS = V12_ROOT / "targets"
FRAME_BATTERY = V12_ROOT / "bench" / "msi" / "frame_battery.jsonl"

sys.path.insert(0, str(V12_ROOT / "bench" / "msi"))
from canonicalizer import canonicalize_identity  # noqa: E402


class SPBackend:
    def __init__(self, model_path):
        import sentencepiece as spm
        self.sp = spm.SentencePieceProcessor(model_file=str(model_path))

    def vocab_size(self):
        return self.sp.vocab_size()

    def encode(self, text):
        return self.sp.encode(text, out_type=int)

    def decode(self, ids):
        return self.sp.decode(ids)

    def unk_id(self):
        return self.sp.unk_id()


class ByteLevelBPEBackend:
    def __init__(self, candidate_dir):
        from tokenizers import ByteLevelBPETokenizer
        vocab_file = str(candidate_dir / "vocab.json")
        merges_file = str(candidate_dir / "merges.txt")
        self.tok = ByteLevelBPETokenizer(vocab_file, merges_file)
        self._unk_id = self.tok.token_to_id("<unk>")

    def vocab_size(self):
        return self.tok.get_vocab_size()

    def encode(self, text):
        return self.tok.encode(text).ids

    def decode(self, ids):
        return self.tok.decode(ids)

    def unk_id(self):
        return self._unk_id


class HFTokenizerBackend:
    """Loads v11's real tokenizer.json (HF format) -- confirmed to reproduce
    the same ids as the compiled Rust binary on a spot check -- so the
    incumbent gets evaluated through the exact same pipeline as every
    candidate, a genuine apples-to-apples comparison."""

    def __init__(self, path):
        from tokenizers import Tokenizer
        self.tok = Tokenizer.from_file(str(path))
        self._unk_id = self.tok.token_to_id("<unk>")

    def vocab_size(self):
        return self.tok.get_vocab_size()

    def encode(self, text):
        return self.tok.encode(text).ids

    def decode(self, ids):
        return self.tok.decode(ids)

    def unk_id(self):
        return self._unk_id


class PureByteBackend:
    """Every byte value in [0,256) is token id 4+b; ids 0-3 are specials."""

    def vocab_size(self):
        return 260

    def encode(self, text):
        return [4 + b for b in text.encode("utf-8")]

    def decode(self, ids):
        return bytes(i - 4 for i in ids if i >= 4).decode("utf-8", errors="replace")

    def unk_id(self):
        return 1  # never actually emitted -- every byte has a token


def load_targets(name):
    rows = [json.loads(l) for l in (TARGETS / name).read_text().splitlines() if l.strip()]
    return [r["text"] for r in rows]


def evaluate(backend, candidate_id, algorithm, tag=None):
    t_core = load_targets("t_core.jsonl")
    t_cell = load_targets("t_cell.jsonl")
    t_scale = load_targets("t_scale.jsonl")

    # compression + round-trip + UNK, over the real incumbent sample corpus
    total_tokens, total_bytes, roundtrip_fail, unk_count = 0, 0, 0, 0
    for p in sorted(V11_CORPUS.rglob("*")):
        if not p.is_file():
            continue
        text = p.read_text(errors="ignore")
        ids = backend.encode(text)
        total_tokens += len(ids)
        total_bytes += len(text.encode("utf-8"))
        unk_count += sum(1 for i in ids if i == backend.unk_id())
        if backend.decode(ids) != text:
            roundtrip_fail += 1
    compression = total_tokens / total_bytes if total_bytes else None

    # T-core / T-scale fertility: tokens per target item
    t_core_tokens = sum(len(backend.encode(t)) for t in t_core)
    t_core_fertility = t_core_tokens / len(t_core) if t_core else None
    t_scale_tokens = sum(len(backend.encode(t)) for t in t_scale)
    t_scale_fertility = t_scale_tokens / len(t_scale) if t_scale else None

    # T-cell coverage: fraction of items encoding to exactly one token
    t_cell_single = sum(1 for t in t_cell if len(backend.encode(t)) == 1)
    t_cell_coverage = t_cell_single / len(t_cell) if t_cell else None

    # category-5 proxy: vocab fraction never exercised on the sample corpus
    exercised = set()
    for p in sorted(V11_CORPUS.rglob("*")):
        if p.is_file():
            exercised.update(backend.encode(p.read_text(errors="ignore")))
    category_5_fraction = 1 - (len(exercised) / backend.vocab_size())

    # MSI-strict rate over the frame battery
    probes = [json.loads(l) for l in FRAME_BATTERY.read_text().splitlines() if l.strip()]
    strict_hits, strict_total = 0, 0
    for probe in probes:
        operand_ids = backend.encode(probe["operand"])
        for frame_text in probe["frames"].values():
            framed_ids = backend.encode(frame_text)
            strict_total += 1
            if canonicalize_identity(framed_ids, operand_ids) is not None:
                strict_hits += 1
    msi_strict = strict_hits / strict_total if strict_total else None

    row = {
        "id": candidate_id,
        "algorithm": algorithm,
        "compression": compression,
        "t_core_fertility": t_core_fertility,
        "t_cell_coverage": t_cell_coverage,
        "t_scale_fertility": t_scale_fertility,
        "category_5_fraction": category_5_fraction,
        "msi_canonical": msi_strict,  # conservative proxy, see module docstring
        "msi_strict_note": "class-2 canonicalization not implemented yet; this is MSI-STRICT, a lower bound on true msi_canonical",
        "round_trip_pass": roundtrip_fail == 0,
        "unk_count": unk_count,
        "vocab_size": backend.vocab_size(),
    }
    if tag:
        row["tag"] = tag
    return row


CANDIDATES = [
    ("v11_incumbent", "incumbent_sp", "hf"),
    ("unigram_sp_4000_v0", "unigram_sp", "sp"),
    ("unigram_sp_6900_v0", "unigram_sp", "sp"),
    ("bpe_sp_4000_v0", "bpe_sp", "sp"),
    ("bpe_sp_8000_v0", "bpe_sp", "sp"),
    ("bpe_sp_16000_v0", "bpe_sp", "sp"),
    ("bpe_sp_20000_v0", "bpe_sp", "sp"),
    ("byte_level_bpe_4000_v0", "byte_level_bpe", "blbpe"),
    ("byte_level_bpe_8000_v0", "byte_level_bpe", "blbpe"),
    ("pure_byte_v0", "pure_byte", "pure_byte"),
]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--out", default=str(TRAINING_DIR / "candidates.jsonl"))
    args = ap.parse_args()

    rows = []
    for candidate_id, algorithm, kind in CANDIDATES:
        cdir = TRAINING_DIR / "candidates" / candidate_id
        if kind == "sp":
            backend = SPBackend(cdir / f"{candidate_id}.model")
        elif kind == "blbpe":
            backend = ByteLevelBPEBackend(cdir)
        elif kind == "hf":
            backend = HFTokenizerBackend(REPO_ROOT / "tokenizer" / "v11" / "artifacts" / "tokenizer.json")
        else:
            backend = PureByteBackend()
        tag = "branch_b" if algorithm == "pure_byte" else ("incumbent" if algorithm == "incumbent_sp" else None)
        row = evaluate(backend, candidate_id, algorithm, tag=tag)
        rows.append(row)
        print(json.dumps(row, indent=2))

    with open(args.out, "w") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")
    print(f"\nwrote {len(rows)} rows to {args.out}", file=sys.stderr)


if __name__ == "__main__":
    main()
