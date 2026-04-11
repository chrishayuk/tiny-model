# Roadmap

Living document. Tracks what ships in each tier, what's blocked, and what's
still a design question. See [SPEC.md](./SPEC.md) for architecture; this
file is about sequencing and scope.

## Status at a glance

|                  | registered | target | note                             |
|------------------|-----------:|-------:|----------------------------------|
| framework        |          ✓ |      — | base split into downloader/extractor phases |
| tier 1           |      8 / 8 |      8 | all tier-1 datasets ported       |
| tier 2           |     0 / 10 |     10 | next milestone                   |
| tier 3           |      0 / 7 |      7 |                                  |
| ast languages    |         77 |    ~80 | tier 1–3 grammars registered     |

## Done

### Framework (v0.3.0)
- `BaseDownloader` + `BaseExtractor` contracts; strict phase boundary (no
  network in `extract()` unless `streaming=True`)
- `NLTKBackedDownloader` + `NLTKRawLayout` shared base for the five
  NLTK-consuming datasets
- All data models are pydantic (`RawTriple`, `DatasetMeta`, `RawLayout`,
  plus per-dataset record schemas like `WikidataPropertyDump`)
- `Normaliser` with `strict` / `permissive` profiles (auto-dispatch on `layer_band`)
- `Filter` with optional `TokeniserCheck` (HF tokeniser, cached)
- `TripleWriter` — atomic per-relation JSON with dedup
- `io_utils.atomic_write_json` / `atomic_write_bytes` — shared helpers
- `PipelineRunner` — `download_dataset` / `run_dataset` phases; global manifest
- Lazy registry (`DATASETS` dict; `list` survives missing deps)
- CLI: `list`, `download`, `extract`, `run`, `stats`, `verify` — each
  accepts dataset / `--tier` / `--category` / `--all` / `--config`
- Folder-per-dataset layout: each dataset is a package with `model.py`
  (pydantic contract), `downloader.py`, `extractor.py`

### Extractors
| key | relations | notes |
|---|---:|---|
| `linguistics/wordnet` | 20 | NLTK; all WordNet relation types |
| `linguistics/framenet` | 4 | NLTK framenet_v17 |
| `linguistics/verbnet` | 5 | NLTK verbnet; includes selectional restrictions |
| `linguistics/morphology` | 11 | lemminflect + WN derivational links |
| `linguistics/collocations` | 3 | Brown PMI + adj_noun + verb_object |
| `knowledge/wikidata` | 44 | curated SPARQL properties; raw JSON per property persisted |
| `ast/treesitter` | 5 | 77 languages; `<lang>/<symbol>`-scoped subjects |
| `domain/standards` | 7 | hand-curated IANA tables, zero deps |

## Near term — extend tier 1 domain coverage

Tier 1 linguistics/knowledge/ast is complete. Remaining tier 1 targets are
all domain-layer:

1. **`domain/errors`** — per-language compiler/interpreter error tables.
   Start with Python (`errno`, `builtins.__dict__`, scraping cpython `Doc/library/exceptions.rst`) and Rust (`rustc --explain` index). Shape: `error_code → message`, `error → category`.
2. **`domain/cli`** — man pages. Parse troff via `man -w` + `groff -Tutf8`. Shape: `command → flag`, `command → description`, `flag → description`.
3. **`domain/api_docs`** — Python stdlib by walking `sys.modules` + `inspect`; Rust `std` via `rustdoc --output-format json`. Shape: `function → module`, `module → submodule`, `function → return_type`.

Acceptance: `run --tier 1` produces ≥2M pairs across all registered datasets on a clean install.

## Medium term — tier 2

Datasets requiring meaningful downloads but nothing planetary:

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

`ast/treesitter` is one extractor over 77 registered languages across three
tiers. `tier` is a `TreeSitterLanguage` field — filter with
`extract --only python,rust` or via a config file. All per-language output
lands in one triple stream with `<lang>/<symbol>`-prefixed subjects, so a
single `ast/treesitter/` folder contains every language's keyword, parent-
child, supertype, sequence, and delimiter triples.

Still TODO:
- **Cross-language analysis** (universal keywords, Jaccard language
  families, keyword translation tables). This is a downstream step that
  reads the extracted triples, not a job for the extractor itself.
- **Grammar breadth**: ~80 languages registered today vs ~250 available
  upstream. Adding one is a single entry in `TreeSitterLanguage.LANGUAGES`.

## Known issues

- **Morphology blocked locally**: `lemminflect` → `spacy` → `thinc` hits a numpy ABI mismatch in the dev env. Fix by pinning numpy <2 or rebuilding thinc. Not a framework bug.
- **Registry is static**: dataset keys are declared in `registry.py`. Entry-point based discovery would be nicer for out-of-tree datasets; defer until someone actually needs it.

## Open design questions

- **Sharding large relations.** `wordnet/hypernyms` is 300K+ pairs today; what's the target shard size before compilation gets unhappy? Options: leave as one file, split by first letter, split by pair count. Blocked on compiler side.
- **Relation name canonicalisation.** Different extractors can call similar things different names (`synonyms` vs `similar`, `hypernyms` vs `is_a`). Should there be a relation alias table, or does the compiler handle it? Lean: compiler handles it, extractors stay source-faithful.
- **Tokeniser coverage as filter vs annotation.** Right now `TokeniserCheck` drops a triple. It could instead annotate `confidence` so the compiler decides. Punt until we see real compilation behaviour on borderline pairs.
- **Provenance fidelity.** Today `provenance` is a single string. For stackoverflow/pubmed we'll want (doc_id, span) tuples. Upgrade when the first extractor needs it, not before.
- **Multilingual.** v0.3 is English-only. Multilingual means vocab contamination risk in the syntax band — decide after the first compile actually uses this data.

## Out of scope (for now)

- Web scraping with selenium/playwright — every planned source has a structured download or API.
- Licence filtering — assumed handled upstream at ingest time.
- Incremental / resumable runs — current design is idempotent-by-rerun, which is good enough until individual extractors cross the 30-minute mark.
- Format converters (RDF, Neo4j, etc.) — the JSON triple files are the interchange format.

## Changelog

- **2026-04-11** — v0.3.0: download/extract phase split. `BaseDownloader`
  and `BaseExtractor` replace the combined contract. All data models on
  pydantic. Folder-per-dataset layout with `model.py` contract. New
  datasets: `linguistics/collocations`, `knowledge/wikidata` (44 SPARQL
  properties, raw JSON persistence), `ast/treesitter` (77 languages).
  Morphology gains adverb_form + negation_prefix via WordNet. VerbNet
  gains selectional_restrictions. Renamed from `larql-knowledge` to
  `knowledge-extractor`. Legacy `dataset-downloader/` deleted; its 86MB
  of extracted data preserved at `../datasets/extracted-legacy/`.
  Benchmark coverage tool moved to sibling `../benchmarks/` project.
- **2026-04-11** — repo cleanup: datasets moved to `<monorepo>/datasets/{raw,extracted}/`, NLTK redirected into the project tree, `raw_dir` threaded through the runner, CLI gains `--raw-dir`, env vars `KNOWLEDGE_RAW_DIR`/`KNOWLEDGE_EXTRACTED_DIR` honoured.
- **2026-04-11** — roadmap created; tier 1 at 5/8 registered, 4/8 runnable, 1.24M pairs sampled.
- **2026-04-10** — v0.2.0 framework + linguistics/{wordnet,framenet,verbnet,morphology} + domain/standards; lazy registry; normaliser profiles; token-coverage filter.
