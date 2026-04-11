# knowledge-extractor

Dataset-oriented triple extraction pipeline for the LARQL graph-to-weights
compiler. One framework, pluggable extractors per dataset, one self-contained
folder of JSON triples per dataset.

See [SPEC.md](./SPEC.md) for the v0.2 architecture, [ROADMAP.md](./ROADMAP.md)
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
└── knowledge-extractor/              # this project — pure code
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
cd knowledge-extractor
uv sync
```

## Try it in 30 seconds

```bash
python3 knowledge-extractor/examples/run_demo.py
```

Runs the zero-dependency `domain/standards` extractor end-to-end, verifies
the manifest, and prints sample pairs. Writes to
`knowledge-extractor/examples/_demo_output/` (gitignored). See
[`examples/`](./examples) for a trimmed snapshot of a real tier-1 run across
wordnet, framenet, verbnet, and standards (1.2M triples before trimming).

## Usage

Run from the monorepo root so relative paths resolve.

```bash
# list what's registered
uv run knowledge-extractor list

# run a single dataset (writes to datasets/extracted/linguistics/wordnet/)
uv run knowledge-extractor extract linguistics/wordnet

# run an entire tier
uv run knowledge-extractor extract --tier 1

# run everything in a category
uv run knowledge-extractor extract --category linguistics

# config-driven run
uv run knowledge-extractor extract --config knowledge-extractor/configs/tier1.yaml

# explicit paths
uv run knowledge-extractor extract linguistics/wordnet \
    --output datasets/extracted/ \
    --raw-dir datasets/raw/

# inspect output
uv run knowledge-extractor stats datasets/extracted/
uv run knowledge-extractor verify datasets/extracted/
```

Override paths globally for scripted runs:

```bash
KNOWLEDGE_EXTRACTED_DIR=/mnt/big-disk/extracted \
KNOWLEDGE_RAW_DIR=/mnt/big-disk/raw \
    uv run knowledge-extractor extract --tier 2
```

## Code layout

```
src/knowledge_extractor/
  base.py           BaseExtractor, RawTriple, DatasetMeta
  paths.py          dataset path resolution + NLTK redirection
  normaliser.py     text cleaning (strict/permissive profiles)
  filter.py         quality filter + optional tokeniser coverage
  tokeniser_check.py  HF tokeniser wrapper, cached
  writer.py         atomic JSON writer + dedup
  manifest.py       stats / verification
  runner.py         PipelineRunner — the orchestrator
  registry.py       lazy EXTRACTORS dict + TIERS
  cli.py            argparse entry point
  linguistics/      wordnet, framenet, verbnet, morphology
  ast/              tree-sitter (planned)
  knowledge/        wikidata, dbpedia, geonames, ... (planned)
  domain/           standards, stackoverflow, api_docs, ... (in progress)
```

## Currently registered

- `linguistics/wordnet` — 20 relations (synonyms, hypernyms/hyponyms,
  meronyms/holonyms, antonyms, troponyms, entailments, causes, similar_to,
  pertainyms, derivations, domain_{topic,region,usage})
- `linguistics/framenet` — evokes_frame, frame_lexicon, frame_element, frame_parent
- `linguistics/verbnet` — member_of_class, has_role, has_frame
- `linguistics/morphology` — plurals, verb tenses, comparative/superlative,
  agent_noun, nominalization
- `domain/standards` — http_status, http_method, dns_record, tcp_port,
  udp_port, mime_type, tls_version

Adding a new extractor is a ~50 line file — see section 7 of
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
