"""Derives inflectional forms via lemminflect over a Brown-derived vocabulary.

Produces plurals, verb tenses, comparatives/superlatives, and a handful of
derivational patterns (agent nouns, nominalisations) read off WordNet lemma
links.
"""

from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Iterator

from ...base import BaseExtractor, DatasetMeta, RawTriple
from ...paths import default_raw_dir, setup_nltk_data_dir
from .model import META


_INFLECTIONS = [
    ("NOUN", "NNS", "plurals"),
    ("VERB", "VBD", "verb_past"),
    ("VERB", "VBN", "verb_past_participle"),
    ("VERB", "VBG", "verb_gerund"),
    ("VERB", "VBZ", "verb_3rd_person"),
    ("ADJ",  "JJR", "comparative"),
    ("ADJ",  "JJS", "superlative"),
]


class MorphologyExtractor(BaseExtractor):
    def meta(self) -> DatasetMeta:
        return META

    def extract(self, config: dict) -> Iterator[RawTriple]:
        raw_dir = Path(config.get("raw_dir") or default_raw_dir())
        setup_nltk_data_dir(raw_dir)
        from lemminflect import getInflection  # type: ignore
        from nltk.corpus import brown, wordnet as wn  # type: ignore

        vocab_limit = int(config.get("vocab_limit", 20000))
        per_pos_limit = int(config.get("per_pos_limit", 3000))

        word_counts = Counter(w.lower() for w in brown.words() if w.isalpha())
        vocab = {w for w, _ in word_counts.most_common(vocab_limit)}

        tagged = list(brown.tagged_words(tagset="universal"))
        pos_words: dict[str, list[str]] = {}
        for target in ("NOUN", "VERB", "ADJ"):
            c: Counter = Counter()
            for word, tag in tagged:
                if tag != target:
                    continue
                w = word.lower()
                if w.isalpha() and w in vocab:
                    c[w] += 1
            pos_words[target] = [w for w, _ in c.most_common(per_pos_limit)]

        for pos, tag, relation in _INFLECTIONS:
            for w in pos_words[pos]:
                try:
                    forms = getInflection(w, tag=tag)
                except Exception:
                    forms = ()
                for f in forms:
                    yield RawTriple(
                        subject=w,
                        relation=relation,
                        object=f,
                        provenance=f"brown:{pos}",
                    )

        # Derivational morphology from WordNet lemma links.
        for s in wn.all_synsets(pos="v"):
            for lemma in s.lemmas():
                for d in lemma.derivationally_related_forms():
                    if d.synset().pos() != "n":
                        continue
                    name = d.name().lower()
                    if name.endswith(("er", "or", "ist")):
                        yield RawTriple(
                            subject=lemma.name(),
                            relation="agent_noun",
                            object=d.name(),
                        )

        for s in wn.all_synsets(pos="a"):
            for lemma in s.lemmas():
                for d in lemma.derivationally_related_forms():
                    if d.synset().pos() != "n":
                        continue
                    name = d.name().lower()
                    if name.endswith(("ness", "ity", "cy")):
                        yield RawTriple(
                            subject=lemma.name(),
                            relation="nominalization",
                            object=d.name(),
                        )

        # Adverb form: adjective → adverb via WordNet derivational links,
        # restricted to adverbs ending in "ly" (the productive morphology).
        # Authoritative source is WordNet's curated derivationally_related_forms.
        for s in wn.all_synsets(pos="r"):
            for lemma in s.lemmas():
                if not lemma.name().lower().endswith("ly"):
                    continue
                for d in lemma.derivationally_related_forms():
                    if d.synset().pos() != "a":
                        continue
                    yield RawTriple(
                        subject=d.name(),
                        relation="adverb_form",
                        object=lemma.name(),
                        provenance=s.name(),
                    )

        # Negation prefix: adjective → prefix-negated antonym. WordNet antonyms
        # are curated; we keep only the pairs where one is a morphological
        # prefix form of the other (filtering out semantic antonyms like hot/cold).
        neg_prefixes = ("un", "in", "im", "ir", "non", "dis")
        for s in wn.all_synsets(pos="a"):
            for lemma in s.lemmas():
                a_name = lemma.name().lower()
                for ant in lemma.antonyms():
                    b_name = ant.name().lower()
                    if any(b_name == pfx + a_name for pfx in neg_prefixes):
                        yield RawTriple(
                            subject=lemma.name(),
                            relation="negation_prefix",
                            object=ant.name(),
                            provenance=s.name(),
                        )
