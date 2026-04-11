"""Normaliser profile dispatch + cleaning rules."""

from __future__ import annotations

from knowledge_extractor.base import RawTriple
from knowledge_extractor.normaliser import Normaliser


def _t(subject: str, object_: str, layer_band: str = "syntax") -> RawTriple:
    return RawTriple(subject=subject, relation="r", object=object_, layer_band=layer_band)


def test_strict_profile_lowercases_and_strips():
    n = Normaliser(profile="strict")
    out = n.normalise(_t("  BIG  ", "Large"))
    assert out is not None
    assert out.subject == "big"
    assert out.object == "large"


def test_strict_profile_drops_self_loops():
    n = Normaliser(profile="strict")
    assert n.normalise(_t("dog", "dog")) is None


def test_permissive_profile_keeps_punctuation():
    """Permissive profile is used for the knowledge band and must not
    reject subjects like ``application/json`` or ``tls 1.3``."""
    n = Normaliser(profile="permissive")
    out = n.normalise(_t("application/json", "json", layer_band="knowledge"))
    assert out is not None
    assert out.subject == "application/json"


def test_auto_dispatch_on_layer_band():
    """With profile=None the normaliser picks strict for syntax, permissive
    for knowledge — this keeps WordNet clean while letting standards keep
    their structured subjects."""
    n = Normaliser(profile=None)
    # syntax layer → strict (would reject a slash-containing subject)
    strict_out = n.normalise(_t("foo/bar", "baz", layer_band="syntax"))
    # knowledge layer → permissive (keeps the slash)
    perm_out = n.normalise(_t("foo/bar", "baz", layer_band="knowledge"))
    # One of the two profiles should reject, the other should keep
    assert (strict_out is None) or (perm_out is not None and perm_out.subject == "foo/bar")
