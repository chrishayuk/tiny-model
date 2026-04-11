# Roadmap

Living document. Tracks what ships in each tier, what's blocked, and what's
still a design question. See [SPEC.md](./SPEC.md) for architecture; this
file is about sequencing and scope.

## Status at a glance

|                  | registered | target | note                             |
|------------------|-----------:|-------:|----------------------------------|
| framework        |          ✓ |      — | base split into downloader/extractor phases |
| tests            |    90 / 90 |      — | pytest suite, `make ke-test`, 0.2s |
| tier 1           |      8 / 8 |      8 | all tier-1 datasets ported       |
| tier 2           |     1 / 10 |     10 | osm-gb registered; in progress   |
| tier 3           |      0 / 7 |      7 |                                  |
| ast languages    |         77 |    ~80 | tier 1–3 grammars registered     |

## Done

### Framework (v0.3.1)
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
- Per-downloader `tqdm` progress bars: byte-level for osm-gb, per-item
  (property / language / NLTK package) for the others
- HTTP Range resume in the osm-gb downloader so killed transfers pick up
  at the `.tmp` file's current size
- Pytest suite (90 tests, ~0.2 s) covering the pydantic base contracts,
  registry integrity, io_utils, writer dedup, normaliser profiles, paths
  env-var overrides, standards end-to-end, osm-gb pure helpers + geohash,
  treesitter grammar walker, and wikidata synthetic-dump round trip

### Extractors
| key | relations | notes |
|---|---:|---|
| `linguistics/wordnet` | 20 | NLTK; all WordNet relation types |
| `linguistics/framenet` | 4 | NLTK framenet_v17 |
| `linguistics/verbnet` | 5 | NLTK verbnet; includes selectional restrictions |
| `linguistics/morphology` | 11 | lemminflect + WN derivational links |
| `linguistics/collocations` | 3 | Brown PMI + adj_noun + verb_object |
| `knowledge/wikidata` | 44 | curated SPARQL properties; raw JSON per property persisted |
| `knowledge/osm-gb` | 5 | Geofabrik GB extract; is_a, located_in, has_cuisine, has_brand, wikidata_id (ODbL) |
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

- `knowledge/osm-gb` — **registered**, first tier-2 port, Geofabrik GB extract (~2GB PBF). Next geography expansion: add `osm-us`, `osm-de`, etc. by copying the folder and retargeting `GEOFABRIK_URL`.
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

- `knowledge/osm-planet` — full OpenStreetMap planet PBF (~70 GB
  compressed, ~2 TB expanded). A qualitative jump from the per-country
  extracts: needs osmium CLI toolchain, hours of processing, and a
  tag-filtered first pass to keep the triple count manageable. Only
  worth it once the per-country extracts (osm-gb, osm-us, osm-de, …)
  have been validated end-to-end.
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
- Format converters (RDF, Neo4j, etc.) — the JSON triple files are the interchange format.

## Changelog

- **2026-04-11** — v0.3.1: first tier-2 dataset, developer ergonomics,
  and a real test suite.
  - **New dataset: `knowledge/osm-gb`.** Geofabrik GB extract (~2 GB
    PBF), pyosmium walker, ODbL. Emits `is_a`, `located_in`,
    `has_cuisine`, `has_brand`, `wikidata_id` on bare `<name>` subjects
    plus `has_name`, `at_coords`, `in_geohash` on per-instance
    `<name>#<kind><osm_id>` subjects so chain stores dedup semantically
    while keeping individual geometry. Self-contained 7-char geohash
    encoder in the extractor (no dep). Ways resolved via arithmetic
    centroid of member nodes.
  - **Progress bars on all real downloaders.** `tqdm` at the right
    granularity for each: byte-level for osm-gb, per-property for
    wikidata, per-language for treesitter, per-NLTK-package for the
    linguistics datasets. Errors use `bar.write()` to avoid breaking
    the bar layout.
  - **HTTP Range resume on osm-gb.** A killed download leaves its
    `.tmp` sibling in place and the next invocation sends
    `Range: bytes=<partial>-`, picking up where it stopped. Falls back
    to restart if the server returns a fresh 200.
  - **Monorepo Makefile generator.** One `DATASETS` list plus a
    `foreach`/`eval` macro emits `run-<name>`, `download-<name>`, and
    `extract-<name>` for every registered dataset — 27 targets from one
    source of truth. Adding a dataset is a one-line change.
  - **Pytest suite: 90 tests, ~0.2 s.** Covers the pydantic base
    contracts, registry integrity (parametrised over every dataset),
    io_utils atomic writes with failure cleanup, writer dedup semantics,
    normaliser profile dispatch, paths env-var overrides, standards
    full end-to-end pipeline, osm-gb pure helpers including the
    Wikipedia-canonical geohash vector, treesitter grammar walkers,
    and wikidata extraction from a synthesised raw dump. Wired up as
    `make ke-test` (included in the composite `make test`).
  - **Bug found and fixed by tests.** `BaseDownloader.raw_path()` had a
    `mkdir` side effect that made `is_downloaded()` incorrectly report
    True after just constructing a layout. `raw_path()` is now pure;
    callers that need to write are expected to use `atomic_write_*`
    which mkdirs the parent itself, or mkdir explicitly.
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
