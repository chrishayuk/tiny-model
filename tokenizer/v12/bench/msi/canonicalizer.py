"""MSI canonicalizer — frozen, context-free deterministic transducer.

Maps a framed encoding (a sequence of token ids produced by tokenizing one
of the MSI frame-battery contexts) to a single canonical operand-id
sequence, without inspecting surrounding semantics. Per the design doc
(section 2.2), only class-3 (context-entangled) failures are fatal;
class-2 (losslessly canonicalizable) failures are priced via this
transducer, not treated as fatal.

This module ships in both Python and Rust (C7 merge-opacity /
Python-Rust parity requirement); the Rust counterpart does not exist yet
— TOK-1 candidates (and their real merge tables) are a prerequisite for
writing the actual class-2 collapsing rules on both sides.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class CanonicalizeResult:
    operand_ids: tuple
    segmentation_class: int  # 1 identical, 2 canonicalizable, 3 context-entangled
    failure_mode: str | None  # None, or one of: leading-space, merge-boundary,
                               # punctuation-absorption, delimiter-interaction


def canonicalize_identity(framed_ids, operand_ids):
    """Class-1 case: the framed encoding already contains operand_ids verbatim
    as a contiguous subsequence. Real, working — no tokenizer-specific
    knowledge required since class 1 is defined as exact id-level equality.
    """
    n = len(operand_ids)
    for start in range(len(framed_ids) - n + 1):
        if tuple(framed_ids[start:start + n]) == tuple(operand_ids):
            return CanonicalizeResult(tuple(operand_ids), 1, None)
    return None  # not class 1 — caller falls through to the class-2 transducer


def canonicalize(framed_ids, operand_ids, merge_table=None):
    """Full canonicalizer. `merge_table` is a per-candidate-tokenizer artifact
    (which merges absorbed which boundary) that does not exist until a TOK-1
    candidate is trained. Until then this only resolves the class-1 case.
    """
    hit = canonicalize_identity(framed_ids, operand_ids)
    if hit is not None:
        return hit
    if merge_table is None:
        raise NotImplementedError(
            "class-2 canonicalization requires a candidate's merge_table; "
            "none available until TOK-1 candidates exist"
        )
    raise NotImplementedError("class-2 collapsing-merge resolution: TODO once merge_table format is pinned")
