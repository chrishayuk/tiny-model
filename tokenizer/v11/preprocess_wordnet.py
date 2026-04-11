#!/usr/bin/env python3
"""
One-shot preprocessor: turn nltk WordNet + wordfreq into a stable
data file that the Rust builder can read.

Output:
  tiny-model/tokenizer/v11/data/wordnet_lemmas.json
    {
      "generated_at": "2026-04-11",
      "min_zipf": 2.5,
      "lemmas": [
        {"lemma": "the",  "zipf": 7.73},
        {"lemma": "and",  "zipf": 7.53},
        ...
      ]
    }

Sorted by Zipf descending so the Rust builder can just slice a
prefix. Rerun whenever NLTK / wordfreq changes.

Run from this directory:
  python preprocess_wordnet.py
"""

import json
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).parent
OUT = HERE / "data" / "wordnet_lemmas.json"
OUT.parent.mkdir(parents=True, exist_ok=True)

MIN_ZIPF = 2.5


def main():
    from nltk.corpus import wordnet as wn
    import wordfreq

    lemmas = set()
    for syn in wn.all_synsets():
        for lemma in syn.lemmas():
            name = lemma.name().lower()
            if "_" in name or " " in name:
                continue
            if 3 <= len(name) <= 20 and name.isalpha():
                lemmas.add(name)

    filtered = []
    for w in lemmas:
        z = wordfreq.zipf_frequency(w, "en")
        if z >= MIN_ZIPF:
            filtered.append({"lemma": w, "zipf": round(z, 3)})
    filtered.sort(key=lambda x: (-x["zipf"], x["lemma"]))

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": "nltk.corpus.wordnet + wordfreq",
        "min_zipf": MIN_ZIPF,
        "total_raw": len(lemmas),
        "kept": len(filtered),
        "lemmas": filtered,
    }
    with open(OUT, "w") as f:
        json.dump(payload, f, separators=(",", ":"))
    print(f"  wrote {OUT}")
    print(f"  {len(lemmas)} raw lemmas, {len(filtered)} kept @ Zipf ≥ {MIN_ZIPF}")
    print(f"  top 10: {[x['lemma'] for x in filtered[:10]]}")
    print(f"  tail 10: {[x['lemma'] for x in filtered[-10:]]}")


if __name__ == "__main__":
    main()
