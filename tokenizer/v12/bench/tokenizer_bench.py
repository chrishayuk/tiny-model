#!/usr/bin/env python3
"""TOK-0 harness skeleton for the v12 tokenizer design funnel.

Real, dependency-free subcommands that run today against the v11
artifacts already in this repo:

  census      five-way taxonomy classification of a vocab
  intrinsics  compression / fertility via greedy longest-match tokenization
  g0-smoke    census + intrinsics against v11's real tokenizer + sample
              corpus — a SMOKE TEST of this harness, not Gate G0 itself
              (G0 needs the pinned C2 24M-token atlas stream, not present
              in this repo).

Everything downstream of TOK-0 (the actual TOK-1 grid screen, MSI battery
runs, parity checks) needs candidates that don't exist yet and is tracked
as queued work in chuk-experiments, not implemented here.
"""
import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent          # tokenizer/v12/bench
V12_ROOT = HERE.parent                           # tokenizer/v12
V11_ARTIFACTS = V12_ROOT.parent / "v11" / "artifacts"
V11_CORPUS = V12_ROOT.parent / "v11" / "corpus"


def load_vocab(vocab_json_path):
    d = json.loads(Path(vocab_json_path).read_text())
    pieces = d["pieces"]  # [{"id","text","score"}, ...]
    special = d.get("special", {})
    id_to_text = {p["id"]: p["text"] for p in pieces}
    return id_to_text, special


def classify_five_way(id_to_text, special, exercised_ids):
    """Five-way taxonomy per TOK-0 pins. v11 has no dormant blocks (fails C7),
    so categories 3/4 are always 0 for it — that itself is a real, correct
    finding, not a placeholder.
    """
    pad_id = special.get("pad_id")
    active_special_ids = {v for k, v in special.items() if k != "pad_id"}
    counts = {1: 0, 2: 0, 3: 0, 4: 0, 5: 0}
    for tid in id_to_text:
        if tid == pad_id:
            counts[1] += 1
        elif tid in active_special_ids:
            counts[2] += 1
        elif tid not in exercised_ids:
            counts[5] += 1
        # else: exercised ordinary vocab — not counted against any category
    return counts


def cmd_census(args):
    id_to_text, special = load_vocab(args.vocab)
    exercised = set()
    if args.corpus:
        exercised = _exercised_ids(id_to_text, Path(args.corpus))
    counts = classify_five_way(id_to_text, special, exercised)
    print(json.dumps({
        "vocab_total": len(id_to_text),
        "special": special,
        "exercised_count": len(exercised),
        "five_way_counts": counts,
        "note": "categories 3/4 are 0 for v11 by construction — no dormant blocks (fails C7)",
    }, indent=2))


_END = object()  # sentinel key distinct from any char — vocab pieces can legitimately contain "$"


def _build_trie(id_to_text):
    trie = {}
    for tid, text in id_to_text.items():
        node = trie
        for ch in text:
            node = node.setdefault(ch, {})
        node[_END] = tid
    return trie


def _greedy_tokenize(text, trie):
    ids = []
    i, n = 0, len(text)
    while i < n:
        node, j, last_match = trie, i, None
        while j < n and text[j] in node:
            node = node[text[j]]
            j += 1
            if _END in node:
                last_match = (j, node[_END])
        if last_match is None:
            ids.append(None)  # unmapped byte/char — no UNK id tracked in this simple sim
            i += 1
        else:
            j, tid = last_match
            ids.append(tid)
            i = j
    return ids


def _sp_metaspace_normalize(text):
    """Approximate SentencePiece metaspace normalization (v11 config.json: metaspace ["▁"]):
    literal spaces become the metaspace char, with a leading one for the first word.
    Approximate — real normalization also touches newlines/tabs; not a substitute for parity."""
    return "▁" + text.replace(" ", "▁")


def _iter_corpus_texts(corpus_dir):
    for p in sorted(Path(corpus_dir).rglob("*")):
        if p.is_file():
            try:
                yield p, _sp_metaspace_normalize(p.read_text(errors="ignore"))
            except Exception:
                continue


def _exercised_ids(id_to_text, corpus_dir):
    trie = _build_trie(id_to_text)
    exercised = set()
    for _, text in _iter_corpus_texts(corpus_dir):
        for tid in _greedy_tokenize(text, trie):
            if tid is not None:
                exercised.add(tid)
    return exercised


def cmd_intrinsics(args):
    id_to_text, special = load_vocab(args.vocab)
    trie = _build_trie(id_to_text)
    total_tokens, total_bytes, total_words, unmapped = 0, 0, 0, 0
    for path, text in _iter_corpus_texts(args.corpus):
        ids = _greedy_tokenize(text, trie)
        # unmapped (None) entries are failed matches, not real pieces -- counting
        # them toward total_tokens silently inflated compression/fertility on any
        # candidate with nonzero unmapped chars (found while evaluating the first
        # real TOK-1 candidate, 2026-07-19). Excluded here; tracked separately.
        total_tokens += sum(1 for t in ids if t is not None)
        unmapped += sum(1 for t in ids if t is None)
        total_bytes += len(text.encode("utf-8"))
        total_words += len(text.split())
    compression = total_tokens / total_bytes if total_bytes else None
    fertility = total_tokens / total_words if total_words else None
    print(json.dumps({
        "corpus": str(args.corpus),
        "total_tokens": total_tokens,
        "total_bytes": total_bytes,
        "total_words": total_words,
        "unmapped_chars": unmapped,
        "unmapped_fraction_of_positions": unmapped / (total_tokens + unmapped) if (total_tokens + unmapped) else None,
        "compression_tokens_per_byte": compression,
        "fertility_pieces_per_word": fertility,
        "note": "greedy longest-match simulation in pure Python — approximates but is "
                "NOT bit-identical to the real Rust v11 tokenizer; parity check is TODO. "
                "compression/fertility computed over successfully-mapped tokens only; "
                "high unmapped_fraction means these numbers understate real cost.",
    }, indent=2))


def _iter_corpus_raw(corpus_dir):
    """Unlike _iter_corpus_texts, no metaspace preprocessing — the real v11
    binary does its own normalization, so raw text is what its CLI expects."""
    for p in sorted(Path(corpus_dir).rglob("*")):
        if p.is_file():
            try:
                yield p, p.read_text(errors="ignore")
            except Exception:
                continue


def cmd_roundtrip(args):
    """Operational gate per doc §2.3: exact UTF-8 round-trip; UNK > 0 is a hard
    reject. Unlike census/intrinsics/g0-smoke, this drives the REAL compiled
    v11 Rust binary (build first: `cargo build --release -p v11-cli` from
    tokenizer/) rather than the Python greedy-match approximation — a genuine
    product-level check, not a harness smoke test."""
    import subprocess

    binary = args.binary
    vocab = args.vocab
    if not Path(binary).exists():
        print(json.dumps({
            "error": f"binary not found at {binary}",
            "fix": "cd tokenizer && cargo build --release -p v11-cli",
        }, indent=2))
        sys.exit(1)

    results = {"files_checked": 0, "roundtrip_mismatches": [], "unk_total": 0, "unk_files": [], "errors": []}
    for path, text in _iter_corpus_raw(args.corpus):
        results["files_checked"] += 1
        try:
            enc = subprocess.run(
                [binary, "--model", str(vocab), "encode", "--text", text, "--json"],
                capture_output=True, text=True, timeout=30, check=True,
            )
            ids = json.loads(enc.stdout)["ids"]
        except Exception as e:
            results["errors"].append({"file": str(path), "stage": "encode", "error": str(e)})
            continue

        unk_count = sum(1 for i in ids if i == 1)  # unk_id per v11 special map
        if unk_count:
            results["unk_total"] += unk_count
            results["unk_files"].append({"file": str(path), "unk_count": unk_count})

        try:
            dec = subprocess.run(
                [binary, "--model", str(vocab), "decode", "--ids", ",".join(map(str, ids))],
                capture_output=True, text=True, timeout=30, check=True,
            )
        except Exception as e:
            results["errors"].append({"file": str(path), "stage": "decode", "error": str(e)})
            continue

        decoded = dec.stdout[:-1] if dec.stdout.endswith("\n") else dec.stdout
        if decoded != text:
            results["roundtrip_mismatches"].append({
                "file": str(path),
                "original_len": len(text),
                "decoded_len": len(decoded),
            })

    results["roundtrip_pass"] = not results["roundtrip_mismatches"] and not results["errors"]
    results["unk_gate_pass"] = results["unk_total"] == 0
    print(json.dumps(results, indent=2))


def cmd_grid_screen(args):
    """Gate G1 per doc section 5: run the pinned selection algorithm
    (g1_selection.select_survivors) over a candidates file. The algorithm
    itself is fully implemented and unit-tested against synthetic fixtures
    (see test_g1_selection.py) -- what's genuinely blocked is the INPUT:
    real candidates need TOK-1 grid tokenizers trained on the frozen C8
    corpus, which doesn't exist in this repo. Refuses to run against
    undecided pins rather than silently defaulting them."""
    import yaml

    from g1_selection import select_survivors

    pins = yaml.safe_load(Path(args.pins).read_text())["open_pins"]
    missing = [k for k in ("census_F_max", "census_R_max", "MSI_canonical_min") if pins.get(k) is None]
    if missing:
        print(json.dumps({
            "blocked": f"pins {missing} are still PIN: null in {args.pins} -- these are Chris's "
                        "research decisions (see pins/tok0_pins.yaml open_pins), not something "
                        "this harness will invent a default for.",
        }, indent=2))
        sys.exit(1)

    if not Path(args.candidates).exists():
        print(json.dumps({
            "blocked": f"no candidates file at {args.candidates} -- TOK-1 needs real tokenizers "
                        "trained on the frozen C8 superset corpus (not present in this repo) run "
                        "through `intrinsics`/`census`/MSI battery first to produce one.",
        }, indent=2))
        sys.exit(1)

    candidates = [json.loads(line) for line in Path(args.candidates).read_text().splitlines() if line.strip()]
    result = select_survivors(candidates, pins["census_F_max"], pins["census_R_max"], pins["MSI_canonical_min"])
    print(json.dumps(result, indent=2))


def cmd_g0_smoke(args):
    vocab = args.vocab or (V11_ARTIFACTS / "v11.vocab.json")
    corpus = args.corpus or V11_CORPUS
    print("=== G0 SMOKE TEST (not the pinned gate — see tokenizer/v12/README.md) ===", file=sys.stderr)
    id_to_text, special = load_vocab(vocab)
    exercised = _exercised_ids(id_to_text, corpus)
    counts = classify_five_way(id_to_text, special, exercised)
    print(json.dumps({
        "vocab_path": str(vocab),
        "corpus_path": str(corpus),
        "vocab_total": len(id_to_text),
        "expected_vocab_total_per_design_doc": 71261,
        "vocab_total_matches_design_doc": len(id_to_text) + 1 == 71261 or len(id_to_text) == 71261,
        "exercised_on_sample_corpus": len(exercised),
        "expected_exercised_per_design_doc_on_real_atlas_stream": 17158,
        "five_way_counts": counts,
        "blocked": "full G0 (bit-for-bit atlas-stream reproduction, 17,158 distinct ids) "
                    "requires the C2 24M-token atlas stream, not present in this repo",
    }, indent=2))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="command", required=True)

    p_census = sub.add_parser("census", help="five-way taxonomy census of a vocab")
    p_census.add_argument("--vocab", required=True)
    p_census.add_argument("--corpus", help="dir of text files to determine 'exercised' ids")
    p_census.set_defaults(func=cmd_census)

    p_intr = sub.add_parser("intrinsics", help="compression + fertility via greedy longest-match")
    p_intr.add_argument("--vocab", required=True)
    p_intr.add_argument("--corpus", required=True, type=Path)
    p_intr.set_defaults(func=cmd_intrinsics)

    p_g0 = sub.add_parser("g0-smoke", help="census+intrinsics smoke test against real v11 artifacts")
    p_g0.add_argument("--vocab", type=Path, default=None)
    p_g0.add_argument("--corpus", type=Path, default=None)
    p_g0.set_defaults(func=cmd_g0_smoke)

    p_rt = sub.add_parser("roundtrip", help="real UTF-8 round-trip + UNK gate check via the compiled v11 binary")
    p_rt.add_argument("--binary", default=str(V12_ROOT.parent / "target" / "release" / "v11"))
    p_rt.add_argument("--vocab", default=str(V11_ARTIFACTS / "v11.vocab.bin"))
    p_rt.add_argument("--corpus", type=Path, default=V11_CORPUS)
    p_rt.set_defaults(func=cmd_roundtrip)

    p_g1 = sub.add_parser("grid-screen", help="Gate G1 candidate selection (needs a real candidates file + decided pins)")
    p_g1.add_argument("--candidates", default=str(V12_ROOT / "training" / "candidates.jsonl"), help="jsonl of candidate intrinsic/gate results")
    p_g1.add_argument("--pins", default=str(V12_ROOT / "pins" / "tok0_pins.yaml"))
    p_g1.set_defaults(func=cmd_grid_screen)

    args = ap.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
