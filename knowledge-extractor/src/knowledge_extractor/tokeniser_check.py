"""Optional HuggingFace tokeniser coverage check.

A triple passes the coverage check iff both subject and object are tokenised
into at most ``max_tokens`` pieces by the target tokeniser. This is how we
keep compiled edges from blowing up the FFN width by resolving to fragments
that no single token covers.
"""

from __future__ import annotations

from .base import RawTriple


class TokeniserCheck:
    def __init__(self, model_name: str, max_tokens: int = 3):
        try:
            from transformers import AutoTokenizer  # type: ignore
        except ImportError as e:
            raise RuntimeError(
                "tokeniser_check requires `transformers`. "
                "install the `tokeniser` extra: `uv add transformers`."
            ) from e
        self.tok = AutoTokenizer.from_pretrained(model_name)
        self.max_tokens = max_tokens
        self._cache: dict[str, int] = {}

    def _count(self, text: str) -> int:
        n = self._cache.get(text)
        if n is None:
            n = len(self.tok.encode(text, add_special_tokens=False))
            self._cache[text] = n
        return n

    def accepts(self, t: RawTriple) -> bool:
        return (
            self._count(t.subject) <= self.max_tokens
            and self._count(t.object) <= self.max_tokens
        )
