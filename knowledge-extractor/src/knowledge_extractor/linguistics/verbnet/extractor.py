"""Reads the VerbNet corpus and yields raw triples.

Emits:

* ``member_of_class`` (verb, classid)
* ``has_role``        (classid, role_type)
* ``has_frame``       (classid, frame_description)
* ``selrestr_pos``    (classid/role, restriction)  — role must have trait
* ``selrestr_neg``    (classid/role, restriction)  — role must not have trait
"""

from __future__ import annotations

from pathlib import Path
from typing import Iterator

from ...base import BaseExtractor, DatasetMeta, RawTriple
from ...paths import default_raw_dir, setup_nltk_data_dir
from .model import META


class VerbNetExtractor(BaseExtractor):
    def meta(self) -> DatasetMeta:
        return META

    def extract(self, config: dict) -> Iterator[RawTriple]:
        raw_dir = Path(config.get("raw_dir") or default_raw_dir())
        setup_nltk_data_dir(raw_dir)
        from nltk.corpus import verbnet as vn  # type: ignore

        for classid in vn.classids():
            for lemma in vn.lemmas(classid):
                yield RawTriple(
                    subject=lemma,
                    relation="member_of_class",
                    object=classid,
                    provenance=classid,
                )

            for role in vn.themroles(classid):
                role_type = role.get("type")
                if not role_type:
                    continue
                yield RawTriple(
                    subject=classid,
                    relation="has_role",
                    object=role_type,
                    provenance=classid,
                )
                for restr in role.get("modifiers", []) or []:
                    r_type = restr.get("type")
                    if not r_type:
                        continue
                    polarity = restr.get("value", "+")
                    relation = "selrestr_neg" if polarity == "-" else "selrestr_pos"
                    yield RawTriple(
                        subject=f"{classid}/{role_type}",
                        relation=relation,
                        object=r_type,
                        provenance=classid,
                    )

            for frame in vn.frames(classid):
                description = frame.get("description", {}).get("primary", "")
                if description:
                    yield RawTriple(
                        subject=classid,
                        relation="has_frame",
                        object=description,
                        provenance=classid,
                    )
