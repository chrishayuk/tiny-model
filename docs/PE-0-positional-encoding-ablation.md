# PE-0 — v12 Positional-Encoding Ablation

**Pre-registration.** Commit this file and record the sha256 printed at build
time *before* training a single arm or reading a single number. Tag `PE-0`; this
experiment discharges the PE-decision ownership held by CN-8c. It is **step 5**
of the base-model arc — it consumes the step-3 tokenizer and step-4 reference
architecture, and produces the frozen positional mechanism the step-6 base
pretrain uses.

Status at authoring: nothing built. This document is the contract.

---

## 0. Thesis

RoPE is out of v12 entirely — not baseline, not hybrid layer, not training
scaffold, not p-RoPE. The question PE-0 answers is: **given a position-free
attention core, does the model need an explicit positional mechanism, and if so,
which — a learned relative-distance bias, short causal convolution, or both —
and does that mechanism keep position cleanly separable from identity, value,
and role?**

The downstream consumer is the compiler front-end (CF-0): the hub's flagship job
is span-copying and operand binding, so PE-0 selects on marshalling capability
and positional legibility, not perplexity alone.

## 1. Why no RoPE (and no DroPE) — the exclusion is a project constraint

RoPE rotates projected Q/K inside each head; it does **not** rotate the residual
stream the interpretability tooling reads. So the *residual-contamination*
argument for banning RoPE was overstated and is **not** the reason it's
excluded. The actual reasons:

1. **Operational** — the training recipe itself must be RoPE-free.
2. **Experimental-object integrity** — PE-0's question includes *how position
   emerges in a non-rotary architecture*. A network whose weights were formed
   under position-dependent Q/K geometry cannot answer that, even if the
   rotation is stripped at the end.

DroPE (train with RoPE, remove near the end) satisfies neither (2) nor the
operational constraint — its final weights were still shaped under rotary
geometry, and the recipe still requires a RoPE implementation. It is **important
external evidence** (explicit position accelerates optimization; pure NoPE
finishes worse) but is **intentionally outside the v12 design space**. No
further decision required.

## 2. Scope

**In:** position-free attention core; a 2×2 factorial over {learned relative
bias} × {short causal convolution}; ALiBi as a diagnostic reference.

**Out:** RoPE / p-RoPE / DroPE (§1); learned *absolute* embeddings (inject
position into the initial residual — the opposite of the desired property; not
even a control); SSM / recurrent positional carrier (Kimi-KDA style) — the most
interesting long-term direction but it changes the token mixer, state semantics,
kernels, and parameter allocation, so it is a **v13/CN-line** matched
architecture experiment, not on the v12 critical path; regularization and
sharing studies (§8 wave 2).

**Dependencies:** tokenizer frozen (step 3) and reference architecture frozen
(step 4). PE-0 holds *everything non-positional fixed* at the step-4 reference
config — dims, depth, heads, data, tokenizer, optimizer, seed set, token budget,
context length. The only thing that varies across arms is the positional
mechanism. (Assumes the PE choice is stable across nearby dim choices; a
one-off robustness check at a second dim point is a permitted wave-2 add-on, not
a wave-1 gate.)

Context length fixed at **512** (TinyStories sequences are short; 512 is the max
and the size of the relative-bias table).

## 3. Arms

Core 2×2 factorial (bias ∈ {no, yes} × conv ∈ {no, yes}):

| Arm | Rel. bias | Causal conv | Role                                    |
| --- | :-------: | :---------: | --------------------------------------- |
| A0  |    no     |     no      | **pure NoPE — scientific control**      |
| A1  |    yes    |     no      | what explicit relative distance buys    |
| A2  |    no     |     yes     | what local ordered mixing buys          |
| A3  |    yes    |     yes     | are global position and locality complementary? |

Plus one diagnostic (fewer seeds, not a production candidate):

- **D — ALiBi**: fixed per-head slope × distance. Answers "does a little
  monotonic recency suffice, or is a richer learned distance function needed?"

Pure NoPE is the **control, not the default** — the DroPE and multi-query
retrieval evidence (ALiBi/NoPE at ~0–5% on retrieval variants) says it is
genuinely risky; it must *win* to become the recipe, and the prior is that it
won't.

## 4. Mechanism specifications (frozen)

**Relative bias (A1, A3):** a learned scalar added to attention logits before
softmax, indexed by exact causal distance.

```
relative_bias : [n_layers, n_heads, max_ctx]     # per-layer, per-head, exact-distance
distance = query_pos - key_pos                    # causal ⇒ 0 … 511
scores[l,h] += relative_bias[l, h, distance]
```

- **Per-layer, per-head** tables — ~74k params at 12L×12H×512 (≈0.06% of a 115M
  model). Per-layer is deliberate: it lets early layers develop local curves,
  middle layers delimiter/span behaviour, late layers go position-independent —
  the developmental structure PE-0 exists to observe. Layer/head **sharing is a
  wave-2 compression ablation**, not the starting point (sharing first would
  erase the phenomenon being studied).
- **Zero-initialized** — every arm begins as pure NoPE and only learns
  positional preference where data rewards it.
- **Unregularized in wave 1.** No L2. An L2 penalty would make A1 a test of
  *bias + regularization* as one bundle, unattributable — and L2 only shrinks
  magnitudes, it does not buy the sparse legible structure wanted. L1 /
  total-variation / pruning are wave-2 studies (§8).

This is a **T5-style exact-distance relative logit bias** — per-head like T5,
but per-layer and exact-distance rather than T5's log-bucketed layer-shared
form. Proven family (predates RoPE; RoPE's one advantage over it, extrapolation
past training length, is moot at fixed 512), deliberately more granular and
inspectable than T5. Not "reinvented T5," not "novel PE."

**Causal convolution (A2, A3):** short depthwise **causal** convolution applied
to Q/K/V post-projection. Kernel size fixed at **5** for wave 1 (one clean
placement, one size — kernel-size and placement sweeps are wave 2). Provides
local order/adjacency (digits, delimiters, slot boundaries) without any global
position signal. Padding causal (no future leakage).

**ALiBi (D):** standard fixed per-head geometric slopes, `scores -= slope[h] ×
distance`.

## 5. Training (matched across arms)

All arms trained to an **identical token budget** at the step-4 reference config,
same data, tokenizer, optimizer, and schedule. Factorial arms A0–A3 at **≥3
seeds**; diagnostic D at **1 seed**. Runs are M3-overnight-scale per arm (no
rented GPU). The winning arm's recipe *is* the base-model pretrain recipe, so the
token budget is the full base budget, not a fraction.

## 6. Grading

Three panels; the selection rule (§7) combines them with a pre-committed order.

**6.1 LM quality panel** — the standard v-series panel (validation NLL/PPL, plus
whatever fluency/grammar probes the panel already carries). Primary
sanity/quality axis; explicitly *not* the sole selection signal.

**6.2 Interpretability panel** — measures **separability/transfer**, not
"residual stability across positions" (a competent model *should* encode
position; excess stability = failure to represent order). Six instruments:

1. **Probe transfer (translated-matched).** Train number-identity, operand-role,
   delimiter-role, and semantic-identity probes on operands at positions 0–255;
   test unchanged at 256–511 using **translated matched examples** — same
   operands, operation, distractors, and syntactic structure, only the absolute
   offset differs. (Matched translation is essential: first-half-vs-second-half
   with *different content* lets corpus differences masquerade as positional
   non-transfer.)
2. **Subspace overlap.** Principal angles between the decoded position subspace
   and the role / number / semantic subspaces, per layer.
3. **Projection intervention.** Remove the linear position subspace; re-run PPL,
   grammar, marshalling-proxy (§6.3), and copying. What breaks localizes what
   position carried.
4. **Mechanism intervention.** Zero / shuffle / reverse the learned distance
   table at inference; measure degradation. (Decodability shows information is
   *present*; ablation shows it is *used* — decodable-but-unused is a real trap
   this catches.)
5. **Convolution intervention.** Disable / scramble the causal kernels while
   preserving the rest of the checkpoint.
6. **Counterfactual marshalling.** Asymmetric operands, role reversal, distractor
   numerals, variable digit length, equal-value accidental-equivalence controls
   (role = NA on equal-value, per CF-0 §4).

**6.3 Marshalling proxy** — a lightweight span-copy / operand-binding eval that
does **not** require the full CF-0 pipeline (no cell80, no tagger): given a
sequence with numbers at varying distances and roles, copy the operand at a
queried role, across seen and held distances. This is a *proxy* for what CF-0
will later stress — PE-0 must not depend on CF-0 (CF-0 needs the base, the base
needs PE-0; circularity forbidden). The proxy is the marshalling signal PE-0
selects on; the full CF-0 spoke runs later on the chosen base.

## 7. Selection rule (pinned before numbers)

Lexicographic, to avoid selecting the base recipe on perplexity alone:

1. **Quality floor** — discard any arm whose LM-panel PPL regresses beyond ε
   (ε pinned from a dry-run seed-SD, §9) relative to the best arm.
2. Among survivors, **maximize the marshalling proxy** (held-distance span-copy
   accuracy) — the hub's actual job.
3. Tie-break on **positional legibility** — cleanest separability (probe
   transfer + low position/semantic subspace overlap + intervention specificity).

## 8. Wave 2 (only on the selected mechanism — not run in wave 1)

L1 / total-variation regularization (does a few distances / smooth curves
suffice); head- and layer-sharing (can positional specialization be compressed);
distance-table pruning (does the marshalling proxy depend on isolated terms or
broad curves); conv kernel-size and placement sweep; the second-dim robustness
check.

## 9. Predictions (pinned before numbers)

- **PE-P1 (ranking)** — LM quality: A3 ≥ A1 > A2 ≈ D > A0. Pure NoPE trails.
- **PE-P2 (flagship — complementarity)** — bias and conv are **complementary,
  not substitutable**: the 2×2 interaction `(A3−A2) − (A1−A0)` is **positive**
  (super-additive), because relative bias answers *how far* and convolution
  answers *what ordered local neighbourhood* — different problems. Registered as
  a signed interaction contrast with an equivalence bound (non-significance ≠ no
  interaction; if the interaction is within ±δ of zero, the mechanisms are
  additive/independent, which is itself a reportable finding).
- **PE-P3 (where NoPE's cost shows)** — A0's deficit concentrates in the
  **marshalling proxy at held distance**, not in gross PPL. NoPE can look nearly
  fine on perplexity while failing span-copy — which is exactly why §7 selects on
  marshalling.
- **PE-P4 (separability)** — in the bias arms, position is cleanly factored:
  translated-matched probes trained 0–255 transfer to 256–511; projecting out
  the position subspace breaks span-copy but **not** semantic identity.
- **PE-P5 (used, not just present)** — mechanism intervention (zero/shuffle the
  distance table) degrades the marshalling proxy **more** than PPL, showing the
  model *uses* the bias for binding rather than merely encoding decodable
  position.

Inference: seed is the unit for LM-quality contrasts; the translated-matched
eval **cluster** is the unit for probe/marshalling contrasts (N instantiations
of one structure ≠ N independent observations — bootstrap over clusters, seed a
separate variance component). δ and ε set from a dry-run seed-SD, fixed before
the arms run.

## 10. Gates & commitments

- **G-validity** — all arms matched on config, data, budget; ≥3 seeds for
  A0–A3. No arm advantaged by anything but its positional mechanism.
- **G-instrument** — the six interpretability instruments + marshalling proxy
  run on every arm and produce readouts before any selection.
- **No RoPE in architecture or training history** (§1) — enforced, including
  no rotary scaffold at any point.
- **Everything non-positional held fixed** at the step-4 reference config.
- **Unregularized, per-layer-per-head, wave 1** — regularization and sharing are
  wave 2, deliberately after the phenomenon is observed.
- **Measure-once** — panels, instruments, predictions, δ/ε procedure frozen here.
- **Translated-matched probe construction** mandatory (not first/second-half).
- **Intervention tier mandatory** (decodability ≠ use).
- Negative results ship (NoPE winning, or no complementarity, or NoPE's cost
  *not* localizing to marshalling, are all reportable as run).

## 11. Build order & deliverables

1. Freeze reference config (from step 4) + the five arm configs; commit this file
   + sha256.
2. Implement: per-layer/per-head zero-init relative-bias table; short causal
   depthwise conv (k=5, post-QKV); ALiBi slopes.
3. Build the interpretability panel: translated-matched probe set + probe
   trainer; subspace-overlap (principal angles); projection intervention;
   mechanism intervention; conv intervention; counterfactual-marshalling set.
   Build the marshalling proxy eval.
4. Train A0–A3 ×3 seeds + D ×1 seed at matched budget; dry-run first to fix
   δ/ε from seed-SD.
5. Grade all three panels; apply the §7 lexicographic selection rule; freeze the
   winning positional mechanism as the v12 base recipe.
6. Wave-2 follow-ups on the winner only (§8).

**Compute:** step-4 reference (v11/115M-class), full base token budget, 512 ctx.
M3 overnight per arm; no rented GPU.

## 12. Place in the arc

PE-0 (step 5) → frozen positional mechanism → base pretrain (step 6) → CF-0 (first
spoke) on that base. PE-0 uses a *proxy* for marshalling; CF-0 is the real test,
and it can only run once the base exists — hence the strict ordering and the
forbidden circularity. Steps 1–2 (platform, harness) remain the gating
prerequisite for running PE-0 at all: this is the second pre-registered payload
(with CF-0) that commissions the rig.
