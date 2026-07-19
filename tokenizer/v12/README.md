# v12 Tokenizer — TOK-0/TOK-1 Harness + First Real Candidate

Implements the TOK-0 deliverables from `v12-tokenizer-design-funnel.md`
(DRAFT v0.5): the harness, the pin file, target-set stubs, the candidate
grid, and the dormant-block map schema — plus, as of 2026-07-19, a real
(prototype-scale) C8 corpus and the first genuinely-trained TOK-1
candidate tokenizer.

Tracked in the `chuk-experiments` server under programme `v12-tokenizer`,
experiments `tok-0-harness-pinning` through `tok-5-freeze`.

## Layout

```
tokenizer/v12/
  pins/tok0_pins.yaml        frozen commitments C0-C10 + open numeric PINs
  candidate_grid.yaml        TOK-1 4x4x3 grid + ABL-1 + Branch B + shadow lane
  dormant_block_map.yaml     C7 immutable vocab-block schema
  targets/                   t_core / t_cell / t_num / t_scale seed sets

  bench/                     all runnable harness code + its data
    tokenizer_bench.py       CLI: census, intrinsics, g0-smoke, roundtrip, grid-screen
    g1_selection.py          Gate G1 selection algorithm (Pareto frontier + rejects + tie-break)
    test_g1_selection.py     unit test against synthetic fixtures, 11/11 pass
    msi/
      canonicalizer.py             MSI class-1/2/3 transducer (Python)
      parity_vectors.jsonl         golden vectors shared by both languages
      test_canonicalizer_parity.py Python side of the parity check
      frame_battery.jsonl          T-num probes x 4 framing contexts
    reports/                 run output lands here (gitignored)

  corpus/                    C8 corpus assembly (scripts + manifests tracked;
                              the bulk .jsonl/.txt dumps are gitignored --
                              regenerate via the scripts below, or pull the
                              real artifact from chuk-experiments)
    build_code_corpus.py       harvests this repo's own source into the C8 code domain
    c8_code_corpus_manifest.json    95 files, 7 languages, sha-pinned per file
    assemble_c8_corpus.py      streams TinyStories + samples cn7/cn8 math + loads code
    c8_manifest.json           the real C8 manifest: domains, byte counts, mixture, seed
    c8_code_corpus.jsonl / c8_corpus_v0.jsonl / .txt   (gitignored, regenerable)

  training/                  candidate training + real evaluation (scripts
                              tracked; trained candidates/ and candidates.jsonl
                              are gitignored -- they're registered as real
                              artifacts in chuk-experiments instead)
    train_candidate.py         trains a real SentencePiece candidate on corpus/c8_corpus_v0.txt
    train_byte_level_bpe.py    trains a real byte-level BPE candidate (tokenizers library)
    build_pure_byte_vocab.py   builds the deterministic 260-token Branch B vocab
    evaluate_candidate.py      evaluates every candidate through its own real library
    candidates/<id>/           (gitignored) trained .model + vocab.json per candidate
    candidates.jsonl           (gitignored) real per-candidate evaluation rows

tokenizer/v12-msi/           Rust side of the MSI canonicalizer, workspace member
  Cargo.toml
  src/lib.rs                canonicalize_identity + #[test] against the same
                             parity_vectors.jsonl the Python side uses
```

## Status

- `bench/tokenizer_bench.py` — working CLI: `census`, `intrinsics`, `g0-smoke`.
  Runs today against the real v11 artifacts (`../../v11/artifacts/v11.vocab.json`)
  and the real (small) sample corpus (`../../v11/corpus/**`). This is a
  **smoke test of the harness code**, not Gate G0 itself — G0 requires
  the pinned 24M-token C2 atlas stream, which lives in the corpus-atlas
  programme and is not present in this repo yet.
- **MSI canonicalizer class-1 parity: done, both languages, verified.**
  `bench/msi/canonicalizer.py::canonicalize_identity` and the `v12-msi`
  Rust crate's `canonicalize_identity` both run against the same 9 golden
  vectors in `bench/msi/parity_vectors.jsonl` and agree line-for-line —
  `python3 tokenizer/v12/bench/msi/test_canonicalizer_parity.py` and
  `cargo test -p v12-msi` both pass. The class-2 collapsing-merge case is
  still a stub on both sides — it needs a real TOK-1 candidate's merge
  table, which doesn't exist yet.
- **Round-trip + UNK gate: run for real against the compiled v11 binary — found a genuine
  incumbent defect, root-caused, and FIXED.** `bench/tokenizer_bench.py roundtrip` shells
  out to `target/release/v11` (build first: `cd tokenizer && cargo build --release -p
  v11-cli`) and checks exact round-trip on all 32 files in `../../v11/corpus`. Original
  result: UNK gate passed (0 UNK anywhere), but round-trip failed on 32/32 files. Root
  cause: `v11-core`'s `pretokenize_chunks()`/`metaspace()` treated any ASCII whitespace as
  a chunk delimiter, but real HF `Metaspace` splits only on the literal space character
  (0x20) — verified directly against the `tokenizers` library. **Patched** (both functions
  now split on 0x20 only; 18/18 v11-core tests pass, 4 new regression tests added) and
  **verified**: the compiled Rust binary now matches real HF `tokenizers` token-for-token
  on the file that originally exposed the gap (115 tokens, 1 UNK, identical). Disclosed
  side effect, not hidden: this correctly reveals a separate, pre-existing vocab coverage
  gap — v11's vocab has no piece for a literal tab/newline, so `unk_gate_pass` now
  correctly fails (662 UNK across the 32-file sample; code files hit hardest via
  indentation) instead of masking it. Round-trip still fails 32/32 files, now for the
  honest reason. Full detail in `pins/tok0_pins.yaml` `incumbent_ledger` and the
  `tok-0-harness-pinning` writeup (chuk-experiments).
- **Bigger, unresolved finding surfaced while verifying the fix: a real 3-way tokenizer
  divergence.** Native SentencePiece loading the actual, sha-verified `v11.model` (the file
  `corpus-atlas`'s pipeline used to build the already-frozen C2 eval stream) disagrees with
  both the old and the now-patched Rust/`tokenizer.json` pair — 99 tokens/0 UNK vs 115/1 on
  the same file. Root cause: `v11.model`'s own `normalizer_spec` (`nmt_nfkc`,
  `remove_extra_whitespaces: True`) collapses all whitespace before tokenizing;
  `tokenizer.json` has `normalizer: null` — that step was dropped at export time, a
  distinct and earlier bug than the one just fixed. This means the pinned C2 stream was
  built with a tokenizer that disagrees with the artifacts this repo's harness and Rust
  runtime actually use — real tension with commitment C5. **Not resolved here** —
  reconciling it means deciding which artifact is canonical, which is Chris's call, not an
  engineering decision to make solo mid-session. See `pins/tok0_pins.yaml`
  `incumbent_ledger.MAJOR_2026_07_19_three_way_divergence`.
- **Gate G1 selection algorithm: implemented and unit-tested, not just scaffolded.**
  `bench/g1_selection.py::select_survivors` runs the doc's own funnel verbatim
  (hard rejects → threshold rejects → Pareto frontier over the four pinned axes →
  ≤1 survivor per family via tie-break). `bench/test_g1_selection.py` proves it
  correct against 12 hand-designed synthetic candidates (11/11 checks pass) —
  dominance, tie-break, both threshold axes, both hard-reject paths, incumbent/
  Branch-B exemption, shadow passthrough. Wired into `tokenizer_bench.py
  grid-screen`, which correctly refuses to run against this repo's real,
  still-undecided pins rather than inventing defaults. What's blocked is the
  *input* (real TOK-1 candidates need the C8 corpus + training tooling), not
  the algorithm.
- **C2/C3 corpora: found, real, referenced in place (not copied).** A
  sibling repo, `cell80/experiments/corpus-atlas`, already has the exact
  24M-token atlas eval stream the doc describes (16M seed42 + 8M seed43,
  MAX_SEQ 256, tokenized with the real v11 model, sha-verified) and a
  held-out slice (`div0_heldout.json`) with a genuine prefreeze-exposure
  appendix. Full provenance recorded in `pins/tok0_pins.yaml`. The
  held-out slice's own rule says it's scored once and not to be
  reselected — treated as a reference pattern for v12, not reused outright.
- **C8 corpus: real v0 mixture assembled, not just planned.** Prose
  streams live from `roneneldan/TinyStories` (same pinned hub revision as
  C2). Math+structured is sampled from real cn7/cn8 cell-calling corpora
  in `cell80/experiments/cell-native-architectures`, referenced in place.
  Code didn't exist anywhere on this machine, so `build_code_corpus.py`
  harvested this repo's own Rust/Python/etc. source (95 files, 7
  languages, 299KB). `assemble_c8_corpus.py` combines all three into
  5,595 rows / 1.9MB — see `c8_manifest.json` for exact composition,
  mixture proportions (**provisional v0**, not the frozen commitment),
  and what's not yet implemented (dedup, C3-exclusion, repeated-identifier
  cap).
- **First real TOK-1 candidate: trained, not simulated.**
  `train_candidate.py` ran actual `sentencepiece` unigram training
  (vocab 4000, `split_digits=True` per C6) on the v0 C8 corpus —
  `candidates/unigram_sp_4000_v0/`. Evaluated with `census`/`intrinsics`
  against the same sample corpus used for v11's g0-smoke: five-way census
  `{1:1, 2:3, 3:0, 4:0, 5:3206}`, compression 0.328 tok/byte, fertility
  17.09 pieces/word (genuinely mediocre — a tiny prose-heavy vocab
  evaluated against a code-heavy sample; reported as measured, not tuned).
  Along the way, found and fixed a real harness bug: `intrinsics` was
  counting unmapped/failed matches toward `total_tokens`, silently
  inflating compression/fertility on any candidate with nonzero unmapped
  chars.
- **Grid expanded to 9 real candidates + the v11 incumbent, all evaluated
  through real libraries.** `train_byte_level_bpe.py` (via the
  `tokenizers` library's `ByteLevelBPETokenizer`) and
  `build_pure_byte_vocab.py` (deterministic 260-token byte map, no
  training) added the `byte_level_bpe` and `pure_byte` (Branch B) families
  alongside `unigram_sp`/`bpe_sp`. `evaluate_candidate.py` evaluates all
  10 rows (each through its own real backend — sentencepiece / tokenizers
  / a direct byte map — not the harness's approximate simulator) into
  `candidates.jsonl`, in exactly the schema `g1_selection.select_survivors`
  consumes. Three real findings, all disclosed:
  - SentencePiece hits hard vocab ceilings on the 1.9MB v0 C8 corpus —
    unigram ≤6923, bpe ≤20743 — a corpus-scale artifact, not a library
    bug; trained near-ceiling candidates instead of the originally
    planned sizes.
  - `pure_byte_v0` measures MSI-strict = 1.0 exactly across all 116
    `frame_battery.jsonl` instances — an empirical confirmation of the
    design doc's pre-registered prediction P10'(b).
  - Every `unigram_sp`/`bpe_sp` candidate shows `round_trip_pass=false,
    unk_count=144` on the real v11 corpus sample; `byte_level_bpe` and
    `pure_byte` both show `round_trip_pass=true, unk_count=0` — the
    compression-vs-coverage tradeoff Gate G1's Pareto frontier exists to
    surface.
  - Also found, while building the incumbent's evaluation path: a genuine
    Python/Rust parity gap distinct from the whitespace bug above (114 vs
    115 tokens, 0 vs 1 UNK on the same file via two v11 loaders) — see
    `pins/tok0_pins.yaml` `incumbent_ledger.newly_discovered_2026_07_19_b`.
    `candidates.jsonl`'s `v11_incumbent` row carries a `CAVEAT_parity_gap`
    field rather than being presented as authoritative.
  Real `grid-screen` selection is still correctly blocked — see below.
- Everything under `targets/` is seed content, not the frozen C8-derived
  sets — `t_core` in particular is illustrative only.
- `pins/tok0_pins.yaml` — commitments C0–C10 are filled in from the
  design doc; the numeric bands (δ_switch, Δ, ε_match, MSI_canonical_min,
  F_max, R_max, N, W, ...) are explicit `PIN: null # not yet decided` —
  these are research decisions for Chris, not something to invent.

## Not done here (needs compute / corpus / a human decision)

The real `grid-screen` (screening the full 4×4×3 candidate grid) needs
`census_F_max`/`census_R_max`/`MSI_canonical_min` decided — that's now
the *only* blocker: `candidates.jsonl` has 9 real candidates + the
incumbent ready as input, and `g1_selection.select_survivors` is
implemented and unit-tested. This is a research decision for Chris, not
an engineering gap. TOK-2a/b/c through TOK-4 model
training and TOK-5 freeze need GPU compute and/or the frozen C10
mini-ladder corpus (not yet built, no precedent found anywhere). Those
are registered as experiments and queued as runs in `chuk-experiments`.
The class-2 canonicalizer (and its parity check) is blocked the same
way — it needs a real candidate's merge table.
