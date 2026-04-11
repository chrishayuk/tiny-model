# knowledge-extractor

Dataset-oriented triple extraction pipeline with a strict download / extract
phase split. One framework, pluggable downloader + extractor per dataset,
one self-contained folder of JSON triples per dataset.

See [SPEC.md](./SPEC.md) for the v0.3 architecture, [ROADMAP.md](./ROADMAP.md)
for what's shipping when, and [docs/datasets/](./docs/datasets/) for a
per-dataset explanation of what each extractor produces.

## Where things live

This project is code only. Datasets live one level up at the monorepo root:

```
tiny-model/                       # monorepo root — run commands from here
├── datasets/
│   ├── raw/                      # everything downloaded, gitignored
│   │   └── nltk/                 # NLTK_DATA is redirected here
│   └── extracted/                # transformed JSON triples, gitignored
│       ├── manifest.json
│       ├── linguistics/wordnet/
│       ├── linguistics/framenet/
│       └── domain/standards/
│
└── knowledge-extractor/          # this project — pure code
    ├── src/knowledge_extractor/
    ├── configs/                  # tier{1,2,3}.yaml
    ├── docs/datasets/            # per-dataset documentation
    ├── examples/                 # demo script + committed sample output
    └── tests/
```

Nothing in `datasets/` is committed. Regenerate everything by re-running
the extractors.

## Install

```bash
# from the monorepo root
make setup
```

This syncs the `knowledge-extractor` and `benchmarks` Python venvs and
builds the Rust tokenizer workspace. Just want this project?

```bash
cd knowledge-extractor && uv sync
```

## Try it in 30 seconds

```bash
# from the monorepo root
make demo
```

Runs the zero-dependency `domain/standards` extractor end-to-end, verifies
the manifest, and prints sample pairs. Writes to
`knowledge-extractor/examples/_demo_output/` (gitignored). See
[`examples/`](./examples) for a trimmed snapshot of a real tier-1 run
(1.2M triples before trimming).

## Usage

The pipeline has three phases — `download`, `extract`, and `run` (which
chains both). All commands expect to run from the monorepo root so that
the default `datasets/{raw,extracted}/` paths resolve correctly.

### Via the Makefile (recommended)

```bash
make list                # registered datasets
make run                 # download + extract, tier 1
make download            # just the raw fetch, tier 1
make extract             # just the transform step, tier 1

# single-dataset phase targets — all three of run-, download-, extract-
# are generated from one DATASETS list in the Makefile.
make run-osm-gb          # download + extract knowledge/osm-gb
make download-osm-gb     # just fetch the raw PBF (useful for large datasets)
make extract-osm-gb      # just walk the raw into triples
# valid names: wordnet morphology framenet verbnet collocations
#              wikidata osm-gb treesitter standards

make stats               # summarise datasets/extracted/
make verify              # check manifest consistency
make coverage            # run the benchmarks sibling project
make clean-datasets      # wipe datasets/{raw,extracted}/
```

Run `make` with no target for the full list.

### Via the CLI directly

```bash
# common case: download then extract
uv run knowledge-extractor run linguistics/wordnet

# phases separately (download once, extract many times with different filters)
uv run knowledge-extractor download linguistics/wordnet
uv run knowledge-extractor extract  linguistics/wordnet

# tiers, categories, everything
uv run knowledge-extractor run --tier 1
uv run knowledge-extractor run --category linguistics
uv run knowledge-extractor run --all
uv run knowledge-extractor run --config configs/tier1.yaml

# explicit paths
uv run knowledge-extractor run linguistics/wordnet \
    --output datasets/extracted/ \
    --raw-dir datasets/raw/
```

Override paths globally for scripted runs:

```bash
KNOWLEDGE_EXTRACTED_DIR=/mnt/big-disk/extracted \
KNOWLEDGE_RAW_DIR=/mnt/big-disk/raw \
    uv run knowledge-extractor run --tier 2
```

## Code layout

```
src/knowledge_extractor/
  base.py           BaseDownloader, BaseExtractor, NLTKBackedDownloader,
                    RawLayout, NLTKRawLayout, RawTriple, DatasetMeta
  paths.py          dataset path resolution + NLTK redirection
  io_utils.py       atomic_write_json / atomic_write_bytes
  normaliser.py     text cleaning (strict/permissive profiles)
  filter.py         quality filter + optional tokeniser coverage
  tokeniser_check.py  HF tokeniser wrapper, cached
  writer.py         atomic JSON writer + dedup
  manifest.py       stats / verification
  runner.py         PipelineRunner — orchestrates download + extract phases
  registry.py       lazy DATASETS dict + TIERS
  cli.py            argparse entry point
  linguistics/      wordnet, framenet, verbnet, morphology, collocations
  ast/              treesitter (77 languages)
  knowledge/        wikidata
  domain/           standards (more planned)
```

Every dataset is a folder with `__init__.py`, `model.py` (pydantic
`RawLayout` + `DatasetMeta`), `downloader.py`, and `extractor.py`.

## Currently registered

- `linguistics/wordnet` — 20 relations (synonyms, hypernyms/hyponyms,
  meronyms/holonyms, antonyms, troponyms, entailments, causes, similar_to,
  pertainyms, derivations, domain_{topic,region,usage})
- `linguistics/framenet` — evokes_frame, frame_lexicon, frame_element, frame_parent
- `linguistics/verbnet` — member_of_class, has_role, has_frame, selrestr_{pos,neg}
- `linguistics/morphology` — plurals, verb tenses, comparative/superlative,
  adverb_form, negation_prefix, agent_noun, nominalization
- `linguistics/collocations` — bigram_pmi, adjective_noun, verb_object (Brown)
- `knowledge/wikidata` — 44 curated SPARQL properties across geography,
  people, culture, organisations, science, politics, sport
- `knowledge/osm-gb` — OpenStreetMap GB extract: named amenities, shops,
  tourism, historic sites, leisure, natural features; is_a, located_in,
  has_cuisine, has_brand, wikidata_id (ODbL licence, optional `osm` extra)
- `ast/treesitter` — 77 languages across 3 tiers; keyword_begins, contains,
  is_a, followed_by, delimiter_role (subjects are `<lang>/<symbol>`-scoped)
- `domain/standards` — http_status, http_method, dns_record, tcp_port,
  udp_port, mime_type, tls_version

Adding a new extractor is a ~50 line folder — see section 9 of
[SPEC.md](./SPEC.md) and [docs/datasets/](./docs/datasets/) for examples.

## Output shape

Each dataset writes to `datasets/extracted/<category>/<dataset>/`:

```
datasets/extracted/linguistics/wordnet/
  manifest.json
  synonyms.json
  hypernyms.json
  ...
```

Triple files all share the same schema (`source`, `relation`, `layer_band`,
`pair_count`, `pairs`). The folder structure IS the compilation spec.
