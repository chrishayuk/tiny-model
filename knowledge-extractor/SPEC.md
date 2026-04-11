# Knowledge Extractor — Triple Extraction Pipeline

**Spec v0.3 — Download/Extract Phase Split**

Chris Hay | April 2026

---

## 1. Purpose

One framework. Pluggable extractors per dataset. Each dataset is a self-contained
folder with its own manifest, triple files, and version. The pipeline handles
normalisation, dedup, filtering, and output. Extractors only parse source formats
and yield raw triples.

```
Raw source (XML, HTML, JSON, troff, .d.ts, Python, YAML, ...)
    ↓
Dataset-specific extractor (plugin)
    ↓
Raw triples (subject, relation, object, confidence, provenance)
    ↓
Normalisation (lowercase, dedup, token check)
    ↓
Filtering (frequency, quality, token coverage)
    ↓
Dataset folder with manifest + per-relation JSON files
```

---

## 2. Data Directory Structure

Datasets live **outside the code repo**, under `<monorepo>/datasets/`, split
into two trees:

```
datasets/
├── raw/             # everything downloaded, untouched. gitignored.
│   ├── nltk/        # NLTK_DATA is redirected here
│   ├── linguistics/ # per-extractor raw caches (category/dataset/...)
│   ├── knowledge/
│   └── domain/
│
└── extracted/       # transformed JSON triples (the output). gitignored.
    ├── manifest.json  # global aggregate
    ├── linguistics/
    ├── ast/
    ├── knowledge/
    └── domain/
```

Every dataset is a self-contained folder under `extracted/`. You can clone,
update, or contribute a single dataset independently.

```
datasets/extracted/
├── manifest.json                        # global aggregate
│
├── linguistics/
│   ├── wordnet/
│   │   ├── manifest.json
│   │   ├── synonyms.json
│   │   ├── hypernyms.json
│   │   ├── hyponyms.json
│   │   ├── antonyms.json
│   │   ├── meronyms_part.json
│   │   ├── meronyms_substance.json
│   │   ├── meronyms_member.json
│   │   ├── holonyms_part.json
│   │   ├── holonyms_substance.json
│   │   ├── holonyms_member.json
│   │   ├── troponyms.json
│   │   ├── entailments.json
│   │   ├── causes.json
│   │   ├── also_see.json
│   │   ├── pertainyms.json
│   │   ├── derivations.json
│   │   ├── similar_to.json
│   │   ├── domain_topic.json
│   │   ├── domain_region.json
│   │   └── domain_usage.json
│   ├── framenet/
│   ├── verbnet/
│   ├── morphology/
│   └── collocations/
│
├── ast/
│   ├── python/
│   ├── javascript/
│   ├── ... (248 languages)
│   └── _cross_language/
│
├── knowledge/
│   ├── wikidata/
│   ├── dbpedia/
│   ├── geonames/
│   ├── osm/
│   ├── imdb/
│   ├── musicbrainz/
│   ├── pubchem/
│   ├── taxonomy/
│   └── unicode/
│
└── domain/
    ├── stackoverflow/
    ├── api_docs/{python,rust,go,javascript,...}
    ├── cli/
    ├── standards/
    ├── openapi/
    ├── medical/{pubmed,clinical_trials}
    ├── errors/{python,rust,javascript,...}
    ├── changelogs/
    └── config_schemas/{kubernetes,terraform,docker}
```

## 3. Manifest Schemas

### Dataset manifest (`<dataset>/manifest.json`)

```json
{
  "dataset": "wordnet",
  "category": "linguistics",
  "version": "3.0",
  "license": "Princeton WordNet License",
  "url": "https://wordnet.princeton.edu/",
  "layer_band": "syntax",
  "extracted": "2026-04-10T14:30:00Z",
  "extractor": "WordNetExtractor",
  "raw_triples": 420000,
  "kept_triples": 320000,
  "filter_rate": "76.2%",
  "relations": {
    "synonyms": {"file": "synonyms.json", "pairs": 52000},
    "hypernyms": {"file": "hypernyms.json", "pairs": 81000}
  },
  "total_pairs": 320000
}
```

### Triple file (`<dataset>/<relation>.json`)

```json
{
  "source": "wordnet",
  "relation": "synonyms",
  "description": "Words with the same or similar meaning",
  "layer_band": "syntax",
  "extracted": "2026-04-10T14:30:00Z",
  "pair_count": 52000,
  "pairs": [["big", "large"], ["fast", "quick"]]
}
```

### Global manifest (`datasets/extracted/manifest.json`)

```json
{
  "version": "1.0",
  "extracted": "2026-04-10T...",
  "categories": {
    "linguistics": {"datasets": ["wordnet", "morphology"], "layer_band": "syntax", "total_pairs": 370000}
  },
  "totals": {"categories": 1, "datasets": 2, "total_pairs": 370000}
}
```

## 4. Phase Split: Download vs Extract

The pipeline has **two phases** with a strict boundary:

1. **Download** — populates `<raw_dir>` with unmodified source artifacts
   (NLTK corpora, SPARQL JSON responses, tree-sitter grammar files, …).
   Network I/O lives here. Must be idempotent.
2. **Extract** — reads `<raw_dir>` and yields triples. Must NOT hit the
   network unless the extractor opts into ``streaming=True`` (rare;
   only when persisting raw data would be genuinely wasteful).

The runner enforces this by running the downloader first and only then
invoking the extractor. `knowledge-extractor run` chains both; `download`
and `extract` are also available as separate subcommands.

## 5. Core Classes

All data models are pydantic ``BaseModel``.

- `RawTriple(subject, relation, object, confidence=1.0, provenance="", source="", layer_band="knowledge")`
- `DatasetMeta(name, category, version, license, url, layer_band, description)`
- `RawLayout` — per-dataset contract between downloader and extractor.
  Each dataset subclasses this in its ``model.py`` with the paths and
  files the raw_dir should contain. ``verify()`` returns True when the
  layout is complete.
- `BaseDownloader` — abstract, implements `meta()`, `download(raw_dir)`,
  `is_downloaded(raw_dir)`, `layout(raw_dir)`, `raw_path(raw_dir)`.
  May hit the network; must be idempotent.
- `BaseExtractor` — abstract, implements `meta()`, `extract(config)`,
  `output_path(base_dir)`, `raw_path(raw_dir)`. No network (unless
  ``streaming=True``). Reads raw_dir, yields ``RawTriple``.
- `Normaliser` — lowercase, strip, reject non-alpha/digit, drop self-loops
- `Filter` — min_confidence, max_subject_length, max_object_length, token-coverage (optional)
- `TripleWriter` — atomic per-relation JSON writes
- `PipelineRunner` — orchestrates download and extract phases; writes manifests

## 6. Folder-per-Dataset Layout

Each registered dataset lives in its own package under
``src/knowledge_extractor/<category>/<name>/`` with three files:

```
linguistics/wordnet/
  __init__.py     # re-exports the three classes
  model.py        # META, RawLayout, any record schemas
  downloader.py   # WordNetDownloader (BaseDownloader)
  extractor.py    # WordNetExtractor (BaseExtractor)
```

`model.py` is the shared contract: it owns the ``DatasetMeta`` singleton,
the pydantic ``RawLayout`` subclass describing the raw_dir shape, and any
record-level pydantic models (e.g. the Wikidata ``WikidataPropertyDump``
envelope). Both downloader and extractor import from ``model.py`` so
neither half has to know the other's internals.

## 7. Extractor Registry & Tiers

```
TIERS[1] = quick wins (APIs, local tools, small downloads)
TIERS[2] = medium (needs downloads, manageable)
TIERS[3] = heavy (large downloads, long processing)
```

`registry.py` holds a single ``DATASETS`` dict mapping ``"category/name"``
keys to ``{"downloader": "...", "extractor": "..."}`` module paths. Both
components are imported lazily so partial installs still work.

## 8. CLI

Paths default to `datasets/extracted/` and `datasets/raw/`, resolved
relative to the current working directory. Run from the monorepo root.

```bash
knowledge-extractor list

# Phase-aware subcommands
knowledge-extractor download linguistics/wordnet       # just fetch raw
knowledge-extractor extract  linguistics/wordnet       # just transform raw → triples
knowledge-extractor run      linguistics/wordnet       # download + extract

# Selection flags apply to all three
knowledge-extractor run --tier 1
knowledge-extractor run --category linguistics
knowledge-extractor run --all
knowledge-extractor run --config configs/tier1.yaml
knowledge-extractor run linguistics/wordnet \
    --output datasets/extracted/ \
    --raw-dir datasets/raw/

# Inspection
knowledge-extractor stats datasets/extracted/
knowledge-extractor verify datasets/extracted/
```

Override defaults with env vars for scripted runs:

```bash
KNOWLEDGE_EXTRACTED_DIR=/mnt/big-disk/extracted \
KNOWLEDGE_RAW_DIR=/mnt/big-disk/raw \
    knowledge-extractor run --tier 2
```

All NLTK downloads are redirected into `<raw_dir>/nltk/`, so the project
is self-contained — nothing lands in `~/nltk_data`.

## 9. Adding a New Dataset

1. Create `src/knowledge_extractor/<category>/my_dataset/` as a package
   with `__init__.py`, `model.py`, `downloader.py`, `extractor.py`.
2. In `model.py`: define a ``META`` ``DatasetMeta`` singleton and a
   ``MyDatasetRawLayout(RawLayout)`` pydantic model that names the files
   and implements ``verify()``.
3. In `downloader.py`: subclass ``BaseDownloader``; implement
   ``download(raw_dir)`` and ``layout(raw_dir)``.
4. In `extractor.py`: subclass ``BaseExtractor``; implement
   ``extract(config)`` as a pure reader over ``raw_dir``.
5. Register in `registry.py`'s ``DATASETS`` dict using ``_pair(...)``
   and add the key to the appropriate tier.
6. Run: `knowledge-extractor run <category>/my_dataset`

The framework handles normalisation, filtering, dedup, manifests, output.

## 10. Compilation Interface

The folder structure IS the compilation spec:
- `linguistics/` + `ast/` → L0-13 (syntax band)
- `knowledge/` + `domain/` → L14-27 (knowledge band)
- Each JSON file is one `compile_triples()` call
