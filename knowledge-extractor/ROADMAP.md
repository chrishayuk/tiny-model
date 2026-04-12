# Roadmap

Living document. Tracks what ships in each tier, what's blocked, and what's
still a design question. See [SPEC.md](./SPEC.md) for architecture; this
file is about sequencing and scope.

## Status at a glance

|                  | registered | target | note                             |
|------------------|-----------:|-------:|----------------------------------|
| framework        |          ✓ |      — | base split into downloader/extractor phases |
| tests            |    90 / 90 |      — | pytest suite, `make ke-test`, 0.2s |
| tier 1           |      9 / 9 |      9 | all tier-1 datasets ported (+ countries) |
| tier 2           |     2 / 18 |     18 | spatial cluster: 2/6 done (countries, natural-earth) |
| tier 3           |      0 / 9 |      9 |                                  |
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
| `knowledge/countries` | 13 | hand-curated ISO 3166 + UN reference; 70 countries |
| `knowledge/natural-earth` | 15 | sovereignty chains + admin-1; 258 entities, 4500 subnational regions, 45 real dependencies |
| `knowledge/osm-gb` | 5 | Geofabrik GB extract; is_a, located_in, has_cuisine, has_brand, wikidata_id (ODbL) |
| `ast/treesitter` | 5 | 77 languages; `<lang>/<symbol>`-scoped subjects |
| `domain/standards` | 7 | hand-curated IANA tables, zero deps |

## Current priorities — spatial coverage

The next six datasets form a focused cluster that builds a coherent
spatial hierarchy and UK grounding on top of `knowledge/osm-gb`. Ordered
top-down so earlier datasets ground later ones, and zero-cost work
(existing PBF, no downloads) comes before new bandwidth:

1. **`knowledge/countries`** — ✅ **DONE** (v0.3.4). Hand-curated ISO 3166
   + UN reference in `_data.py`. 70 countries × 13 relations ≈ 900
   triples. Tier 1. Zero download. Doc: [countries](./docs/datasets/knowledge-countries.md).
2. **`knowledge/natural-earth`** — ✅ **DONE** (v0.3.5). 10m cultural
   shapefiles (~20 MB, pyshp). 258 country/dependency entities with
   sovereignty chains, 4500 subnational regions with admin hierarchy,
   45 real dependencies (e.g. French Guiana→France), economy/income
   classifications. 15,374 triples across 15 relations.
   Doc: [natural-earth](./docs/datasets/knowledge-natural-earth.md).
3. **`knowledge/osm-boundaries`** — **zero new network cost.** Second
   pass over the already-downloaded osm-gb PBF, keying off
   `admin_level=*` on boundary relations. Produces the GB admin
   hierarchy (parish → district → county → region → UK) as pure
   containment triples. Can live as a second extractor in the osm-gb
   folder or as a standalone dataset; lean standalone so the registry
   surfaces it.
4. **`knowledge/geonames`** — `allCountries.zip` (~300 MB) from
   geonames.org. Global place hierarchy, population bands, feature
   classes, timezones. Complements OSM at global scale: OSM tells you
   *what's there*, GeoNames tells you *how places relate and scale*.
5. **`domain/postcodes`** — UK postcodes from ONS/OS Code-Point Open.
   Tiny CSV. Shape: `(CO7_7, district, Colchester)`,
   `(CO7_7, region, East_of_England)`. Pins the postcode layer into
   the admin hierarchy the previous four datasets established.
6. **`domain/tides`** — UK tide gauge station reference from NTSLF/BODC.
   Smallest of the six, most specialised. Shape: `station → location`,
   `station → port`, `station → datum_offset`. Ties the physical
   measurement network into the place graph.

**Acceptance:** after these land, `run --category knowledge` and
`run --category domain` together produce a coherent chain from
country → sovereignty → subnational → UK admin → postcode → station,
with every step grounded in at least one authoritative source.
`DESCRIBE "CO7 7"` in LARQL should surface district → county → region →
country → continent in a single walk.

## Near term — extend tier 1 domain coverage

Tier 1 linguistics/knowledge/ast is complete. Remaining tier 1 targets are
all domain-layer:

1. **`domain/errors`** — per-language compiler/interpreter error tables.
   Start with Python (`errno`, `builtins.__dict__`, scraping cpython `Doc/library/exceptions.rst`) and Rust (`rustc --explain` index). Shape: `error_code → message`, `error → category`.
2. **`domain/cli`** — man pages. Parse troff via `man -w` + `groff -Tutf8`. Shape: `command → flag`, `command → description`, `flag → description`.
3. **`domain/api_docs`** — Python stdlib by walking `sys.modules` + `inspect`; Rust `std` via `rustdoc --output-format json`. Shape: `function → module`, `module → submodule`, `function → return_type`.
4. **`domain/periodic_table`** — element symbols, names, groups, periods,
   atomic numbers, categories, electron configurations. Tiny dataset but
   extremely clean, zero ambiguity. Good calibration dataset for LARQL
   probing: if DESCRIBE can't get `He → noble_gas`, something's wrong.
   One JSON file, no download needed.
5. **`domain/units`** — SI units, conversions, prefixes (kilo, mega,
   milli), dimensions. Models use these constantly. Similar calibration
   value to periodic_table. Zero deps.
6. **`domain/http`** — HTTP status codes, methods, headers, MIME types.
   Similar shape to `domain/standards` (IANA tables). Clean pairs, zero
   deps. Models see these constantly in training data.

Acceptance: `run --tier 1` produces ≥2M pairs across all registered datasets on a clean install.

## Medium term — tier 2

Datasets requiring meaningful downloads but nothing planetary. Items
marked **⭐** are in the current spatial-coverage priority cluster above.

### Knowledge — encyclopaedic

- `knowledge/osm-gb` — **registered**, first tier-2 port, Geofabrik GB extract (~2GB PBF). Next geography expansion: add `osm-us`, `osm-de`, etc. by copying the folder and retargeting `GEOFABRIK_URL`.
- `knowledge/dbpedia` — mappingbased objects. Wikipedia infoboxes
  pre-extracted as structured triples. Filter to single/few-token
  entities, group by property. Fastest path to scaling LARQL probe
  coverage: 50K+ triples from one script. Top 30 relations at 1000+
  pairs each. Sports, entertainment, business, science, food, history,
  animals, education categories.
- `knowledge/conceptnet` — 34M edges covering everyday common-sense
  relations (UsedFor, CapableOf, AtLocation, HasProperty, PartOf,
  Causes). Fills the common-sense gap that encyclopaedic sources miss.
  Models learn "knife → UsedFor → cutting" from text but current
  extractors only capture formal knowledge. Downloadable as CSV,
  filter to English single-token pairs. Targets syntax/knowledge band
  boundary (L10-16).
- **⭐ `knowledge/geonames`** — allCountries.zip (~300MB). Place
  hierarchy, population, elevation, timezone, administrative
  containment, feature class. Complements OSM: GeoNames tells you
  *how places relate* (London → Greater London → England → UK), OSM
  tells you *what's there*. Shape: `place → admin1`,
  `place → population_band`, `place → timezone`,
  `place → feature_class`.
- `knowledge/imdb` (title.basics + title.principals, ~1GB)
- `knowledge/unicode` (CLDR/Unicode tables, currencies, emoji names)
- **⭐ `knowledge/countries`** — dedicated extractor from ISO 3166 +
  UN data. Currencies, calling codes, TLDs, ISO codes, population
  bands, UN membership, continent, official languages — all in one
  clean pass. These are the relations LARQL probes test most heavily
  and the ones that light up best in DESCRIBE.

### Knowledge — spatial

- **⭐ `knowledge/natural-earth`** — free vector/attribute data at
  1:10m, 1:50m, 1:110m scales. Country polygons, sovereign states vs
  dependencies, disputed territories, admin-1 subdivisions, coastlines,
  rivers, lakes. Attribute tables give sovereignty chains
  (`French_Guiana → sovereignty → France`), continent membership,
  UN region classifications, economy/income groupings. Downloadable
  as shapefiles or GeoJSON. ~50MB.
- **⭐ `knowledge/osm-boundaries`** — second pass over the same PBF
  files as osm-gb. Extracts admin boundary relations from OSM
  `admin_level` tags: parish → district → county → region → country.
  Pure containment triples: `(Leavenheath, within, Babergh)`,
  `(Babergh, within, Suffolk)`. Could be a second extractor in the
  osm-gb folder or a standalone dataset.
- `knowledge/listed-buildings` — NHLE data from Historic England.
  ~400K listed buildings with structured attributes. Shape:
  `(Colchester_Castle, grade, I)`, `(Colchester_Castle, period,
  Norman)`, `(Colchester_Castle, type, castle)`. CSV download from
  Historic England open data portal.

### Knowledge — domain spatial

- **⭐ `domain/postcodes`** — UK postcode → coordinate → area mappings
  from ONS/OS Code-Point Open. Shape: `(CO7_7, district, Colchester)`,
  `(CO7_7, region, East_of_England)`. Models learn UK postcodes from
  training data. Tiny dataset, zero deps, clean CSV. Extend with US
  ZIP codes later.
- **⭐ `domain/tides`** — UK tide gauge stations from NTSLF/BODC.
  Shape: `station → location`, `station → port`,
  `station → datum_offset`. Small reference dataset mapping the
  physical measurement network. Feeds coastal heritage and flooding
  work.

### Linguistics

- `linguistics/grammar` — English syntactic templates. Determiner→noun,
  preposition→noun, subject→verb agreement patterns. Fills the syntax
  band (L0-13) gap: WordNet covers semantics, morphology covers word
  forms, AST covers code, but nothing covers English grammar structure.
  Source: parsed Wikipedia sentences or BNC. Target: 10K+ syntactic
  pairs.
- `linguistics/antonyms` — WordNet antonym relations as a dedicated
  stream. Antonyms are a distinct probe signal in the syntax band
  (`hot→cold` activates differently from `hot→warm`). May already be
  partially covered by the wordnet extractor but worth confirming
  explicit coverage.
- `linguistics/named_entity_types` — gazetteer mapping common entities
  to NER types: `London → LOCATION`, `Mozart → PERSON`, `IBM → ORG`.
  Ground truth for probing L14 attention where entity type
  classification happens.

### Domain

- `domain/stackoverflow` (Posts.xml, ~60GB → streaming XML parse)
- `domain/openapi` (APIs.guru registry)
- `domain/changelogs` (parse common CHANGELOG.md formats for 100+ popular libs)
- `domain/package_registries` — top packages from PyPI/npm/crates.io.
  Shape: `name → description`, `name → language`, `name → license`,
  `name → dependency`. Models know "requests is a Python HTTP library"
  — that's a learnable triple. Structured APIs for all three registries.
- `domain/git` — Git commands, flags, concepts. Similar shape to
  `domain/cli` but specifically for the tool every developer uses.
  `git rebase → interactive`, `git stash → temporary`,
  `--force → dangerous`.

Acceptance: `--tier 2` completes in <12h on a laptop, yields ≥5M pairs.

## Long term — tier 3

Heavy downloads, long processing, dedicated runs:

- `knowledge/osm-planet` — full OpenStreetMap planet PBF (~70 GB
  compressed, ~2 TB expanded). A qualitative jump from the per-country
  extracts: needs osmium CLI toolchain, hours of processing, and a
  tag-filtered first pass to keep the triple count manageable. Only
  worth it once the per-country extracts (osm-gb, osm-us, osm-de, …)
  have been validated end-to-end.
- `knowledge/whosonfirst` — Spelunker/WOF gazetteer. Every place has a
  stable ID, parent chain, and "belongsto" relationships. Key value:
  cross-dataset concordances — every WOF record links to its Wikidata
  QID, GeoNames ID, and other identifiers, enabling entity alignment
  across datasets. ~40GB for full gazetteer; filter to GB or subset
  for tier 2 treatment.
- `knowledge/musicbrainz` — Postgres dump ingest
- `knowledge/pubchem` — REST API, many requests, rate-limited
- `knowledge/taxonomy` — GBIF backbone
- `knowledge/coastline-change` — NCERM dataset from the Environment
  Agency. Predicted erosion rates per stretch of coastline. Shape:
  `(Holderness_Coast, erosion_rate, 2m_per_year)`,
  `(Holderness_Coast, SMP_policy, managed_realignment)`. Directly
  relevant to the coastal heritage erosion report.
- `knowledge/maritime` — triples derived from the chuk-mcp-maritime-
  archives dataset (833K+ records, 8 archives). Shape:
  `(Batavia, cargo, spices)`, `(Gotheborg, flag, Swedish)`,
  `(VOC_Route, waypoint, Cape_Town)`. Archive data already structured;
  extractor wraps existing ingestion.
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
  Prior LARQL experiments suggest `if` (English grammar) and `if`
  (Python keyword) may share gate features in L0-13 — the "rings are
  shared" hypothesis. Cross-language tables would test this.
- **Grammar breadth**: ~80 languages registered today vs ~250 available
  upstream. Adding one is a single entry in `TreeSitterLanguage.LANGUAGES`.

## LARQL integration

The knowledge-extractor feeds the LARQL vindex labelling pipeline. The
engine reads JSON triple files; this project produces them. Different
repo, different release cadence, different contributors.

```
knowledge-extractor (this project)     larql (the engine)
  ┌──────────────────────┐              ┌──────────────────────┐
  │ Extract              │              │                      │
  │   WordNet            │    JSON      │  extract-index       │
  │   Wikidata           │──────────►   │  label               │
  │   DBpedia            │   files      │  describe            │
  │   ConceptNet         │              │  walk                │
  │   OSM / GeoNames     │              │                      │
  │   AST corpora        │              │                      │
  └──────────────────────┘              └──────────────────────┘
```

Priority ordering for LARQL impact (aligned with the current spatial-
coverage focus above, then breadth items):

1. **`knowledge/countries`** — foundation layer. Every other spatial
   and admin dataset references country codes; probe-friendly.
2. **`knowledge/natural-earth`** — extends (1) with sovereignty +
   admin-1. Unlocks the "is French Guiana in France?" probe class.
3. **`knowledge/osm-boundaries`** — free win (reuses osm-gb PBF),
   gives GB admin hierarchy for DESCRIBE walks.
4. **`knowledge/geonames`** — global place hierarchy + population
   bands. Completes the country ↔ place ↔ city chain.
5. **`domain/postcodes` + `domain/tides`** — UK-detail grounding.
   Postcodes tie tokens models actually see to the admin hierarchy.
6. **`knowledge/dbpedia`** — biggest bang for buck on encyclopaedic
   breadth once the spatial cluster is in. 50K+ triples from one
   script across top 30 relations.
7. **`knowledge/conceptnet`** — fills the common-sense gap at the
   syntax/knowledge boundary (L10–16).
8. **`linguistics/grammar`** — fills the syntax band (L0–13) gap.
9. **Calibration tier-1 items** (`domain/periodic_table`,
   `domain/units`, `domain/http`) — tiny datasets that validate the
   probe pipeline at every layer.
10. **Wikidata dump** — long-tail coverage at scale once everything
    else is validated.

Target: `run --tier 2` produces labelled triples across all three layer
bands — syntax (L0-13), knowledge (L14-27), and output (L28-33) — so
that `larql label` can assign probe-quality labels to features at every
layer.

## Known issues

- **Morphology blocked locally**: `lemminflect` → `spacy` → `thinc` hits a numpy ABI mismatch in the dev env. Fix by pinning numpy <2 or rebuilding thinc. Not a framework bug.
- **Registry is static**: dataset keys are declared in `registry.py`. Entry-point based discovery would be nicer for out-of-tree datasets; defer until someone actually needs it.

## Open design questions

- **Sharding large relations.** `wordnet/hypernyms` is 300K+ pairs today; what's the target shard size before compilation gets unhappy? Options: leave as one file, split by first letter, split by pair count. Blocked on compiler side.
- **Relation name canonicalisation.** Different extractors can call similar things different names (`synonyms` vs `similar`, `hypernyms` vs `is_a`). Should there be a relation alias table, or does the compiler handle it? Lean: compiler handles it, extractors stay source-faithful.
- **Tokeniser coverage as filter vs annotation.** Right now `TokeniserCheck` drops a triple. It could instead annotate `confidence` so the compiler decides. Punt until we see real compilation behaviour on borderline pairs.
- **Provenance fidelity.** Today `provenance` is a single string. For
  stackoverflow/pubmed we'll want (doc_id, span) tuples. Upgrade when
  the first extractor needs it, not before. Promote to tier-2
  prerequisite once streaming extractors land.
- **Multilingual.** v0.3 is English-only. Multilingual means vocab contamination risk in the syntax band — decide after the first compile actually uses this data. LARQL cross-lingual experiments (француз, китай, brasileiro surfacing in multi-hop walks) suggest multilingual triples would improve probe coverage significantly.
- **Cross-dataset entity alignment.** Multiple extractors will produce
  triples about the same entity (e.g. "London" appears in OSM,
  GeoNames, natural-earth, Wikidata, listed-buildings). Should the
  extractor layer normalise entity IDs, or is this a compiler concern?
  Lean: extractors emit source-native IDs + a Wikidata QID where
  available; compiler handles alignment. WhoIsOnFirst concordances
  would help here. **Surfaces first with the spatial-coverage
  cluster**: countries / natural-earth / geonames / osm-boundaries all
  describe the same places with different IDs, so the cluster is the
  forcing function for the decision.

## Out of scope (for now)

- Web scraping with selenium/playwright — every planned source has a structured download or API.
- Licence filtering — assumed handled upstream at ingest time.
- Format converters (RDF, Neo4j, etc.) — the JSON triple files are the interchange format.

## Changelog

- **2026-04-12** — v0.3.4: `knowledge/countries` shipped. First of the
  six spatial-cluster datasets. Hand-curated ISO 3166 / UN M49 / ISO
  4217 / E.164 / IANA tables covering 70 countries × 13 relations ≈
  900 triples. Tier 1 (zero download). Follows the `domain/standards`
  pattern: `_data.py` holds Python literals, `model.py` maps keys to
  relation names via `SCALAR_RELATIONS`, extractor walks and yields.
  Parametrised integrity tests run against every country — catches
  missing fields and malformed codes immediately. Fixed two bugs the
  smoke test surfaced: the permissive normaliser was dropping
  `Washington, D.C.` (comma not in allowed set — fixed), and four
  city-states lost their `capital` triple to the self-loop filter
  (three unavoidable, Luxembourg disambiguated as "Luxembourg City").
  Registered, makefiled, tested, documented.
- **2026-04-12** — v0.3.3: roadmap re-prioritisation. Spatial coverage
  cluster (`knowledge/countries`, `knowledge/natural-earth`,
  `knowledge/osm-boundaries`, `knowledge/geonames`, `domain/postcodes`,
  `domain/tides`) promoted to a named priority block with an explicit
  sequencing rationale (top-down, zero-cost first). LARQL integration
  priority list re-ordered to lead with the spatial cluster and push
  the encyclopaedic breadth items (dbpedia, conceptnet, grammar)
  behind them. "Cross-dataset entity alignment" open question annotated
  as being forced by this cluster — four of the six datasets describe
  the same places with different IDs, so the decision can't stay
  abstract. Tier 2 status note updated from "in progress" to
  "spatial cluster is current focus". No code changes.
- **2026-04-11** — v0.3.2: roadmap expansion. Added 18 new dataset
  targets across spatial (natural-earth, osm-boundaries, listed-
  buildings, postcodes, tides, whosonfirst, coastline-change),
  knowledge (dbpedia, conceptnet, countries, maritime), linguistics
  (grammar, antonyms, named-entity-types), and domain (periodic-table,
  units, http, package-registries, git) categories. Added LARQL
  integration section documenting the pipeline relationship and
  priority ordering. New open design question on cross-dataset entity
  alignment. Tier 2 target expanded from 10 to 18 datasets.
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
