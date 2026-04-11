# Dataset docs

One markdown file per registered (or planned) dataset. Each doc covers:

- **what it is** — the upstream source and why it matters
- **relations** — what triples come out, with examples
- **provenance** — where each pair is sourced from inside the dataset
- **dependencies** — pip/nltk/file downloads
- **licence** — usage constraints
- **caveats** — known quirks or edge cases

Index:

## Linguistics (L0-13, syntax band)

- [wordnet](./linguistics-wordnet.md) — Princeton WordNet synsets and lexical relations
- [framenet](./linguistics-framenet.md) — Berkeley FrameNet frames and lexical units
- [verbnet](./linguistics-verbnet.md) — verb classes with thematic roles and frames
- [morphology](./linguistics-morphology.md) — inflectional + derivational morphology via lemminflect

## Domain (L14-27, knowledge band)

- [standards](./domain-standards.md) — hand-curated HTTP / DNS / ports / MIME / TLS tables

## Planned

These have roadmap entries but no extractor yet:

- `linguistics/collocations`, `ast/*`, `knowledge/wikidata`, `knowledge/dbpedia`,
  `knowledge/geonames`, `knowledge/osm`, `knowledge/imdb`, `knowledge/musicbrainz`,
  `knowledge/pubchem`, `knowledge/taxonomy`, `knowledge/unicode`,
  `domain/stackoverflow`, `domain/api_docs`, `domain/cli`, `domain/openapi`,
  `domain/medical/{pubmed,clinical_trials}`, `domain/errors`,
  `domain/changelogs`, `domain/config_schemas`.

See [../../ROADMAP.md](../../ROADMAP.md) for sequencing.
