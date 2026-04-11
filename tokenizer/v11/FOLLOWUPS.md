# v11 Tokenizer Followups

Gaps found during v11 compilation experiments on the v11 TinyStories 115M
checkpoint. Each requires a `v11-builder` config change + tokenizer
rebuild + model retrain to take effect (v11.1).

## 1. Sentence-initial TitleCase function words fragment

**58%** of common sentence-initial TitleCase function words split into
multiple SP pieces on v11. The WordNet TitleCase interleave
(`wordnet_titlecase_top_n: 3000`) only covers top-3K content lemmas and
doesn't reach pronouns, determiners, auxiliaries, or common adverbs.

### Measured gap

```
Sentence-initial TitleCase function words: 55/95 fragment (58%)
  'The'   → ['▁T', 'he']
  'An'    → ['▁A', 'n']
  'This'  → ['▁T', 'his']
  'That'  → ['▁T', 'hat']
  'These' → ['▁T', 'h', 'ese']
  'Those' → ['▁T', 'hose']
```

### Impact

Any passage compilation where sentences start with an article or
pronoun (which is most English prose) costs 2-3 extra tokens per
sentence and blocks single-token fact-edge extraction from the
sentence-initial position. In the exp12 v11 port, **4 of 5 test
sentences were rejected at Phase 0** because their opening word
(`The`, `Bees`, etc.) fragmented.

### Fix

Add to `config.json` → `layers` → L1/L2 a new layer
`L1.5_function_caps` (or extend `function_words` to cover
capitalized variants), containing the 95-word TitleCase list:

```json
"function_word_titlecase": [
  "The", "A", "An", "This", "That", "These", "Those",
  "I", "You", "He", "She", "It", "We", "They",
  "My", "Your", "His", "Her", "Our", "Their",
  "When", "Where", "What", "Why", "Who", "How", "Which",
  "Then", "There", "Here", "Now",
  "And", "But", "Or", "So", "If", "Yet",
  "For", "Nor", "As", "At", "By", "In", "On", "Up", "To",
  "Of", "With", "From", "Into", "Onto",
  "Some", "All", "Any", "Each", "Every", "Both", "Few",
  "Many", "More", "Most", "Other",
  "Is", "Are", "Was", "Were", "Be", "Been", "Being",
  "Have", "Has", "Had", "Do", "Does", "Did",
  "Will", "Would", "Can", "Could", "Should", "May", "Might",
  "Must", "Shall",
  "Not", "No",
  "One", "Two", "Three", "Four", "Five",
  "Six", "Seven", "Eight", "Nine", "Ten"
]
```

Cost: ~95 vocab slots. Benefit: 58% → 0% fragmentation on
sentence-initial function words, which unblocks passage compilation on
natural English prose.

Alternative (cleaner): change `wordnet_titlecase_top_n` from 3000 →
5000 and also add the explicit function_word_titlecase list, because
the top-5K WordNet lemmas include all the content words you'd want
capitalized at sentence-start.

## 2. Plural and inflected forms fragment

**84%** of common `-s` / `-es` plurals and `-s` third-person singular
verbs split into `stem + s` on v11. The WordNet layer stores base forms
only (`cat`, `run`), and SP training on 24M TinyStories tokens didn't
allocate single-token slots to the inflections.

### Measured gap

```
Common plurals/inflections: 32/38 fragment (84%)
  'cats'   → ['▁cat', 's']
  'dogs'   → ['▁dog', 's']
  'birds'  → ['▁bird', 's']
  'runs'   → ['▁run', 's']
  'sleeps' → ['▁sleep', 's']
  'flowers'→ ['▁flower', 's']
```

### Impact

Any natural English sentence with a plural subject or present-tense
verb costs at least one extra token per inflected word, and passage
chains that contain plurals can't encode the plural as a single
landing-pad. Many of v10c's exp12 v4 sentences (`Bees make honey`,
`The cat sleeps`) failed on v11 specifically because of this.

### Fix

Add a new config layer `L2.5_inflections` that programmatically
generates `{stem}{suffix}` pairs for the top-N WordNet nouns and verbs:

```json
"wordnet_inflect_top_n": 2000,
"wordnet_inflect_suffixes": ["s", "es", "ed", "ing", "er", "est"]
```

And in `v11-builder/src/main.rs`, the `extract_wordnet_lemmas`
function would emit both `cat` and `cats` (and `▁cat` and `▁cats`)
for the top-2000 lemmas that accept them. Cost: ~4-6K vocab slots
(minus SP dedup). Benefit: 84% → near 0% fragmentation on common
inflections.

Alternative: don't allocate vocab slots, but provide an `adjustments`
post-pass that SP-trains on a corpus deliberately biased toward
inflected forms so the longest-match trie picks them up naturally.

## 3. Wikidata entity coverage gaps

Spot-checked during the exp15 compilation test; logged for
completeness.

### Measured gap

Of 13 common world capitals tested:

```
✓ single-token on v11: Paris, London, Rome, Berlin, Moscow
✗ fragment:            Tokyo, Madrid, Athens, Dublin, Vienna, Warsaw,
                       Seoul, Cairo, Oslo, Prague, Bern, Lisbon
```

Only 5 out of 13 major European and world capitals land as single
tokens. Cairo, Athens, Tokyo — obvious must-haves — all fragment.

### Impact

The "knowledge-first" claim in `SPEC.md §1` is weakened. A knowledge
graph that can't address `Tokyo` as a single token can't compile
`Japan → capital → Tokyo` without proxy substitution (exactly the
Fix 1 collision-free resolve that v11 was supposed to eliminate).

### Fix

Upstream in `tiny-model/dataset-downloader` — the Wikidata entity
extraction pass is dropping valid single-word proper nouns. Likely
causes (to investigate):

1. The per-domain cap in `extract_wikidata` truncates before the
   less-frequent European/Asian capitals.
2. Length or script filters too aggressive.
3. `wikidata_max_entities: 2000` is too tight; raising to 5000 would
   cover most world capitals at the cost of vocab slots.

### Workaround (no rebuild required)

Add a manual `language_extras.wikidata_cities` section to `config.json`
with the ~200 most common world capital/country/major-city names.
Slot cost: ~200. Covers the obvious geography gap without touching
the Wikidata extractor.

```json
"wikidata_cities": [
  "Tokyo", "Madrid", "Athens", "Dublin", "Vienna", "Warsaw",
  "Seoul", "Cairo", "Oslo", "Prague", "Bern", "Lisbon",
  "Kyoto", "Osaka", "Sydney", "Melbourne", "Toronto",
  "Chicago", "Boston", "Seattle", "Denver",
  ...
]
```

## Prioritisation

For a v11.1 rebuild, (1) and (2) are the most impactful — they unblock
prose compilation in general. (3) is a narrow gap that can be patched
via `language_extras` without an extractor rewrite.

- **(1) + (2) together**: ~5-6K new vocab slots, single config change,
  one tokenizer rebuild, one model retrain. Unblocks natural English
  prose for compile experiments.
- **(3)**: ~200 vocab slots via language_extras, or an upstream fix
  in dataset-downloader. Orthogonal to (1) and (2).

All three are **v11-builder config changes**, not tokenizer algorithm
changes. The v11-core runtime, HF compatibility, and `commit+refine`
compilation pipeline all carry over unchanged to v11.1.

## Not a followup

The 7-fix hypothesis was confirmed in exp15. What v11 still needs at
compile time is:

- **Delta-skip** — feature, not workaround. 30-40% of edges typically
  hit this path even on fresh content.
- **Isolated α auto-fit** — replaced by `compile_facts.refine()` for
  facts; still in place for multi-layer passage compilation.
- **Cascade-aware α verify** — same; `max_rounds=15` with real
  convergence detection works reliably.

None of these are blockers for v11. They're the permanent compilation
machinery.
