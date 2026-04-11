"""Reads the WordNet NLTK corpus and yields raw triples.

Covers the full set of WordNet relations: synonyms, hypernyms, hyponyms,
antonyms, meronyms/holonyms (part/substance/member), troponyms, entailments,
causes, also_see, similar_to, pertainyms, derivations, and the three domain
relations (topic, region, usage).
"""

from __future__ import annotations

from itertools import combinations
from pathlib import Path
from typing import Iterator

from ...base import BaseExtractor, DatasetMeta, RawTriple
from ...paths import default_raw_dir, setup_nltk_data_dir
from .model import META


def _lemmas(synset) -> list[str]:
    return [lemma.name() for lemma in synset.lemmas()]


class WordNetExtractor(BaseExtractor):
    def meta(self) -> DatasetMeta:
        return META

    def extract(self, config: dict) -> Iterator[RawTriple]:
        raw_dir = Path(config.get("raw_dir") or default_raw_dir())
        setup_nltk_data_dir(raw_dir)
        from nltk.corpus import wordnet as wn  # type: ignore

        synsets = list(wn.all_synsets())

        # Synonyms: all lemma pairs within a synset.
        for s in synsets:
            ls = _lemmas(s)
            for a, b in combinations(ls, 2):
                yield RawTriple(
                    subject=a, relation="synonyms", object=b, provenance=s.name()
                )

        # Synset-level edges to lexical pairs.
        synset_edges = [
            ("hypernyms", "hypernyms"),
            ("hyponyms", "hyponyms"),
            ("part_meronyms", "meronyms_part"),
            ("substance_meronyms", "meronyms_substance"),
            ("member_meronyms", "meronyms_member"),
            ("part_holonyms", "holonyms_part"),
            ("substance_holonyms", "holonyms_substance"),
            ("member_holonyms", "holonyms_member"),
            ("entailments", "entailments"),
            ("causes", "causes"),
            ("also_sees", "also_see"),
            ("similar_tos", "similar_to"),
            ("topic_domains", "domain_topic"),
            ("region_domains", "domain_region"),
            ("usage_domains", "domain_usage"),
        ]
        for method, relation in synset_edges:
            for s in synsets:
                related = getattr(s, method, lambda: [])()
                if not related:
                    continue
                src = _lemmas(s)
                for r in related:
                    for a in src:
                        for b in _lemmas(r):
                            yield RawTriple(
                                subject=a,
                                relation=relation,
                                object=b,
                                provenance=s.name(),
                            )

        # Troponyms = verb hyponyms. Reuse the materialised synset list.
        for s in synsets:
            if s.pos() != "v":
                continue
            for r in s.hyponyms():
                for a in _lemmas(s):
                    for b in _lemmas(r):
                        yield RawTriple(
                            subject=a,
                            relation="troponyms",
                            object=b,
                            provenance=s.name(),
                        )

        # Lemma-level edges: antonyms, derivations, pertainyms.
        lemma_edges = [
            ("antonyms", "antonyms"),
            ("derivationally_related_forms", "derivations"),
            ("pertainyms", "pertainyms"),
        ]
        for s in synsets:
            for lemma in s.lemmas():
                for method, relation in lemma_edges:
                    related = getattr(lemma, method, lambda: [])()
                    for r in related:
                        yield RawTriple(
                            subject=lemma.name(),
                            relation=relation,
                            object=r.name(),
                            provenance=s.name(),
                        )
