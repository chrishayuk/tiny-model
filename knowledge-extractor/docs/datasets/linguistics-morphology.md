# linguistics/morphology

Inflectional and lightweight derivational morphology for English. Two
sources are combined:

1. **lemminflect** — a rule-based English inflector. Given a base form,
   it returns the plural, past tense, gerund, comparative, etc. Candidate
   base forms come from the **Brown corpus**, restricted to the 20k most
   frequent lemmas.
2. **WordNet derivations** — for derivational patterns (verb → agent noun,
   adjective → abstract noun), we walk `lemma.derivationally_related_forms()`
   and filter by suffix.

Purpose: give the syntax band explicit pairs for the morphological
relations that WordNet doesn't carry directly (WordNet knows "decide" and
"decision" are related, but not that "big/bigger/biggest" share a root).

- **Upstream**: [lemminflect](https://github.com/bjascob/LemmInflect), Brown corpus (NLTK), WordNet (NLTK)
- **Licence**: MIT (lemminflect) + CC (Brown) + Princeton (WordNet)
- **Layer band**: `syntax`
- **Scale**: ~35k pairs (estimated; see "known issues" below)

## Relations produced

| relation | direction | example | tag |
|---|---|---|---|
| `plurals` | directed | (cat, cats) | `NNS` |
| `verb_past` | directed | (run, ran) | `VBD` |
| `verb_past_participle` | directed | (run, run) | `VBN` (may be filtered as self-loop) |
| `verb_gerund` | directed | (run, running) | `VBG` |
| `verb_3rd_person` | directed | (run, runs) | `VBZ` |
| `comparative` | directed | (big, bigger) | `JJR` |
| `superlative` | directed | (big, biggest) | `JJS` |
| `agent_noun` | directed | (write, writer) | WN deriv., -er/-or/-ist |
| `nominalization` | directed | (happy, happiness) | WN deriv., -ness/-ity/-cy |

## Configuration

`configs/tier1.yaml`:
```yaml
morphology:
  vocab_limit: 20000    # top-N Brown words to seed with
  per_pos_limit: 3000   # candidates per POS (NOUN/VERB/ADJ)
```

Lowering `per_pos_limit` gives you a quick smoke-test run; raising it
pulls in rarer forms at the cost of runtime.

## Dependencies

- `pip`: `lemminflect`, `nltk`
- `nltk`: `brown`, `universal_tagset`, `wordnet`, `omw-1.4`

## Caveats

- **Irregular forms are the whole point.** Regular plurals (cat → cats)
  and regular pasts (walk → walked) are also valuable because the model
  needs to learn the *boundary* between regular and irregular, not just
  the exceptions. Both are emitted.
- **Self-loops get dropped** by the normaliser. This kills verb past
  participles for verbs where past and participle are identical (`read`,
  `cut`, `put`) — you'll see `verb_past` pairs for them but not
  `verb_past_participle`. If you need the self-loop preserved as a
  "no-change" signal, patch the normaliser's self-loop check.
- **POS ambiguity**: a word like `run` is a noun and a verb. The extractor
  iterates POS categories and tries each, so `run` can show up in both
  `plurals` (runs) and `verb_3rd_person` (runs). That's fine — they're
  different relations.
- **Brown is from 1961.** Frequency rankings skew slightly archaic
  (`shall`, `thou`) but not enough to matter at 20k cutoff.
- **Derivational coverage is narrow.** `agent_noun` and `nominalization`
  only catch suffix-based derivations that WordNet already knows about.
  Zero-derivation (`walk_v` → `walk_n`) is *not* captured here — that's
  a WordNet `derivations` relation.

## Known issues

- **Broken on some numpy/spacy binary combos.** `lemminflect` imports
  `spacy`, which imports `thinc`, which on the current dev machine
  hits a numpy ABI error (`numpy.dtype size changed, may indicate
  binary incompatibility`). Fix by pinning `numpy<2` or rebuilding
  thinc. Not a framework bug — the extractor runs cleanly on a fresh
  environment. See `ROADMAP.md#known-issues`.

## Example output

`datasets/extracted/linguistics/morphology/plurals.json`:
```json
{
  "source": "morphology",
  "relation": "plurals",
  "layer_band": "syntax",
  "pair_count": 2800,
  "pairs": [
    ["cat", "cats"],
    ["mouse", "mice"],
    ["child", "children"]
  ]
}
```
