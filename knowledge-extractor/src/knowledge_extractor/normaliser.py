"""Text normalisation profiles for raw triples.

Two profiles:

* ``strict`` — syntax band. Lowercase, allow letters/spaces/hyphens/apostrophes
  only. No digits. Drop self-loops. Used for WordNet, morphology, framenet, etc.
* ``permissive`` — knowledge band. Lowercase, allow letters/digits/spaces and
  a modest set of punctuation. Preserves things like "http 200", "utf-8",
  "cve-2024-1234" that matter for standards/errors/stackoverflow.

Pick a profile per dataset via the extractor's ``layer_band`` (strict for
syntax, permissive for knowledge) or override via runner config.
"""

from __future__ import annotations

from .base import RawTriple


_STRICT_ALLOWED = {" ", "-", "'"}
_PERMISSIVE_ALLOWED = {" ", "-", "'", ".", "_", "/", "+", ":"}


def _clean(text: str, allowed: set[str], allow_digits: bool) -> str | None:
    if not text:
        return None
    text = text.replace("_", " ") if "_" not in allowed else text
    text = text.strip().lower()
    if not text:
        return None
    for ch in text:
        if ch.isalpha():
            continue
        if allow_digits and ch.isdigit():
            continue
        if ch in allowed:
            continue
        return None
    return text


def clean_strict(text: str) -> str | None:
    return _clean(text, _STRICT_ALLOWED, allow_digits=False)


def clean_permissive(text: str) -> str | None:
    return _clean(text, _PERMISSIVE_ALLOWED, allow_digits=True)


class Normaliser:
    """Dispatches to a profile based on triple.layer_band unless forced."""

    def __init__(self, profile: str | None = None):
        self.forced_profile = profile  # None | "strict" | "permissive"

    def _profile_for(self, t: RawTriple) -> str:
        if self.forced_profile:
            return self.forced_profile
        return "strict" if t.layer_band == "syntax" else "permissive"

    def normalise(self, t: RawTriple) -> RawTriple | None:
        profile = self._profile_for(t)
        clean = clean_strict if profile == "strict" else clean_permissive
        s = clean(t.subject)
        o = clean(t.object)
        if s is None or o is None:
            return None
        if s == o:
            return None
        return RawTriple(
            subject=s,
            object=o,
            relation=t.relation,
            confidence=t.confidence,
            provenance=t.provenance,
            source=t.source,
            layer_band=t.layer_band,
        )
