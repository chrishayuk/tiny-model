# linguistics/verbnet

VerbNet 3.3 — a hierarchical verb lexicon organised by **Levin classes**.
Each class groups verbs that share syntactic and semantic behaviour (the
"give" class, the "spray/load" class, the "run" class, etc.) and comes
with **thematic roles** (`Agent`, `Theme`, `Recipient`) and **syntactic
frames** (the sentence patterns each verb can appear in).

If WordNet tells you what a verb *means* and FrameNet tells you what
*situation* it evokes, VerbNet tells you how it *behaves grammatically*.
Useful for teaching models argument structure: which verbs take a direct
object, which can be ditransitive, which alternate.

- **Upstream**: https://verbs.colorado.edu/verbnet/
- **Access**: `nltk.corpus.verbnet`
- **Licence**: VerbNet License — free for research and commercial use
- **Layer band**: `syntax`
- **Scale**: ~7k pairs across 3 relations

## Relations produced

| relation | direction | example |
|---|---|---|
| `member_of_class` | directed (verb → classid) | (give, give-13.1-1) |
| `has_role` | directed (classid → role type) | (give-13.1-1, Agent) |
| `has_frame` | directed (classid → frame description) | (give-13.1-1, NP V NP PP.recipient) |

## Provenance

Every triple carries `provenance = classid` (e.g. `give-13.1-1`). That lets
you reconstruct the full class membership even though the triple format
flattens it into pairs.

## Dependencies

- `pip`: `nltk`
- `nltk`: `verbnet`

Downloaded on first run.

## Caveats

- **Class IDs contain digits and dashes** (`give-13.1-1`, `spray-9.7-2`).
  They survive the permissive normaliser intact. On the syntax band
  (strict normaliser) they'd get dropped, so the runner dispatches
  verbnet output via the permissive profile *despite* the `syntax` layer
  band. If you want to keep them in a strict-only pipeline, split them
  into an ID table.
- **Frame descriptions are full grammar fragments** (`NP V NP PP.recipient`).
  They're intentionally not lowercased in spirit, but the normaliser
  lowercases them to `np v np pp.recipient`. This is lossy — the POS tags
  and the PP role become visually ambiguous. If you need the original
  casing, bypass the normaliser for this relation.
- **VerbNet is smaller than you'd expect**: ~270 classes, ~5k verbs, with
  heavy overlap in class membership. Most pairs are `member_of_class`.
- **Selectional restrictions** (e.g. `[+animate]` on an Agent) are not
  currently emitted — the v0.1 downloader had a `selectional_restrictions`
  relation. It's worth adding if the compiler ends up using them.

## Example output

`datasets/extracted/linguistics/verbnet/member_of_class.json`:
```json
{
  "source": "verbnet",
  "relation": "member_of_class",
  "layer_band": "syntax",
  "pair_count": 5000,
  "pairs": [
    ["give", "give-13.1-1"],
    ["hand", "give-13.1-1"],
    ["lend", "give-13.1-1"]
  ]
}
```

See [`examples/sample_output/linguistics/verbnet/`](../../examples/sample_output/linguistics/verbnet/)
for a trimmed snapshot.
