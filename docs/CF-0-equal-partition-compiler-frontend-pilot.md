# CF-0 — Equal-Partition Compiler-Frontend Pilot

**Pre-registration, rev 3 (frozen).** Commit this file and record the sha256
printed at build time *before* building a single frame or running a single
number. Tag `CF-0` (Compiler Frontend, experiment 0) — kept **distinct** from
CN-8: CF-0 is the reusable compiler-front-end platform (executable-frame schema,
no-call taxonomy, counterfactual validator, tool-dependence grader, factorial
split machinery); CN-8 *consumes* CF-0 as its first concrete grader experiment.

Scope is closed. Rev 3 changes are encoding-only — no new scientific question.
Status at authoring: nothing built. This document is the contract.

- **CF-0** — is the compiler-front-end machinery valid, attributable, trainable?
- **CF-1** (separate) — does competence transfer between semantic subfamilies
  that lower to the same instruction? CF-1 inherits CF-0's schema, grader,
  validator, and G4 verdict, and is where the tagger first exists.

---

## 0. One-line thesis

cell80 is a deterministic instruction set. This programme trains the
natural-language **compiler front-end** for it:

```
source + task context → typed program AST → executable cell call
source + task context → typed abstention
```

Routing and marshalling are learned; calculation stays in the executor. CF-0
establishes the machinery on the **equal-partition** subfamily and factorises
the axes R1's 12-template midtrain conflated.

## 1. What CF-0 tests (and what it does not)

**Tests:** Q1 surface — held phrasing within a seen construction generalises?
Q2 construction — held structural cluster generalises? Q3 magnitude — operands
extracted size-invariantly, or a copy-span cliff? Q4 abstention — declines
correctly, routing on **intent** not trigger words?

**Does NOT do (scope guards, enforced):** no tagger (frames hand-built); no scale
harvest (FineWeb only for the surface-source arm, small slice, phrasings only);
no cross-subfamily transfer (equal-partition only — that is CF-1); no online RL
(deferred behind §7 traction gate); no base-changing skills.

## 2. The object: executable semantic frame

```
surface_template        # skeleton with typed holes, register-banded
program_ast             # divide(dividend=slot(A), divisor=slot(B))
slots[]:
  semantic_role         # total_items | recipient_count | ...
  source_span           # exact char span in the original sentence
  value_type; unit; constraints
guards                  # recipient_count > 0
output_semantics:
  type; unit; rounding  # items_per_recipient ; item ; exact_or_remainder
equivalent_programs[]
context_requirement     # standalone | needs_prior_sentence | hypothetical
task_context:           # ROUTE DEPENDS ON THIS, not the sentence alone
  user_intent           # answer_question | extract_claim | summarise | classify
  query_span; evidence_context
call_policy:
  decision              # call | abstain
  abstain_reason        # §3 taxonomy
register                # in | near | off
construction_features   # {voice, operand_order, mood, coreference, ...}
pool                    # positive | abstain | hard_negative
provenance
validation_evidence     # counterfactual re-instantiation record (§4)
confidence
split_cluster           # train/eval wall by STRUCTURE, not string
group_id                # sibling-atomic split unit (§5.2) — INDIVISIBLE
```

**Ordering rule (fixed):** type and validate **before** stripping values — the
span carries typing evidence (currency, unit noun, plural morphology,
decimal/ordinal form). Preserve {original sentence, spans, parsed values+units,
roles} first; synthesise instantiations after.

## 3. No-call taxonomy and the three pools

Route depends on `task_context`, not the trigger sentence. "The program divides
the payload across shards" is no-call as a bare statement, callable under a
query intent. Committed abstain reasons: `not_applicable` (no arithmetic
relation), `underspecified` (no unique answer), `already_resolved` (answer given
in context), `descriptive_not_queried` (computable, no query targets it),
`quoted_or_hypothetical_not_targeted`.

Pools: **positive** (query intent present → call), **abstain** (one reason above
→ no-call), **hard-negative** (high lexical overlap → no-call).

**Intent minimal pairs:** each `descriptive_not_queried` hard-negative carries
its matched positive — same trigger sentence, query intent added → call. Routing
on lexical trigger rather than intent splits the pair; P4/G2 catch it.

Training mix: positive : abstain : hard-negative ≈ **50 : 20 : 30**.

## 4. Frame construction & the counterfactual validator

Hand-build ~200–400 equal-partition frames across pools. Each **positive** frame
passes counterfactual re-instantiation with these role diagnostics:

- **Strongly asymmetric** (dividend ≫ divisor) — role reversal visibly changes
  the answer. **This row exposes role errors.**
- **Equal values** (dividend = divisor) — role **unidentifiable** (a/a = a/a
  under swap). Marked **role = NA**; kept only as an accidental-equivalence
  control proving execution-correct ≠ role-correct.
- **Rounding-safe** — integer truncation/rounding cannot collapse the two
  orientations to one output.
- **Unit-asymmetric** — reversal is dimensionally invalid.
- **Duplicate distractor values** — a second copy of an operand value elsewhere,
  so selecting by *value* rather than *source span* is exposed.

Require: re-instantiated question stays coherent and uniquely answerable;
asymmetric/unit probes produce detectably wrong results under reversal. The
validator audits the **dataset**, not only rollouts.

## 5. Factorial evaluation — named exposure regions, no generic "held"

The generic label `held magnitude` is **removed** from all manifests and result
tables (its meaning would drift between O1 and O3). Every reported row carries an
unambiguous exposure history. Magnitude regions (§5.1): **SFT-seen** 1–3 (gold
demos), **boundary** 4 (probe), **verifier-only** 5–7 (O2 may search+verify, no
gold), **untouched-transfer** 9–12 (never seen by SFT / rejection / distillation
/ model-selection).

Operational definitions, frozen: **surface** = lexical/phrasal realization
*within* a construction; **construction** = whole structural realization pattern
(active/passive, recipient-first/total-first, interrogative/declarative,
coreference), a held construction being a whole `split_cluster` absent from
training, not a post-hoc feature combination; **seen surface** = never an exact
training sentence, fresh values and nuisance content.

**Eight unique positive conditions**, split into two grids so every row has one
exposure history:

Linguistic grid (magnitude fixed at SFT-seen — isolates linguistic transfer):

| Surface | Construction | Region   |
| ------- | ------------ | -------- |
| seen    | seen         | SFT-seen |
| held    | seen         | SFT-seen |
| seen    | held         | SFT-seen |
| held    | held         | SFT-seen |

Magnitude sweep (linguistic condition fixed at seen/seen — isolates the cliff):

| Surface | Construction | Region             |
| ------- | ------------ | ------------------ |
| seen    | seen         | SFT-seen           |
| seen    | seen         | boundary           |
| seen    | seen         | verifier-only      |
| seen    | seen         | untouched-transfer |

Plus one deliberately hard conjunction (the combined objective):

| Surface | Construction | Region             |
| ------- | ------------ | ------------------ |
| held    | held         | untouched-transfer |

Abstention, register, and distractor probes sit outside these grids.

### 5.2 Sibling-atomic splitting (enforced invariant)

`split_cluster` disjointness is necessary but not sufficient — generated
families leak across it. The following are **indivisible**, share one `group_id`,
and the harness asserts `one group_id → exactly one of {train, calibration,
eval}`:

- intent-positive / intent-negative minimal pairs;
- all counterfactual re-instantiations of one semantic frame;
- equal / asymmetric / unit / distractor diagnostic siblings;
- PCFG and FineWeb realizations of the same semantic construction;
- duplicate / near-duplicate FineWeb specimens.

Without this, one side of an intent pair (or one operand realization) teaches the
answer to its matched eval sibling despite nominal sentence-level disjointness.

## 6. Metrics: six-stage decomposition (frozen)

Per rollout, attributable: **Route** (call-or-not + family; abstain/hard-neg
correct = no-call), **Schema** (valid call), **Span** (correct source spans),
**Role** (each value in correct argument — emits **pass/fail/NA**; NA on
unidentifiable rows; **role-accuracy aggregates pass+fail only, NA never scored
pass**), **Execution** (returns target), **Provenance** (derived from the call,
tested by cell-result swap: inject a wrong return; correct = report the injected
value; reporting the right answer despite wrong injection = internal compute =
FAIL). Reported per cell × grid-row × region × seed.

## 7. Arms & the optimizer ladder

**Data-source arms** — same hand-built ASTs, surfaces differ: **A1** PCFG-only,
**A2** FineWeb-only (phrasings only, operands re-synthesised per §5.1), **A3**
union. **Fairness:** compared at **equal admitted-M1 units** and **equal
training-token budget**; report both + optional dose curve.

**Optimizer stages**, each a distinct claim:

- **O1 — SFT** on randomised valid calls. *Can imitation install it?*
- **O2 — rejection-search readout, NO weight update.** *Does valid behaviour
  exist in sampled support?* Acceptance predicate, pinned:
  `call_valid = route_pass ∧ schema_pass ∧ span_pass ∧ role_pass ∧
  execution_pass`. Role-**NA** rows are **excluded from acceptance** and used
  only as diagnostic controls. Sampling budget frozen: **K ∈ {1, 4, 16, 64}**
  (yield curve), temperature / top-p / top-k / max-length fixed at build,
  committed prompts-and-samples per structural cluster, permutation-null
  construction pinned. Record raw valid-call rate, P(≥1 valid in K), six-stage
  failure location, excess verified yield over null, accepted-trajectory
  distribution. ("No support at K=4" and "support at K=256" are different
  findings — support existence is inseparable from budget.)
- **O3 — successful-trajectory distillation, weight update.** Distil on accepted
  trajectories; test at **K=1** including untouched-transfer. For distillation,
  acceptance additionally requires provenance:
  `trajectory_valid = call_valid ∧ provenance_pass` — otherwise O3 distils calls
  that ignore the return and compute internally, the exact defect the grader
  exists to expose. **Run O3 on all three data arms** (CF-0 is small; this buys
  a balanced data-source × optimizer design and avoids winner's-curse from a
  single advancing arm).
- **RL — deferred.** *Improve beyond distilled support?* Gate: O3 K=1 ≥ **0.15**
  on the target region *(placeholder — repin from the O1/O3 dry-run)*.

**Gating ladder:** O1 K=1 → O2 best-of-K yield vs null → O3 K=1 → RL gate.

## 8. Gates

- **G1 frame trust** — 100% of positives survive §4 (blocking).
- **G2 abstention balance** — hard-neg no-call ≥ 0.90; positive call-rate not
  degraded > 5% rel. vs abstain-free control; intent minimal pairs split
  correctly above chance.
- **G3 cliff readout** — held-magnitude span accuracy per arm × stage × **named
  region**. Measurement, not pass/fail.
- **G4 FineWeb earns it** — A2/A3 beat A1 on held-construction accuracy by the §9
  interaction test (not bare significance). Fail → revert to synthesis-only.

## 9. Predictions & inference

- **P1** — under O1, all arms show the copy-span cliff: optimizer-shaped, not
  data-shaped.
- **P2** — O3 narrows the cliff more than surface diversity, **and the effect
  reaches the untouched 9–12 band** (transfer beyond verifier support), not only
  verifier-only.
- **P3 (flagship, double dissociation)** — data-source improves *construction*;
  optimizer stages improve *magnitude*; each adds little to the other's axis.
- **P4** — without hard-negatives and intent pairs, false-call rate on
  near-neighbours ≫ chance and intent pairs fail to split (routes on trigger
  words). **Identified by the §7.1 ablation.**
- **P5** — a non-zero fraction of O1's execution-"correct" answers fail the
  provenance swap, concentrated at seen magnitude.

### 7.1 P4 training ablation (matched budget, A3/O1 only)

- **N2 full** — positives + abstentions + hard-negatives + intent pairs.
- **N1 no intent pairs** — same quantities and hard-negatives, no matched
  ±intent construction.
- **N0 no negative-space** — abstention/negative tokens replaced by additional
  positives, token count held fixed.

Identifies: N2 vs N1 (do matched intent pairs teach contextual routing beyond
generic negatives), N1 vs N0 (does negative space suppress trigger eagerness),
N2 vs N0 (full compiler-with-decline effect). Without a matched-budget arm, P4 is
rhetorical, not identified.

### 9.1 Inference (non-significance ≠ no effect)

P3 is established only by pre-registered interactions + equivalence bounds:
(1) data-source × axis interaction; (2) optimizer-stage × axis interaction;
(3) equivalence bound `δ = c × SD_calibration`, where **c is fixed now**, the
**calibration seeds and split are fixed now and quarantined** from the main
analysis, and **calibration cannot select models, arms, or checkpoints**. This is
a precision-scaled equivalence bound, not a "smallest effect of practical
interest" — a separate discarded calibration run prevents observed O1 results
from setting how easy P3 is to establish. Inference is **cluster-level**
(bootstrap or mixed-effects over `split_cluster`, seed a separate variance
component). N operands on one frame is **not** N independent observations — the
unit of evidence is the structural cluster.

*(c and the calibration seed set are the two values frozen in the committed
build config alongside this file's hash.)*

## 10. Commitments

Prereg before numbers (sha256); §6 metrics, §9 predictions, δ's c + calibration
split frozen. **M1 stays the frozen admission gate** — constructional-coverage is
a candidate audit row until it passes DIV-0-grade retrodiction. Train/eval wall:
eval `split_cluster`- and `group_id`-disjoint from all training + calibration,
skeleton-disjoint from the frozen FS-bank; overlaps quarantined. Measure-once;
multi-seed. Data-arm fairness reported. Negative results ship. Teachers as
**proposers not authorities** (forward, for CF-1's tagger).

## 11. Build order & deliverables

1. Hand-built frames (3 pools + intent pairs) + counterfactual validator → G1.
2. Six-stage grader (route/schema/span/role[pass/fail/NA]/execution/provenance
   swap).
3. Split harness — FS-bank + `split_cluster` + **`group_id` sibling-atomic**
   invariant + named magnitude regions.
4. Data-source corpora (PCFG gen, small FineWeb harvest surfaces-only, union);
   uniform-stratified slots; equal-M1/equal-token budgeting.
5. O1 SFT across A1/A2/A3 multi-seed → G2, G3, G4, P1, P5, δ calibration (on the
   quarantined split), the §7.1 N0/N1/N2 ablation → P4.
6. O2 readout (K-curve, all arms) → support/yield/failure-location; O3
   distillation **all three arms** → P2, P3(magnitude incl. untouched), cliff
   curve.
7. Results (six stages × grid × region × arm × seed) + plots: held-out accuracy
   vs data-source; magnitude-cliff vs optimizer stage across named regions;
   interaction estimates with cluster-level CIs.

**Compute**: v11-class 115M base, midtrain-scale. M3 overnight per arm (mlx-rs
optional); no rented GPU for CF-0.

## 12. Why CF-0 matters beyond CF-0

Every catalogued failure — KnnStore canonical→narrative collapse, marshalling
slot bug, off-distribution cliff, GPT-OSS brittleness — becomes a **named
compiler defect** owned by a pipeline stage. The thesis, properly conditional:

> Natural-language compilation factorises — **corpus diversity supplies unseen
> source constructions, verifier search installs size-invariant marshalling
> (transferring beyond its own exploration support), and deterministic execution
> removes computation from the learned model.**

If P2's untouched-band transfer and P3's double dissociation both hold, that is
the evidence. If either fails, CF-0 has located precisely where language
construction and marshalling remain entangled — reported as run.
