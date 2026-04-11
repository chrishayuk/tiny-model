# linguistics/wordnet

Princeton WordNet 3.0 — the canonical machine-readable lexical database of
English. Words are organised into **synsets** (sets of synonyms sharing one
meaning); synsets are linked by semantic relations (hypernymy, meronymy,
entailment, ...). This is the backbone of the syntax band (L0-13): almost
every lexical relation a small model needs to know about is in here.

- **Upstream**: https://wordnet.princeton.edu/
- **Access**: `nltk.corpus.wordnet` (ships with NLTK)
- **Licence**: [Princeton WordNet License](https://wordnet.princeton.edu/license-and-commercial-use) — free, attribution required, no warranty
- **Layer band**: `syntax`
- **Scale**: ~1.2M pairs across 20 relations on a full extract

## Relations produced

| relation | direction | example | source method |
|---|---|---|---|
| `synonyms` | bidirectional | (big, large) | all lemma pairs within a synset |
| `hypernyms` | directed | (dog, mammal) | `synset.hypernyms()` |
| `hyponyms` | directed | (dog, poodle) | `synset.hyponyms()` |
| `troponyms` | directed | (walk, stroll) | verb-only `hyponyms` |
| `meronyms_part` | directed | (car, wheel) | `synset.part_meronyms()` |
| `meronyms_substance` | directed | (bread, flour) | `synset.substance_meronyms()` |
| `meronyms_member` | directed | (fleet, ship) | `synset.member_meronyms()` |
| `holonyms_part` | directed | inverse of `meronyms_part` | `synset.part_holonyms()` |
| `holonyms_substance` | directed | inverse of `meronyms_substance` | `synset.substance_holonyms()` |
| `holonyms_member` | directed | inverse of `meronyms_member` | `synset.member_holonyms()` |
| `entailments` | directed | (snore, sleep) | `synset.entailments()` (verbs only) |
| `causes` | directed | (show, see) | `synset.causes()` (verbs only) |
| `also_see` | bidirectional | (big, important) | `synset.also_sees()` |
| `similar_to` | bidirectional | (fast, rapid) | `synset.similar_tos()` (adjectives) |
| `domain_topic` | directed | (backhand, tennis) | `synset.topic_domains()` |
| `domain_region` | directed | (cricket, england) | `synset.region_domains()` |
| `domain_usage` | directed | (dough, slang) | `synset.usage_domains()` |
| `antonyms` | bidirectional | (hot, cold) | `lemma.antonyms()` |
| `derivations` | bidirectional | (decide, decision) | `lemma.derivationally_related_forms()` |
| `pertainyms` | directed | (dental, tooth) | `lemma.pertainyms()` |

Directional relations are emitted once; bidirectional relations are written
both ways and deduped by the writer.

## Provenance

Every emitted triple carries `provenance = synset.name()` (e.g. `dog.n.01`).
Lemma-level relations (antonyms, derivations, pertainyms) attach the parent
synset so you can reconstruct the sense context later.

## Dependencies

- `pip`: `nltk`
- `nltk`: `wordnet`, `omw-1.4` (Open Multilingual WordNet — needed even for
  English-only runs, NLTK imports it eagerly)

All downloaded automatically on first run via `nltk.download(..., quiet=True)`.

## Caveats

- **Synset granularity is fine**. WordNet distinguishes senses very aggressively
  — `bank.n.01` (river) vs `bank.n.02` (financial institution). The extractor
  emits pairs per-synset, so the same word pair can appear under different
  provenances. The writer dedupes by `(subject, object)` so the final JSON
  has it once, but the per-sense frequency is lost. If you need it, change
  the writer to keep provenance on each pair.
- **Multiword expressions** come through with underscores in NLTK (`hot_dog`).
  The normaliser replaces them with spaces (`hot dog`) before deduping.
- **Archaic forms** still count as synonyms (`ere` ≈ `before`). If you want
  modern-only vocab, add a frequency filter with the Brown-top-20k vocab used
  by `linguistics/morphology`.
- **Coverage bias**: WordNet is heavy on nouns (~82k synsets), lighter on
  verbs (~14k), adjectives (~18k), and adverbs (~4k). Verb-only relations
  like `troponyms`, `entailments`, and `causes` are correspondingly sparser.
- **Licence**: Princeton WordNet is free but its licence is not an OSI
  open-source licence. Redistributing the triple files is fine; redistributing
  compiled model weights that embed them is… probably fine, but check with
  a lawyer if you ship commercially.

## Example output

`datasets/extracted/linguistics/wordnet/synonyms.json`:
```json
{
  "source": "wordnet",
  "relation": "synonyms",
  "layer_band": "syntax",
  "pair_count": 52000,
  "pairs": [
    ["big", "large"],
    ["fast", "quick"]
  ]
}
```

See [`examples/sample_output/linguistics/wordnet/`](../../examples/sample_output/linguistics/wordnet/)
for a 20-pair snapshot of each relation.
