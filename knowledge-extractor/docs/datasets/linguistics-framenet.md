# linguistics/framenet

Berkeley FrameNet 1.7 — a lexical resource built around **frames**, which
are schematic representations of situations (buying, arguing, transporting).
Each frame has a set of **frame elements** (roles like `Buyer`, `Seller`,
`Goods`) and is evoked by a set of **lexical units** (the verbs, nouns, and
adjectives that invoke it). Frames are connected by a hierarchy (inheritance,
use, subframe, ...).

FrameNet is how you teach a model that "sell", "purchase", and "acquire"
are all about the same *situation*, even when WordNet would put them in
different synsets.

- **Upstream**: https://framenet.icsi.berkeley.edu/
- **Access**: `nltk.corpus.framenet` (nltk package `framenet_v17`)
- **Licence**: FrameNet Data Release License — free for research and commercial use with attribution
- **Layer band**: `syntax`
- **Scale**: ~39k pairs across 4 relations

## Relations produced

| relation | direction | example | what it means |
|---|---|---|---|
| `evokes_frame` | directed (word → frame) | (buy, Commerce_buy) | this word triggers this frame |
| `frame_lexicon` | directed (frame → word) | (Commerce_buy, purchase) | this frame is triggered by these words |
| `frame_element` | directed (frame → role) | (Commerce_buy, Buyer) | this frame has this role |
| `frame_parent` | directed (parent → child) | (Transfer, Giving) | inter-frame hierarchy |

`evokes_frame` and `frame_lexicon` are duals — you get both so downstream
compilers can pick the direction they need without re-indexing.

## Provenance

- `evokes_frame` and `frame_lexicon`: `provenance = frame.name`
- `frame_element`: `provenance = "<frame_name>/<core_type>"` where `core_type`
  is one of `Core`, `Core-Unexpressed`, `Peripheral`, `Extra-Thematic` — lets
  downstream code split obligatory vs optional roles
- `frame_parent`: `provenance = <relation_type>` (`Inheritance`, `Using`,
  `Subframe`, `Perspective_on`, `Causative_of`, `Inchoative_of`, `See_also`,
  `ReFraming_Mapping`, `Precedes`)

## Dependencies

- `pip`: `nltk`
- `nltk`: `framenet_v17`

Downloaded on first run.

## Caveats

- **Frame names are CamelCase with underscores** (`Commerce_buy`,
  `Motion_directional`). The permissive normaliser preserves them; the strict
  normaliser (used on the syntax band) lowercases to `commerce buy`. That's
  intentional — a frame name is syntax-band vocabulary, not an opaque ID.
  If you need to round-trip back to the original CamelCase, keep a mapping
  table alongside.
- **Lexical units have POS suffixes** in FrameNet (`buy.v`, `purchase.v`).
  The extractor strips them (`lu.name.split(".")[0]`) so pairs are clean
  word→frame. The POS is recoverable from WordNet if you need it.
- **Frame relations are sparse** — about 1.7k edges across 1.2k frames.
  Don't expect a dense DAG.
- **Not every FrameNet frame is textually common.** A few dozen frames
  cover the bulk of everyday language; the long tail (`Scrutiny`,
  `Forging`, `Waking_up`) is present but rare. Frequency filtering is
  up to the compiler.

## Example output

`datasets/extracted/linguistics/framenet/evokes_frame.json`:
```json
{
  "source": "framenet",
  "relation": "evokes_frame",
  "layer_band": "syntax",
  "pair_count": 15000,
  "pairs": [
    ["buy", "commerce buy"],
    ["purchase", "commerce buy"],
    ["acquire", "getting"]
  ]
}
```

See [`examples/sample_output/linguistics/framenet/`](../../examples/sample_output/linguistics/framenet/)
for a trimmed snapshot.
