# LARQL Benchmark Coverage Analysis

**Spec v0.1 — What Do We Already Cover?**

Chris Hay | LARQL Project | April 2026

---

## 1. Purpose

Before downloading more data, measure what the current 1.15M pairs already
cover against real benchmarks. This tells us whether the bottleneck is
data coverage or something else (reformulation, compilation, attention quality).

The analysis answers three questions:

1. **What fraction of benchmark questions can our graph answer today?**
2. **Which data sources would close the biggest gaps?**
3. **What's the theoretical score ceiling if we compile everything we have?**

---

## 2. Target Benchmarks

### 2.1 AA-Omniscience (Primary Target)

The benchmark where compiled models have the biggest structural advantage.

**Public dataset:** 600 questions on HuggingFace
(`ArtificialAnalysis/AA-Omniscience-Public`)

**Scoring:** +1 correct, -1 incorrect, 0 abstain.
Best model: Gemini 3.1 Pro at +33 (out of 6000 full set).
On 600 public set: proportionally ~+3.3

**6 domains:**
- Business
- Health
- Law
- Software Engineering
- Humanities & Social Sciences
- Science, Engineering & Mathematics

**Why it matters:** A compiled model that answers correctly on covered facts
and abstains on everything else would score dramatically higher than any
existing model. The scoring function rewards our architecture.

### 2.2 TriviaQA (Secondary)

95,000 factual questions derived from Wikipedia.

**Public dataset:** HuggingFace (`trivia_qa`)

**Why:** Almost entirely factual retrieval. Wikidata coverage should be high.
Measures the knowledge band directly.

### 2.3 MMLU (Tertiary)

16,000+ multiple-choice questions across 57 subjects.

**Public dataset:** HuggingFace (`cais/mmlu`)

**Why:** Mix of factual and reasoning. Factual subjects (geography, history,
biology) should have high coverage. Reasoning subjects won't.
Useful to measure the split.

### 2.4 ARC-Challenge (Tertiary)

Science reasoning, multiple choice.

**Public dataset:** HuggingFace (`allenai/ai2_arc`)

**Why:** Science fact questions compilable from ontologies.

---

## 3. Coverage Analysis Pipeline

### 3.1 Download Benchmark Questions

```python
from datasets import load_dataset

# AA-Omniscience (600 public questions)
omniscience = load_dataset("ArtificialAnalysis/AA-Omniscience-Public")

# TriviaQA (sample — full set is 95K)
triviaqa = load_dataset("trivia_qa", "rc", split="validation[:1000]")

# MMLU (all subjects, test split)
mmlu = load_dataset("cais/mmlu", "all", split="test[:1000]")

# ARC-Challenge
arc = load_dataset("allenai/ai2_arc", "ARC-Challenge", split="test[:1000]")
```

### 3.2 Entity Extraction from Questions

For each question, extract the entities and likely relation being asked about.

**Approach A: Pattern matching (fast, covers ~60% of factual questions)**

```python
import re

PATTERNS = [
    # "What is the capital of France?"
    (r"[Ww]hat is the (\w+) of (.+?)\?", lambda m: (m.group(2), m.group(1), None)),
    # "Who directed Jaws?"
    (r"[Ww]ho (\w+) (.+?)\?", lambda m: (m.group(2), m.group(1), None)),
    # "In which country is Paris?"
    (r"[Ii]n which (\w+) is (.+?)\?", lambda m: (m.group(2), m.group(1), None)),
    # "What year was X built/founded/born?"
    (r"[Ww]hat year was (.+?) (\w+)\?", lambda m: (m.group(1), m.group(2), None)),
    # "Who is the CEO of X?"
    (r"[Ww]ho is the (\w+) of (.+?)\?", lambda m: (m.group(2), m.group(1), None)),
]

def extract_question_entities(question: str) -> dict:
    """Extract subject, relation guess, and expected answer type."""
    for pattern, extractor in PATTERNS:
        match = re.search(pattern, question)
        if match:
            subject, relation, _ = extractor(match)
            return {"subject": subject, "relation": relation, "method": "pattern"}
    return {"subject": None, "relation": None, "method": "none"}
```

**Approach B: LLM extraction (slower, covers ~95% of questions)**

Use Claude/GPT to classify each question:

```python
CLASSIFICATION_PROMPT = """
Given this question, extract:
1. The subject entity (what/who is being asked about)
2. The relation type (what property is being queried)
3. The expected answer entity

Question: "{question}"

Respond in JSON: {{"subject": "...", "relation": "...", "expected_answer": "..."}}
If this is a reasoning question (not factual retrieval), set relation to "reasoning".
"""
```

**Approach C: Hybrid (recommended)**

Run pattern matching first. For unmatched questions, use LLM classification
on the remainder. Cheap because pattern matching handles the easy ones.

### 3.3 Graph Lookup

Check if the extracted (subject, relation) pair exists in our data:

```python
import json
from pathlib import Path


class GraphCoverage:
    """Check question coverage against extracted triples."""

    def __init__(self, data_dir: str):
        self.index = {}  # subject → [(relation, object)]
        self._load_all(data_dir)

    def _load_all(self, data_dir: str):
        """Load all triple files into a lookup index."""
        for json_file in Path(data_dir).rglob("*.json"):
            if json_file.name == "manifest.json":
                continue
            try:
                data = json.load(open(json_file))
                if "pairs" not in data:
                    continue
                relation = data["relation"]
                for subject, obj in data["pairs"]:
                    key = subject.lower().strip()
                    if key not in self.index:
                        self.index[key] = []
                    self.index[key].append((relation, obj))
            except Exception:
                continue

    def lookup(self, subject: str, relation: str = None) -> list:
        """Find all triples for a subject, optionally filtered by relation."""
        key = subject.lower().strip()
        matches = self.index.get(key, [])
        if relation:
            matches = [(r, o) for r, o in matches if relation.lower() in r.lower()]
        return matches

    def has_answer(self, subject: str, expected_answer: str = None) -> bool:
        """Check if we have ANY triple for this subject."""
        key = subject.lower().strip()
        if key not in self.index:
            return False
        if expected_answer:
            return any(
                expected_answer.lower() in obj.lower()
                for _, obj in self.index[key]
            )
        return True

    def coverage_report(self, questions: list[dict]) -> dict:
        """Run coverage analysis on a list of classified questions."""
        results = {
            "total": len(questions),
            "covered": 0,
            "not_covered": 0,
            "reasoning": 0,  # not factual, can't be compiled
            "no_entity": 0,  # couldn't extract entity from question
            "covered_questions": [],
            "gap_questions": [],
            "reasoning_questions": [],
        }

        for q in questions:
            if q.get("relation") == "reasoning":
                results["reasoning"] += 1
                results["reasoning_questions"].append(q)
                continue

            if not q.get("subject"):
                results["no_entity"] += 1
                continue

            matches = self.lookup(q["subject"], q.get("relation"))
            if matches:
                results["covered"] += 1
                results["covered_questions"].append({
                    **q, "matches": matches[:5]
                })
            else:
                results["not_covered"] += 1
                results["gap_questions"].append(q)

        return results
```

### 3.4 Score Projection

Given coverage results, project benchmark scores:

```python
def project_aa_omniscience_score(coverage: dict) -> dict:
    """Project AA-Omniscience score from coverage analysis."""

    total = coverage["total"]
    covered = coverage["covered"]
    not_covered = coverage["not_covered"]
    reasoning = coverage["reasoning"]
    no_entity = coverage["no_entity"]

    # Assumptions:
    # - Covered questions: 95% correct (some reformulation failures)
    # - Not covered: abstain (score 0)
    # - Reasoning: abstain (score 0)
    correct = int(covered * 0.95)
    incorrect = covered - correct
    abstain = not_covered + reasoning + no_entity

    score = correct * 1 + incorrect * (-1) + abstain * 0
    max_possible = total

    return {
        "projected_score": score,
        "max_possible": max_possible,
        "projected_index": round(score / max_possible * 100, 1),
        "breakdown": {
            "covered": covered,
            "correct_estimate": correct,
            "incorrect_estimate": incorrect,
            "abstain": abstain,
            "reasoning_questions": reasoning,
        },
        "comparison": {
            "gemini_3_1_pro": 33,   # on full 6000 set
            "claude_4_1_opus": 4.8,
            "gpt_5_1": 3,
            "compiled_model_projected": round(score / max_possible * 100, 1),
        },
    }
```

---

## 4. Gap Analysis

After coverage analysis, classify the gaps:

### 4.1 Gaps by Data Source

For each uncovered question, identify which data source would fill it:

```python
GAP_SOURCES = {
    "wikidata_more_properties": "Expand SPARQL to more Wikidata properties",
    "wikidata_full_dump": "Need full dump for long-tail entities",
    "geonames": "Geographic detail (populations, timezones, etc.)",
    "imdb": "Film/TV/entertainment knowledge",
    "pubmed": "Medical/health knowledge",
    "stackoverflow": "Software engineering knowledge",
    "legal_corpus": "Law domain knowledge",
    "business_data": "Business/financial knowledge",
    "no_structured_source": "Requires free-text extraction or reasoning",
}

def classify_gap(question: dict) -> str:
    """Classify what data source would answer this question."""
    q = question.get("question", "").lower()
    domain = question.get("domain", "").lower()

    if domain == "health":
        return "pubmed"
    if domain == "law":
        return "legal_corpus"
    if domain == "software engineering":
        return "stackoverflow"
    if domain == "business":
        return "business_data"
    if any(w in q for w in ["film", "movie", "actor", "direct"]):
        return "imdb"
    if any(w in q for w in ["city", "population", "country", "located"]):
        return "geonames"
    # Default: try more Wikidata first
    return "wikidata_more_properties"
```

### 4.2 Gaps by Type

| Gap type | What it means | Fix |
|----------|---------------|-----|
| **Entity not in graph** | We have the relation type but not this entity | Add more entities (SPARQL limit increase or full dump) |
| **Relation not in graph** | We don't extract this property type | Add more Wikidata properties |
| **Domain not covered** | We have no data source for this domain | Add new data source (PubMed, legal, business) |
| **Reasoning required** | Question needs multi-step inference, not retrieval | Can't compile — honest abstention |
| **Temporal** | Answer changes over time ("current CEO") | Need freshness mechanism |

---

## 5. Output

### 5.1 Coverage Report (per benchmark)

```json
{
  "benchmark": "aa_omniscience_public",
  "questions": 600,
  "analysis": {
    "covered": 312,
    "not_covered": 188,
    "reasoning": 85,
    "no_entity_extracted": 15,
    "coverage_rate": "52.0%"
  },
  "projected_score": {
    "correct": 296,
    "incorrect": 16,
    "abstain": 288,
    "omniscience_index": "+46.7",
    "vs_gemini_3_1_pro": "+33 (their best)"
  },
  "gaps_by_source": {
    "wikidata_more_properties": 82,
    "pubmed": 41,
    "stackoverflow": 28,
    "legal_corpus": 19,
    "imdb": 8,
    "geonames": 5,
    "business_data": 3,
    "no_structured_source": 2
  },
  "gaps_by_domain": {
    "health": 52,
    "law": 38,
    "software_engineering": 31,
    "business": 27,
    "science": 22,
    "humanities": 18
  },
  "recommendation": "Adding 50 more Wikidata properties and PubMed MeSH would increase coverage to ~72%"
}
```

### 5.2 Gap File (for targeted data collection)

```json
{
  "benchmark": "aa_omniscience_public",
  "uncovered_questions": [
    {
      "question": "What enzyme catalyzes the conversion of...",
      "domain": "health",
      "subject": "enzyme X",
      "relation": "catalyzes",
      "suggested_source": "pubmed",
      "priority": "high"
    }
  ]
}
```

### 5.3 Summary Dashboard

```
═══════════════════════════════════════════════════════
  LARQL Benchmark Coverage Analysis
═══════════════════════════════════════════════════════

  Current data: 1,155,886 pairs across 3 downloaders

  AA-Omniscience (600 public questions):
    Covered:           312 / 600 (52.0%)
    Reasoning only:     85 / 600 (14.2%)
    Projected score:   +46.7  (vs Gemini 3.1 Pro: +33)

  TriviaQA (1000 sample):
    Covered:           680 / 1000 (68.0%)
    Projected accuracy: 64.6%  (vs Llama 70B: ~82%)

  MMLU (1000 sample):
    Factual covered:   420 / 1000 (42.0%)
    Reasoning only:    380 / 1000 (38.0%)
    Projected accuracy: 39.9%  (vs Gemma 1B: ~65%)

  Top gaps to fill:
    1. +50 Wikidata properties     → +82 questions covered
    2. PubMed MeSH                 → +41 questions covered
    3. Stack Overflow              → +28 questions covered
    4. Legal corpus                → +19 questions covered

  Next action: expand Wikidata SPARQL to 100 properties
═══════════════════════════════════════════════════════
```

---

## 6. Implementation

```bash
# Step 1: Download benchmark questions
python benchmarks/download_benchmarks.py

# Step 2: Extract entities from questions (pattern + LLM hybrid)
python benchmarks/extract_entities.py --benchmark aa_omniscience

# Step 3: Run coverage analysis against current data
python benchmarks/coverage_analysis.py \
    --benchmark aa_omniscience \
    --data-dir data/ \
    --output benchmarks/results/

# Step 4: Generate gap report
python benchmarks/gap_analysis.py \
    --coverage benchmarks/results/aa_omniscience_coverage.json \
    --output benchmarks/results/aa_omniscience_gaps.json

# All in one:
python benchmarks/run_all.py --data-dir data/ --output benchmarks/results/
```

---

## 7. Project Structure Addition

```
larql-knowledge/
├── data/                            # existing data tree
├── src/                             # existing extractors
├── benchmarks/
│   ├── download_benchmarks.py       # fetch from HuggingFace
│   ├── extract_entities.py          # question → (subject, relation)
│   ├── coverage_analysis.py         # graph lookup
│   ├── gap_analysis.py              # classify gaps by source
│   ├── score_projection.py          # project benchmark scores
│   ├── run_all.py                   # orchestrate everything
│   ├── patterns.py                  # regex patterns for entity extraction
│   └── results/                     # output directory
│       ├── aa_omniscience_coverage.json
│       ├── aa_omniscience_gaps.json
│       ├── triviaqa_coverage.json
│       ├── mmlu_coverage.json
│       └── summary.json
└── ...
```

---

## 8. Decision Tree

The coverage analysis drives the next data engineering decision:

```
Coverage < 30%
  → Current data is too thin. Run full Wikidata dump.
    The SPARQL top-44 properties are missing too many entity types.

Coverage 30-60%
  → Expand SPARQL first (cheaper). Add 50-100 more properties.
    Then reassess. The dump may not be needed.

Coverage 60-80%
  → Targeted gap filling. The gap report tells you exactly which
    sources to add (PubMed, legal, SO, IMDB). No dump needed.

Coverage > 80%
  → Data is sufficient. The bottleneck is now the attention planner
    (reformulation quality). Focus on training, not data.
```

The analysis takes ~10 minutes to run. The answer saves days of
unnecessary downloading.
