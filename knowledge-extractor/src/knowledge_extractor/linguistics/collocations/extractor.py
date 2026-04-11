"""Derives Brown-corpus collocations and yields raw triples.

Three relations:

* ``bigram_pmi``    — top-PMI bigrams over the full Brown corpus
* ``adjective_noun`` — ADJ→NOUN bigrams ranked by frequency
* ``verb_object``   — VERB→NOUN bigrams ranked by frequency
"""

from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Iterator

from ...base import BaseExtractor, DatasetMeta, RawTriple
from ...paths import default_raw_dir, setup_nltk_data_dir
from .model import META


class CollocationsExtractor(BaseExtractor):
    def meta(self) -> DatasetMeta:
        return META

    def extract(self, config: dict) -> Iterator[RawTriple]:
        raw_dir = Path(config.get("raw_dir") or default_raw_dir())
        setup_nltk_data_dir(raw_dir)
        from nltk.collocations import (  # type: ignore
            BigramAssocMeasures,
            BigramCollocationFinder,
        )
        from nltk.corpus import brown  # type: ignore

        min_freq = int(config.get("min_freq", 5))
        top_bigrams = int(config.get("top_bigrams", 10000))
        top_tagged = int(config.get("top_tagged", 3000))
        tagged_min_count = int(config.get("tagged_min_count", 3))

        # Top-PMI bigrams.
        words = [w.lower() for w in brown.words() if w.isalpha()]
        finder = BigramCollocationFinder.from_words(words)
        finder.apply_freq_filter(min_freq)
        for a, b in finder.nbest(BigramAssocMeasures.pmi, top_bigrams):
            yield RawTriple(
                subject=a,
                relation="bigram_pmi",
                object=b,
                provenance="brown",
            )

        # POS-tagged bigrams for adj-noun and verb-object.
        tagged = [
            ((w.lower(), t), (w2.lower(), t2))
            for (w, t), (w2, t2) in zip(
                brown.tagged_words(tagset="universal")[:-1],
                brown.tagged_words(tagset="universal")[1:],
            )
            if w.isalpha() and w2.isalpha()
        ]

        for left_tag, right_tag, relation in (
            ("ADJ", "NOUN", "adjective_noun"),
            ("VERB", "NOUN", "verb_object"),
        ):
            counts: Counter = Counter()
            for (w1, t1), (w2, t2) in tagged:
                if t1 == left_tag and t2 == right_tag:
                    counts[(w1, w2)] += 1
            for (a, b), c in counts.most_common(top_tagged):
                if c < tagged_min_count:
                    break
                yield RawTriple(
                    subject=a,
                    relation=relation,
                    object=b,
                    provenance="brown",
                )
