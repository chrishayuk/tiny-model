# examples

Two things live here:

## 1. `run_demo.py` — runnable end-to-end demo

```bash
python3 examples/run_demo.py
```

Runs the `domain/standards` extractor (zero external deps), verifies the
manifest, prints a summary, and shows a sample of extracted pairs. Exercises
the full pipeline (extract → normalise → filter → dedup → write → manifest)
in ~50ms. Output lands in `knowledge-extractor/examples/_demo_output/` and is
gitignored. The demo never touches your real `datasets/extracted/` tree.

This is the smoke test to run right after install. If it works, the
framework works.

## 2. `sample_output/` — committed trimmed snapshot

A real tier-1 run, trimmed so each relation file has at most 20 pairs.
Lets you eyeball what triples actually look like for each extractor without
running anything or downloading NLTK data.

```
sample_output/
├── manifest.json                    # global — "trimmed sample" note
├── linguistics/
│   ├── wordnet/                     # 20 relations (synonyms, hypernyms, ...)
│   ├── framenet/                    # 4 relations (evokes_frame, frame_parent, ...)
│   └── verbnet/                     # 3 relations (member_of_class, has_role, ...)
└── domain/
    └── standards/                   # 7 relations (http_status, dns_record, ...)
```

Original counts on this snapshot before trimming:

| dataset              | full triples | files |
|----------------------|-------------:|------:|
| linguistics/wordnet  |    1,193,747 |    20 |
| linguistics/framenet |       38,707 |     4 |
| linguistics/verbnet  |        6,852 |     3 |
| domain/standards     |          127 |     7 |
| **total**            | **1,239,433** |  34 |

Verify it still parses:

```bash
python3 -m knowledge_extractor.cli verify examples/sample_output/
python3 -m knowledge_extractor.cli stats examples/sample_output/
```

The snapshot does not include `linguistics/morphology` because the host env
where it was generated had a broken spacy/numpy binary. Re-run to add it:

```bash
python3 -m knowledge_extractor.cli extract linguistics/morphology \
    --output knowledge-extractor/examples/sample_output/
```

## Reproducing the full tier-1 run

Run from the monorepo root. Output lands in `datasets/extracted/`, raw
downloads in `datasets/raw/` (NLTK corpora included).

```bash
python3 -m knowledge_extractor.cli extract --tier 1
```

Expect ~1.2M triples, a few minutes on first run (NLTK data download), and
seconds on subsequent runs.
