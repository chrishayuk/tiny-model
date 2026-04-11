"""Parses tree-sitter grammars from raw_dir and yields structural triples.

Per language, emits:

* ``keyword_begins`` — alphabetic STRING terminal appearing in a rule body
* ``contains``       — parent construct to allowed child node type
* ``is_a``           — subtype to supertype (abstract categories)
* ``followed_by``    — adjacent members inside a SEQ
* ``delimiter_role`` — punctuation/operator role within a construct

All subjects and objects representing language-scoped symbols are prefixed
``<lang>/...`` so triples from different languages don't collide. Cross-
language analysis (universal keywords, Jaccard language families) is out
of scope for this extractor and belongs downstream.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterator

from ...base import BaseExtractor, DatasetMeta, RawTriple
from ...paths import default_raw_dir
from .model import META, TreeSitterLanguage, TreeSitterRawLayout, languages_for_tier


def _walk_rule(node: Any, visit) -> None:
    if not isinstance(node, dict):
        return
    visit(node)
    t = node.get("type")
    if t in ("SEQ", "CHOICE"):
        for m in node.get("members", []):
            _walk_rule(m, visit)
    elif t in (
        "REPEAT", "REPEAT1", "PREC", "PREC_LEFT", "PREC_RIGHT", "PREC_DYNAMIC",
        "FIELD", "ALIAS", "IMMEDIATE_TOKEN", "TOKEN",
    ):
        _walk_rule(node.get("content"), visit)


def _member_label(m: Any) -> str | None:
    if not isinstance(m, dict):
        return None
    t = m.get("type")
    if t == "STRING":
        return m.get("value")
    if t == "SYMBOL":
        return m.get("name")
    if t in ("FIELD", "ALIAS", "PREC", "PREC_LEFT", "PREC_RIGHT", "IMMEDIATE_TOKEN", "TOKEN"):
        return _member_label(m.get("content"))
    return None


def _is_keyword(value: str) -> bool:
    return bool(value) and value.isalpha() and len(value) <= 20


def _extract_from_node_types(
    node_types: list,
) -> tuple[list[tuple[str, str]], list[tuple[str, str]], list[tuple[str, str]]]:
    """Return (parent_child, field_pairs, supertype_pairs)."""
    parent_child: list[tuple[str, str]] = []
    field_pairs: list[tuple[str, str]] = []
    supertypes: list[tuple[str, str]] = []

    for node in node_types:
        if not isinstance(node, dict):
            continue
        name = node.get("type")
        if not name:
            continue

        for sub in node.get("subtypes") or []:
            st = sub.get("type")
            if st:
                supertypes.append((st, name))

        for field_name, field_info in (node.get("fields") or {}).items():
            for allowed in (field_info or {}).get("types") or []:
                at = allowed.get("type")
                if at:
                    field_pairs.append((f"{name}.{field_name}", at))

        children = node.get("children")
        if isinstance(children, dict):
            for allowed in children.get("types") or []:
                at = allowed.get("type")
                if at:
                    parent_child.append((name, at))

    return parent_child, field_pairs, supertypes


def _extract_from_grammar(
    grammar: dict,
) -> tuple[list[tuple[str, str]], list[tuple[str, str]], list[tuple[str, str]]]:
    """Return (keyword_pairs, sequence_pairs, delimiter_pairs)."""
    rules = grammar.get("rules") or {}
    keywords: list[tuple[str, str]] = []
    sequences: list[tuple[str, str]] = []
    delimiters: list[tuple[str, str]] = []

    DELIM_OPENS = {"(", "[", "{", "<"}
    DELIM_CLOSES = {")", "]", "}", ">"}

    for rule_name, rule_body in rules.items():
        skip_keywords = rule_name.startswith("_")

        def visit(n: dict, _rule_name: str = rule_name, _skip: bool = skip_keywords) -> None:
            t = n.get("type")
            if t == "SEQ":
                members = n.get("members", [])
                for a, b in zip(members, members[1:]):
                    av = _member_label(a)
                    bv = _member_label(b)
                    if av and bv:
                        sequences.append((av, bv))
            if t == "STRING":
                v = n.get("value", "")
                if v in DELIM_OPENS:
                    delimiters.append((v, f"opens:{_rule_name}"))
                elif v in DELIM_CLOSES:
                    delimiters.append((v, f"closes:{_rule_name}"))
                elif v == ",":
                    delimiters.append((v, f"separates:{_rule_name}"))
                elif v and not v.isalnum() and 1 <= len(v) <= 3 and not _skip:
                    delimiters.append((v, f"operator_in:{_rule_name}"))
                if not _skip and _is_keyword(v):
                    keywords.append((v, _rule_name))

        _walk_rule(rule_body, visit)

    return keywords, sequences, delimiters


def _read_json(path: Path) -> Any | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text())
    except Exception as e:
        print(f"[treesitter] unreadable {path}: {type(e).__name__}: {e}")
        return None


def _scoped(lang: str, symbol: str) -> str:
    return f"{lang}/{symbol}"


class TreeSitterExtractor(BaseExtractor):
    def meta(self) -> DatasetMeta:
        return META

    def _languages(self, config: dict) -> list[TreeSitterLanguage]:
        max_tier = config.get("max_tier")
        only = config.get("only")
        langs = languages_for_tier(max_tier)
        if only:
            names = set(only) if not isinstance(only, str) else {
                s.strip() for s in only.split(",") if s.strip()
            }
            langs = [lang for lang in langs if lang.name in names]
        return langs

    def extract(self, config: dict) -> Iterator[RawTriple]:
        base_raw = Path(config.get("raw_dir") or default_raw_dir())
        layout = TreeSitterRawLayout(raw_dir=base_raw / META.category / META.name)

        for lang in self._languages(config):
            node_types = _read_json(layout.node_types_path(lang.name))
            grammar = _read_json(layout.grammar_path(lang.name))

            if node_types is None and grammar is None:
                continue

            pc: list[tuple[str, str]] = []
            fields: list[tuple[str, str]] = []
            supertypes: list[tuple[str, str]] = []
            keywords: list[tuple[str, str]] = []
            sequences: list[tuple[str, str]] = []
            delimiters: list[tuple[str, str]] = []

            if isinstance(node_types, list):
                pc, fields, supertypes = _extract_from_node_types(node_types)
            if isinstance(grammar, dict):
                keywords, sequences, delimiters = _extract_from_grammar(grammar)

            for kw, construct in _dedupe(keywords):
                yield RawTriple(
                    subject=_scoped(lang.name, kw),
                    relation="keyword_begins",
                    object=_scoped(lang.name, construct),
                    provenance=lang.name,
                )
            for parent, child in _dedupe(pc + fields):
                yield RawTriple(
                    subject=_scoped(lang.name, parent),
                    relation="contains",
                    object=_scoped(lang.name, child),
                    provenance=lang.name,
                )
            for sub, sup in _dedupe(supertypes):
                yield RawTriple(
                    subject=_scoped(lang.name, sub),
                    relation="is_a",
                    object=_scoped(lang.name, sup),
                    provenance=lang.name,
                )
            for a, b in _dedupe(sequences):
                yield RawTriple(
                    subject=_scoped(lang.name, a),
                    relation="followed_by",
                    object=_scoped(lang.name, b),
                    provenance=lang.name,
                )
            for sym, role in _dedupe(delimiters):
                yield RawTriple(
                    subject=_scoped(lang.name, sym),
                    relation="delimiter_role",
                    object=_scoped(lang.name, role),
                    provenance=lang.name,
                )


def _dedupe(pairs: list[tuple[str, str]]) -> list[tuple[str, str]]:
    seen: set[tuple[str, str]] = set()
    out: list[tuple[str, str]] = []
    for p in pairs:
        if p in seen:
            continue
        seen.add(p)
        out.append(p)
    return out
