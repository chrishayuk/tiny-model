"""Pure grammar-walking helpers in the tree-sitter extractor.

No grammars are downloaded; we hand-build small rule dicts that exercise
each path through the walker.
"""

from __future__ import annotations

from knowledge_extractor.ast.treesitter.extractor import (
    _extract_from_grammar,
    _extract_from_node_types,
    _is_keyword,
    _member_label,
)


# ---------- _is_keyword -------------------------------------------------


def test_is_keyword_accepts_alpha():
    assert _is_keyword("def") is True
    assert _is_keyword("return") is True


def test_is_keyword_rejects_symbols_and_numbers():
    assert _is_keyword("") is False
    assert _is_keyword("==") is False
    assert _is_keyword("123") is False


def test_is_keyword_rejects_too_long():
    assert _is_keyword("x" * 21) is False


# ---------- _member_label -----------------------------------------------


def test_member_label_string():
    assert _member_label({"type": "STRING", "value": "fn"}) == "fn"


def test_member_label_symbol():
    assert _member_label({"type": "SYMBOL", "name": "identifier"}) == "identifier"


def test_member_label_unwraps_field():
    wrapped = {
        "type": "FIELD",
        "content": {"type": "STRING", "value": "return"},
    }
    assert _member_label(wrapped) == "return"


# ---------- _extract_from_node_types -----------------------------------


def test_extract_from_node_types_supertypes():
    node_types = [
        {
            "type": "statement",
            "subtypes": [
                {"type": "if_statement"},
                {"type": "for_statement"},
            ],
        }
    ]
    pc, fields, super_ = _extract_from_node_types(node_types)
    assert ("if_statement", "statement") in super_
    assert ("for_statement", "statement") in super_


def test_extract_from_node_types_fields_and_children():
    node_types = [
        {
            "type": "function_definition",
            "fields": {
                "name": {"types": [{"type": "identifier"}]},
                "parameters": {"types": [{"type": "parameter_list"}]},
            },
            "children": {"types": [{"type": "block"}]},
        }
    ]
    pc, fields, super_ = _extract_from_node_types(node_types)
    assert ("function_definition.name", "identifier") in fields
    assert ("function_definition.parameters", "parameter_list") in fields
    assert ("function_definition", "block") in pc


def test_extract_from_node_types_skips_non_dict():
    pc, fields, super_ = _extract_from_node_types(["not a dict", {"type": "x"}])
    assert (pc, fields, super_) == ([], [], [])


# ---------- _extract_from_grammar --------------------------------------


def _rule(*members):
    return {"type": "SEQ", "members": list(members)}


def test_extract_from_grammar_keywords():
    grammar = {
        "rules": {
            "function_definition": _rule(
                {"type": "STRING", "value": "def"},
                {"type": "SYMBOL", "name": "identifier"},
            )
        }
    }
    keywords, _sequences, _delims = _extract_from_grammar(grammar)
    assert ("def", "function_definition") in keywords


def test_extract_from_grammar_skips_private_rules():
    """Rules with names starting ``_`` don't emit keywords."""
    grammar = {
        "rules": {
            "_private": _rule({"type": "STRING", "value": "hidden"}),
        }
    }
    keywords, _, _ = _extract_from_grammar(grammar)
    assert keywords == []


def test_extract_from_grammar_sequences():
    grammar = {
        "rules": {
            "function_definition": _rule(
                {"type": "STRING", "value": "def"},
                {"type": "SYMBOL", "name": "identifier"},
                {"type": "STRING", "value": "("},
                {"type": "STRING", "value": ")"},
            )
        }
    }
    _kw, sequences, _delims = _extract_from_grammar(grammar)
    assert ("def", "identifier") in sequences
    assert ("identifier", "(") in sequences
    assert ("(", ")") in sequences


def test_extract_from_grammar_delimiters():
    grammar = {
        "rules": {
            "function_call": _rule(
                {"type": "STRING", "value": "("},
                {"type": "STRING", "value": ")"},
                {"type": "STRING", "value": ","},
            )
        }
    }
    _kw, _seq, delimiters = _extract_from_grammar(grammar)
    d = dict(delimiters)
    assert d["("] == "opens:function_call"
    assert d[")"] == "closes:function_call"
    assert d[","] == "separates:function_call"
