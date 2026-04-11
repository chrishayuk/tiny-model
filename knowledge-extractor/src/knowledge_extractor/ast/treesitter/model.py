"""Shared contract between the tree-sitter downloader and extractor.

The downloader fetches ``grammar.json`` and ``node-types.json`` for each
language in :data:`LANGUAGES` from its canonical tree-sitter repository
and stores them under ``<raw_dir>/ast/treesitter/<lang>/``.

The extractor reads those files and yields relation triples keyed by a
``<lang>/<symbol>`` subject so per-language scope survives the flat triple
stream without requiring a separate output dataset per language.

Cross-language analysis (universal keywords, keyword translation tables,
language families by Jaccard similarity) is intentionally NOT part of this
extractor; it belongs as a downstream step that reads the extracted triples.
"""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, ConfigDict

from ...base import DatasetMeta, RawLayout


META = DatasetMeta(
    name="treesitter",
    category="ast",
    version="grammars-2026-04",
    license="per-grammar (MIT/Apache/BSD, see each repo)",
    url="https://tree-sitter.github.io/",
    layer_band="syntax",
    description="Per-language AST structure from tree-sitter grammar definitions",
)


BRANCHES = ("master", "main")
RAW_URL = "https://raw.githubusercontent.com/{owner}/{repo}/{branch}/{path}"
GRAMMAR_FILES = ("node-types.json", "grammar.json")


class TreeSitterLanguage(BaseModel):
    """A single language entry in the curated grammar registry."""

    model_config = ConfigDict(extra="forbid")

    name: str
    owner: str
    repo: str
    src: str
    tier: int


def _lang(name: str, owner: str, repo: str, src: str, tier: int) -> TreeSitterLanguage:
    return TreeSitterLanguage(name=name, owner=owner, repo=repo, src=src, tier=tier)


LANGUAGES: list[TreeSitterLanguage] = [
    # ---- Tier 1 ---------------------------------------------------------
    _lang("python",     "tree-sitter",          "tree-sitter-python",     "src", 1),
    _lang("javascript", "tree-sitter",          "tree-sitter-javascript", "src", 1),
    _lang("typescript", "tree-sitter",          "tree-sitter-typescript", "typescript/src", 1),
    _lang("tsx",        "tree-sitter",          "tree-sitter-typescript", "tsx/src", 1),
    _lang("java",       "tree-sitter",          "tree-sitter-java",       "src", 1),
    _lang("c",          "tree-sitter",          "tree-sitter-c",          "src", 1),
    _lang("cpp",        "tree-sitter",          "tree-sitter-cpp",        "src", 1),
    _lang("csharp",     "tree-sitter",          "tree-sitter-c-sharp",    "src", 1),
    _lang("go",         "tree-sitter",          "tree-sitter-go",         "src", 1),
    _lang("rust",       "tree-sitter",          "tree-sitter-rust",       "src", 1),
    _lang("ruby",       "tree-sitter",          "tree-sitter-ruby",       "src", 1),
    _lang("php",        "tree-sitter",          "tree-sitter-php",        "php/src", 1),
    _lang("swift",      "alex-pinkus",          "tree-sitter-swift",      "src", 1),
    _lang("kotlin",     "fwcd",                 "tree-sitter-kotlin",     "src", 1),
    _lang("scala",      "tree-sitter",          "tree-sitter-scala",      "src", 1),
    _lang("r",          "r-lib",                "tree-sitter-r",          "src", 1),
    _lang("bash",       "tree-sitter",          "tree-sitter-bash",       "src", 1),
    _lang("sql",        "derekstride",          "tree-sitter-sql",        "src", 1),
    _lang("html",       "tree-sitter",          "tree-sitter-html",       "src", 1),
    _lang("css",        "tree-sitter",          "tree-sitter-css",        "src", 1),
    _lang("markdown",   "tree-sitter-grammars", "tree-sitter-markdown",   "tree-sitter-markdown/src", 1),
    # ---- Tier 2 ---------------------------------------------------------
    _lang("lua",        "tree-sitter-grammars", "tree-sitter-lua",        "src", 2),
    _lang("perl",       "tree-sitter-perl",     "tree-sitter-perl",       "src", 2),
    _lang("haskell",    "tree-sitter",          "tree-sitter-haskell",    "src", 2),
    _lang("elixir",     "elixir-lang",          "tree-sitter-elixir",     "src", 2),
    _lang("clojure",    "sogaiu",               "tree-sitter-clojure",    "src", 2),
    _lang("dart",       "UserNobody14",         "tree-sitter-dart",       "src", 2),
    _lang("julia",      "tree-sitter",          "tree-sitter-julia",      "src", 2),
    _lang("objc",       "tree-sitter-grammars", "tree-sitter-objc",       "src", 2),
    _lang("groovy",     "murtaza64",            "tree-sitter-groovy",     "src", 2),
    _lang("powershell", "airbus-cert",          "tree-sitter-powershell", "src", 2),
    _lang("dockerfile", "camdencheek",          "tree-sitter-dockerfile", "src", 2),
    _lang("yaml",       "tree-sitter-grammars", "tree-sitter-yaml",       "src", 2),
    _lang("json",       "tree-sitter",          "tree-sitter-json",       "src", 2),
    _lang("toml",       "tree-sitter-grammars", "tree-sitter-toml",       "src", 2),
    _lang("xml",        "tree-sitter-grammars", "tree-sitter-xml",        "xml/src", 2),
    _lang("latex",      "latex-lsp",            "tree-sitter-latex",      "src", 2),
    _lang("make",       "alemuller",            "tree-sitter-make",       "src", 2),
    _lang("cmake",      "uyha",                 "tree-sitter-cmake",      "src", 2),
    _lang("zig",        "tree-sitter-grammars", "tree-sitter-zig",        "src", 2),
    # ---- Tier 3 ---------------------------------------------------------
    _lang("ocaml",      "tree-sitter",            "tree-sitter-ocaml",      "grammars/ocaml/src", 3),
    _lang("erlang",     "WhatsApp",               "tree-sitter-erlang",     "src", 3),
    _lang("fsharp",     "ionide",                 "tree-sitter-fsharp",     "fsharp/src", 3),
    _lang("elm",        "elm-tooling",            "tree-sitter-elm",        "src", 3),
    _lang("nim",        "alaviss",                "tree-sitter-nim",        "src", 3),
    _lang("crystal",    "crystal-lang-tools",     "tree-sitter-crystal",    "src", 3),
    _lang("nix",        "nix-community",          "tree-sitter-nix",        "src", 3),
    _lang("solidity",   "JoranHonig",             "tree-sitter-solidity",   "src", 3),
    _lang("vue",        "tree-sitter-grammars",   "tree-sitter-vue",        "src", 3),
    _lang("svelte",     "tree-sitter-grammars",   "tree-sitter-svelte",     "src", 3),
    _lang("scheme",     "6cdh",                   "tree-sitter-scheme",     "src", 3),
    _lang("commonlisp", "tree-sitter-grammars",   "tree-sitter-commonlisp", "src", 3),
    _lang("racket",     "6cdh",                   "tree-sitter-racket",     "src", 3),
    _lang("fish",       "ram02z",                 "tree-sitter-fish",       "src", 3),
    _lang("awk",        "Beaglefoot",             "tree-sitter-awk",        "src", 3),
    _lang("verilog",    "tree-sitter",            "tree-sitter-verilog",    "src", 3),
    _lang("vhdl",       "alemuller",              "tree-sitter-vhdl",       "src", 3),
    _lang("cuda",       "tree-sitter-grammars",   "tree-sitter-cuda",       "src", 3),
    _lang("glsl",       "tree-sitter-grammars",   "tree-sitter-glsl",       "src", 3),
    _lang("hlsl",       "tree-sitter-grammars",   "tree-sitter-hlsl",       "src", 3),
    _lang("wgsl",       "szebniok",               "tree-sitter-wgsl",       "src", 3),
    _lang("protobuf",   "mitchellh",              "tree-sitter-proto",      "src", 3),
    _lang("graphql",    "bkegley",                "tree-sitter-graphql",    "src", 3),
    _lang("terraform",  "MichaHoffmann",          "tree-sitter-hcl",        "src", 3),
    _lang("hcl",        "MichaHoffmann",          "tree-sitter-hcl",        "src", 3),
    _lang("jq",         "flurie",                 "tree-sitter-jq",         "src", 3),
    _lang("vim",        "neovim",                 "tree-sitter-vim",        "src", 3),
    _lang("regex",      "tree-sitter",            "tree-sitter-regex",      "src", 3),
    _lang("embeddedtemplate", "tree-sitter",      "tree-sitter-embedded-template", "src", 3),
    _lang("jsdoc",      "tree-sitter",            "tree-sitter-jsdoc",      "src", 3),
    _lang("tlaplus",    "tlaplus-community",      "tree-sitter-tlaplus",    "src", 3),
    _lang("ada",        "briot",                  "tree-sitter-ada",        "src", 3),
    _lang("fortran",    "stadelmanma",            "tree-sitter-fortran",    "src", 3),
    _lang("cobol",      "yutaro-sakamoto",        "tree-sitter-cobol",      "src", 3),
    _lang("pascal",     "Isopod",                 "tree-sitter-pascal",     "src", 3),
    _lang("prolog",     "foxyseta",               "tree-sitter-prolog",     "grammars/prolog/src", 3),
    _lang("smalltalk",  "tree-sitter-grammars",   "tree-sitter-smalltalk",  "src", 3),
]


LANGUAGES_BY_NAME: dict[str, TreeSitterLanguage] = {lang.name: lang for lang in LANGUAGES}


def languages_for_tier(max_tier: int | None) -> list[TreeSitterLanguage]:
    if max_tier is None:
        return list(LANGUAGES)
    return [lang for lang in LANGUAGES if lang.tier <= max_tier]


class TreeSitterRawLayout(RawLayout):
    """Raw layout: one folder per language, each with the two grammar files."""

    def language_dir(self, lang: str) -> Path:
        return self.raw_dir / lang

    def grammar_path(self, lang: str) -> Path:
        return self.language_dir(lang) / "grammar.json"

    def node_types_path(self, lang: str) -> Path:
        return self.language_dir(lang) / "node-types.json"

    def has_language(self, lang: str) -> bool:
        """A language is usable if at least one of the two grammar files exists."""
        return self.grammar_path(lang).exists() or self.node_types_path(lang).exists()

    def verify(self) -> bool:
        if not self.raw_dir.exists():
            return False
        # Don't require every language — just the tier 1 set, which is what
        # the default selection runs. Other tiers opt in via --tier.
        for lang in LANGUAGES:
            if lang.tier == 1 and not self.has_language(lang.name):
                return False
        return True
