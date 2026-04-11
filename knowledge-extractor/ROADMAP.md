# Roadmap

Living document. Tracks what ships in each tier, what's blocked, and what's
still a design question. See [SPEC.md](./SPEC.md) for architecture; this
file is about sequencing and scope.

## Status at a glance

|                  | registered | runnable | target | note                        |
|------------------|-----------:|---------:|-------:|-----------------------------|
| framework        |          — |        ✓ |      — | base, runner, cli, filter   |
| tier 1           |      5 / 8 |    4 / 8 |      8 | morphology blocked by env   |
| tier 2           |     0 / 10 |        — |     10 | next milestone              |
| tier 3           |      0 / 7 |        — |      7 |                             |
| ast languages    |          0 |        — |   ~248 | one extractor, many outputs |
| **total pairs**  |      1.24M |    1.24M |  ~14M  | sample committed            |

## Done

### Framework (v0.2.0)
- `BaseExtractor` contract, `RawTriple`, `DatasetMeta`
- `Normaliser` with `strict` / `permissive` profiles (auto-dispatch on `layer_band`)
- `Filter` with optional `TokeniserCheck` (HF tokeniser, cached)
- `TripleWriter` — atomic per-relation JSON with dedup
- `PipelineRunner` — one-dataset and batch modes, global manifest
- Lazy registry (`"module:Class"` strings; `list` survives missing deps)
- CLI: `list`, `extract` (dataset / --tier / --category / --all / --config), `stats`, `verify`
- Examples: runnable end-to-end demo + trimmed sample output (34 files, 641 pairs)

### Extractors
| key | relations | pairs (full run) | notes |
|---|---:|---:|---|
| `linguistics/wordnet` | 20 | 1,193,747 | NLTK; covers all WN relation types |
| `linguistics/framenet` | 4 | 38,707 | NLTK framenet_v17 |
| `linguistics/verbnet` | 3 | 6,852 | NLTK verbnet |
| `linguistics/morphology` | 9 | ~35,000 (est) | lemminflect + WN; **blocked on broken spacy/numpy in dev env**, code is ready |
| `domain/standards` | 7 | 127 | hand-curated IANA tables, zero deps |

## Near term — finish tier 1

Priority order (quick wins first):

1. **`domain/errors`** — per-language compiler/interpreter error tables.
   Start with Python (`errno`, `builtins.__dict__`, scraping cpython `Doc/library/exceptions.rst`) and Rust (`rustc --explain` index). Shape: `error_code → message`, `error → category`.
2. **`domain/cli`** — man pages. Parse troff via `man -w` + `groff -Tutf8`. Shape: `command → flag`, `command → description`, `flag → description`.
3. **`domain/api_docs`** — Python stdlib by walking `sys.modules` + `inspect`; Rust `std` via `rustdoc --output-format json`. Shape: `function → module`, `module → submodule`, `function → return_type`.
4. **`knowledge/wikidata`** — SPARQL endpoint only (no 71GB dump). Start with ~20 top properties (`P31`, `P279`, `P36`, `P17`, `P131`, ...). Shape is already defined in the spec.
5. **`ast`** — tree-sitter harness. Needs the pack to be wired. Generates keyword / parent-child / supertype triples per language. Target 10 canonical languages first (py, js, ts, rs, go, c, cpp, java, cs, rb), then extend.

Acceptance for tier 1 complete: `extract --tier 1` produces ≥2M pairs from 8 datasets on a clean install.

## Medium term — tier 2

Datasets requiring meaningful downloads but nothing planetary:

- `linguistics/collocations` (Brown bigrams, adj+noun, verb+object)
- `knowledge/dbpedia` (mappingbased objects)
- `knowledge/geonames` (allCountries.zip, ~300MB)
- `knowledge/imdb` (title.basics + title.principals, ~1GB)
- `knowledge/unicode` (CLDR/Unicode tables, currencies, emoji names)
- `domain/stackoverflow` (Posts.xml, ~60GB → streaming XML parse)
- `domain/openapi` (APIs.guru registry)
- `domain/changelogs` (parse common CHANGELOG.md formats for 100+ popular libs)

Acceptance: `--tier 2` completes in <12h on a laptop, yields ≥5M pairs.

## Long term — tier 3

Heavy downloads, long processing, dedicated runs:

- `knowledge/osm` — Geofabrik extracts, amenities/transport/historic
- `knowledge/musicbrainz` — Postgres dump ingest
- `knowledge/pubchem` — REST API, many requests, rate-limited
- `knowledge/taxonomy` — GBIF backbone
- `domain/medical/pubmed` — 35M abstracts, MeSH triples
- `domain/medical/clinical_trials` — interventions/conditions
- `domain/config_schemas` — k8s openapi, terraform providers, docker compose

Acceptance: each runs independently; no tier 3 dataset blocks another.

## AST expansion

`ast` is one extractor with 248 language outputs. Phasing:
- **Phase A (10 languages)**: py, js, ts, rs, go, c, cpp, java, cs, rb. Covers ~80% of real-world code.
- **Phase B (~50 languages)**: swift, kotlin, scala, php, lua, haskell, ocaml, elixir, dart, zig, nim, julia, ... and the common markup/config (html, css, json, yaml, toml, xml, sql, graphql, bash).
- **Phase C (tail)**: everything else tree-sitter supports.

Per-language output path: `datasets/extracted/ast/<lang>/{keywords,parent_child,supertypes,sequences,delimiters}.json`.
Cross-language summary: `datasets/extracted/ast/_cross_language/`.

## Known issues

- **Morphology blocked locally**: `lemminflect` → `spacy` → `thinc` hits a numpy ABI mismatch in the dev env. Fix by pinning numpy <2 or rebuilding thinc. Not a framework bug.
- **CLI shadowing**: another `knowledge_extractor` package exists at `/Users/christopherhay/chris-source/larql/knowledge/` on this machine. `python3 -m knowledge_extractor.cli` can pick the wrong one. Fix by installing this project to a fresh venv or renaming the import root.
- **Registry is static**: extractor keys are declared in `registry.py`. Entry-point based discovery would be nicer for out-of-tree extractors; defer until someone actually needs it.

## Open design questions

- **Sharding large relations.** `wordnet/hypernyms` is 300K+ pairs today; what's the target shard size before compilation gets unhappy? Options: leave as one file, split by first letter, split by pair count. Blocked on compiler side.
- **Relation name canonicalisation.** Different extractors can call similar things different names (`synonyms` vs `similar`, `hypernyms` vs `is_a`). Should there be a relation alias table, or does the compiler handle it? Lean: compiler handles it, extractors stay source-faithful.
- **Tokeniser coverage as filter vs annotation.** Right now `TokeniserCheck` drops a triple. It could instead annotate `confidence` so the compiler decides. Punt until we see real compilation behaviour on borderline pairs.
- **Provenance fidelity.** Today `provenance` is a single string. For stackoverflow/pubmed we'll want (doc_id, span) tuples. Upgrade when the first extractor needs it, not before.
- **Multilingual.** v0.2 is English-only. Multilingual means vocab contamination risk in the syntax band — decide after the first compile actually uses this data.

## Out of scope (for now)

- Web scraping with selenium/playwright — every planned source has a structured download or API.
- Licence filtering — assumed handled upstream at ingest time.
- Incremental / resumable runs — current design is idempotent-by-rerun, which is good enough until individual extractors cross the 30-minute mark.
- Format converters (RDF, Neo4j, etc.) — the JSON triple files are the interchange format.

## Changelog

- **2026-04-11** — repo cleanup: datasets moved to `<monorepo>/datasets/{raw,extracted}/`, NLTK redirected into the project tree, `raw_dir` threaded through the runner, CLI gains `--raw-dir`, env vars `KNOWLEDGE_RAW_DIR`/`KNOWLEDGE_EXTRACTED_DIR` honoured.
- **2026-04-11** — roadmap created; tier 1 at 5/8 registered, 4/8 runnable, 1.24M pairs sampled.
- **2026-04-10** — v0.2.0 framework + linguistics/{wordnet,framenet,verbnet,morphology} + domain/standards; lazy registry; normaliser profiles; token-coverage filter.
