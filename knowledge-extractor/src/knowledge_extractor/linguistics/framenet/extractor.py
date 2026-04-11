"""Reads the FrameNet corpus and yields raw triples.

Emits:

* ``evokes_frame``  (word, frame_name)     — lexical unit to frame
* ``frame_parent``  (parent_frame, child)  — inter-frame hierarchy
* ``frame_element`` (frame_name, element)  — each frame's roles
* ``frame_lexicon`` (frame_name, word)     — frame back to its lemmas
"""

from __future__ import annotations

from pathlib import Path
from typing import Iterator

from ...base import BaseExtractor, DatasetMeta, RawTriple
from ...paths import default_raw_dir, setup_nltk_data_dir
from .model import META


class FrameNetExtractor(BaseExtractor):
    def meta(self) -> DatasetMeta:
        return META

    def extract(self, config: dict) -> Iterator[RawTriple]:
        raw_dir = Path(config.get("raw_dir") or default_raw_dir())
        setup_nltk_data_dir(raw_dir)
        from nltk.corpus import framenet as fn  # type: ignore

        for frame in fn.frames():
            frame_name = frame.name
            for lu in frame.lexUnit.values():
                word = lu.name.split(".")[0]
                yield RawTriple(
                    subject=word,
                    relation="evokes_frame",
                    object=frame_name,
                    provenance=frame_name,
                )
                yield RawTriple(
                    subject=frame_name,
                    relation="frame_lexicon",
                    object=word,
                    provenance=frame_name,
                )
            for fe in frame.FE.values():
                yield RawTriple(
                    subject=frame_name,
                    relation="frame_element",
                    object=fe.name,
                    provenance=f"{frame_name}/{fe.coreType}",
                )

        for rel in fn.frame_relations():
            parent = getattr(rel, "superFrameName", None)
            child = getattr(rel, "subFrameName", None)
            if not parent or not child:
                continue
            rel_type = getattr(rel.type, "name", "related")
            yield RawTriple(
                subject=parent,
                relation="frame_parent",
                object=child,
                provenance=rel_type,
            )
