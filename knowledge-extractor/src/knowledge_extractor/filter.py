"""Quality filter for normalised triples."""

from __future__ import annotations

from .base import RawTriple
from .tokeniser_check import TokeniserCheck


class Filter:
    def __init__(
        self,
        config: dict | None = None,
        tokeniser: TokeniserCheck | None = None,
    ):
        config = config or {}
        self.min_confidence = config.get("min_confidence", 0.0)
        self.max_subject_length = config.get("max_subject_length", 200)
        self.max_object_length = config.get("max_object_length", 200)
        self.tokeniser = tokeniser

    def accept(self, t: RawTriple) -> bool:
        if t.confidence < self.min_confidence:
            return False
        if len(t.subject) > self.max_subject_length:
            return False
        if len(t.object) > self.max_object_length:
            return False
        if self.tokeniser is not None and not self.tokeniser.accepts(t):
            return False
        return True
