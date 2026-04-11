"""Benchmark Coverage Analysis — v0.1.

Measures how many benchmark questions the current compiled-data tree
(data/linguistic, data/ast, data/knowledge) can already answer via direct
subject/relation lookup. Produces per-benchmark coverage JSON, gap
classification, projected scores, and a console dashboard.

Pattern-based entity extraction only (no LLM). Coverage is a lower bound:
anything the regexes don't catch becomes "no_entity" and is treated as a
gap, so the real ceiling is higher.

Usage:
    uv run python benchmark_coverage.py --data-dir data --output benchmarks/results
    uv run python benchmark_coverage.py --only aa_omniscience
    uv run python benchmark_coverage.py --sample 500
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import tempfile
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

try:
    from tqdm import tqdm
except ImportError:
    print("ERROR: tqdm required. uv add tqdm", file=sys.stderr)
    sys.exit(1)


# ---------------------------------------------------------------------------
# Graph index
# ---------------------------------------------------------------------------


class GraphIndex:
    """Subject-keyed index over every pair in every JSON file under data/."""

    def __init__(self):
        self.by_subject: dict[str, list[tuple[str, str]]] = defaultdict(list)
        self.by_object: dict[str, list[tuple[str, str]]] = defaultdict(list)
        self.total_pairs = 0
        self.files_loaded = 0
        self.relations: Counter = Counter()

    def load(self, data_dir: Path) -> None:
        json_files = [
            p
            for p in data_dir.rglob("*.json")
            if p.name not in ("manifest.json",)
            and ".state" not in p.name
            and "_cache" not in p.parts
        ]
        for p in tqdm(json_files, desc="indexing", unit="file"):
            try:
                doc = json.loads(p.read_text())
            except Exception:
                continue
            if not isinstance(doc, dict):
                continue
            pairs = doc.get("pairs")
            if not isinstance(pairs, list):
                continue
            relation = doc.get("relation") or p.stem
            self.relations[relation] += len(pairs)
            for pair in pairs:
                if not isinstance(pair, list) or len(pair) != 2:
                    continue
                a, b = pair
                if not isinstance(a, str) or not isinstance(b, str):
                    continue
                ka = a.strip().lower()
                kb = b.strip().lower()
                if not ka or not kb:
                    continue
                self.by_subject[ka].append((relation, b))
                self.by_object[kb].append((relation, a))
                self.total_pairs += 1
            self.files_loaded += 1

    def lookup(self, subject: str, relation: str | None = None):
        key = subject.strip().lower()
        matches = self.by_subject.get(key, [])
        if relation:
            rlow = relation.lower()
            matches = [m for m in matches if rlow in m[0].lower()]
        return matches

    def contains_token(self, text: str) -> bool:
        """True if the lowercased text is a subject or object we know."""
        key = text.strip().lower()
        return key in self.by_subject or key in self.by_object


# ---------------------------------------------------------------------------
# Entity extraction (regex only)
# ---------------------------------------------------------------------------


STOP_TRAIL = re.compile(r"[\?\.\,\:\;]+$")

# Capitalized multi-word noun phrases. Allows internal lowercase joiners
# ("United States of America", "Bank of England"). Rejects single-letter
# all-caps noise and common sentence-initial words.
PROPER_NOUN_RE = re.compile(
    r"\b([A-Z][a-zA-Z][a-zA-Z'-]*"
    r"(?:\s+(?:of|the|and|de|da|van|von|du|le|la|des|el|&)\s+[A-Z][a-zA-Z][a-zA-Z'-]*)*"
    r"(?:\s+[A-Z][a-zA-Z][a-zA-Z'-]*)*)\b"
)

# Words to drop if they appear as the only token in a candidate — they are
# usually the capitalized first word of the question, not a real entity.
STOPWORDS = {
    "what", "which", "who", "when", "where", "why", "how", "is", "the", "a", "an",
    "this", "that", "these", "those", "in", "on", "at", "of", "for", "with",
    "from", "to", "by", "and", "or", "but", "if", "as", "do", "does", "did",
    "have", "has", "had", "can", "could", "would", "should", "will", "was", "were",
    "are", "am", "be", "been", "being", "all", "each", "one", "two", "three",
    "i", "you", "he", "she", "it", "we", "they",
}


def _clean(s: str) -> str:
    return STOP_TRAIL.sub("", s.strip())


def extract_proper_nouns(question: str) -> list[str]:
    """Return candidate entity spans in rough order of usefulness.

    Drops the sentence-initial capitalized word if it's a stopword
    ('What', 'Which'...) so we don't waste lookups on question words.
    """
    # Strip the first token if it's a capitalized question word.
    q = question.lstrip()
    first_match = re.match(r"^([A-Z][a-z]*)\b", q)
    if first_match and first_match.group(1).lower() in STOPWORDS:
        q = q[first_match.end():]

    out: list[str] = []
    seen: set[str] = set()
    for m in PROPER_NOUN_RE.finditer(q):
        cand = _clean(m.group(1)).strip()
        if not cand:
            continue
        low = cand.lower()
        if low in STOPWORDS:
            continue
        # Drop single-token all-lowercase garbage (shouldn't happen, but safe).
        if len(cand) < 2:
            continue
        if low in seen:
            continue
        seen.add(low)
        out.append(cand)
    return out


def normalize_answer(answer: Any) -> list[str]:
    """Normalize a benchmark 'answer' field into one-or-more lowercase strings."""
    if answer is None:
        return []
    if isinstance(answer, (list, tuple)):
        out = []
        for a in answer:
            out.extend(normalize_answer(a))
        return out
    if isinstance(answer, dict):
        parts: list[str] = []
        for k in ("value", "normalized_value", "text", "aliases"):
            if k in answer:
                parts.extend(normalize_answer(answer[k]))
        return parts
    s = str(answer).strip().lower()
    return [s] if s else []


# Each pattern yields (subject, relation_hint). The relation hint is matched
# against relation names via substring; a blank hint means any relation.
PATTERNS: list[tuple[re.Pattern, Callable[[re.Match], tuple[str, str]]]] = [
    # What is the capital of France?
    (re.compile(r"^[Ww]hat\s+is\s+the\s+([a-z][a-z_ ]{2,30})\s+of\s+(.+?)\??$"),
     lambda m: (_clean(m.group(2)), m.group(1).strip())),
    # Who is the president/CEO/director of X?
    (re.compile(r"^[Ww]ho\s+is\s+the\s+([a-z][a-z_ ]{2,30})\s+of\s+(.+?)\??$"),
     lambda m: (_clean(m.group(2)), m.group(1).strip())),
    # Who directed / wrote / founded / invented X?
    (re.compile(r"^[Ww]ho\s+(directed|wrote|founded|invented|composed|painted|created|authored|produced|discovered)\s+(.+?)\??$"),
     lambda m: (_clean(m.group(2)), m.group(1))),
    # In which country is Paris?
    (re.compile(r"^[Ii]n\s+which\s+([a-z]+)\s+is\s+(.+?)\??$"),
     lambda m: (_clean(m.group(2)), m.group(1))),
    # Where is X located?
    (re.compile(r"^[Ww]here\s+is\s+(.+?)\s+located\??$"),
     lambda m: (_clean(m.group(1)), "located")),
    # Where was X born?
    (re.compile(r"^[Ww]here\s+was\s+(.+?)\s+born\??$"),
     lambda m: (_clean(m.group(1)), "birthplace")),
    # When was X born/founded/built?
    (re.compile(r"^[Ww]hen\s+was\s+(.+?)\s+(born|founded|built|established|created)\??$"),
     lambda m: (_clean(m.group(1)), m.group(2))),
    # What language is spoken in X?
    (re.compile(r"^[Ww]hat\s+language\s+is\s+spoken\s+in\s+(.+?)\??$"),
     lambda m: (_clean(m.group(1)), "language")),
    # What currency does X use?
    (re.compile(r"^[Ww]hat\s+currency\s+(?:does|do)\s+(.+?)\s+use\??$"),
     lambda m: (_clean(m.group(1)), "currency")),
    # Who plays for X?  /  Who plays X?
    (re.compile(r"^[Ww]ho\s+plays\s+for\s+(.+?)\??$"),
     lambda m: (_clean(m.group(1)), "team")),
    # Which team does X play for?
    (re.compile(r"^[Ww]hich\s+team\s+does\s+(.+?)\s+play\s+for\??$"),
     lambda m: (_clean(m.group(1)), "team")),
    # What is X?  → instance_of
    (re.compile(r"^[Ww]hat\s+is\s+(?:an?\s+)?(.+?)\??$"),
     lambda m: (_clean(m.group(1)), "instance")),
    # Generic "who/what ... X ?" — last-ditch, take the trailing noun phrase
]


def extract_entity(question: str) -> dict:
    q = question.strip()
    for pat, extract in PATTERNS:
        m = pat.match(q)
        if m:
            subject, relation = extract(m)
            if subject and len(subject) < 80:
                return {"subject": subject, "relation": relation, "method": "pattern"}
    return {"subject": None, "relation": None, "method": "none"}


# ---------------------------------------------------------------------------
# Benchmark loading
# ---------------------------------------------------------------------------


def load_benchmark(name: str, sample: int | None) -> list[dict]:
    """Return a list of {question, answer?, domain?} dicts."""
    from datasets import load_dataset

    if name == "aa_omniscience":
        ds = load_dataset("ArtificialAnalysis/AA-Omniscience-Public", split="train")
        out = []
        for row in ds:
            question = row.get("question") or row.get("prompt") or ""
            domain = row.get("domain") or row.get("category") or ""
            answer = row.get("answer") or row.get("correct_answer") or ""
            out.append({"question": question, "domain": domain, "answer": answer})
        return out[:sample] if sample else out

    if name == "triviaqa":
        split = f"validation[:{sample}]" if sample else "validation[:1000]"
        ds = load_dataset("trivia_qa", "rc.nocontext", split=split)
        out = []
        for row in ds:
            ans = row.get("answer") or {}
            answer_forms = []
            if isinstance(ans, dict):
                for k in ("value", "normalized_value", "aliases", "normalized_aliases"):
                    v = ans.get(k)
                    if v:
                        if isinstance(v, list):
                            answer_forms.extend(v)
                        else:
                            answer_forms.append(v)
            out.append({"question": row["question"], "answer": answer_forms, "domain": "trivia"})
        return out

    if name == "mmlu":
        split = f"test[:{sample}]" if sample else "test[:1000]"
        ds = load_dataset("cais/mmlu", "all", split=split)
        out = []
        for row in ds:
            q = row["question"]
            choices = row.get("choices") or []
            ans_idx = row.get("answer")
            answer = choices[ans_idx] if isinstance(ans_idx, int) and ans_idx < len(choices) else ""
            out.append({"question": q, "answer": answer, "domain": row.get("subject", "")})
        return out

    if name == "arc":
        split = f"test[:{sample}]" if sample else "test[:1000]"
        ds = load_dataset("allenai/ai2_arc", "ARC-Challenge", split=split)
        out = []
        for row in ds:
            q = row["question"]
            choices = row.get("choices", {}).get("text", [])
            labels = row.get("choices", {}).get("label", [])
            ak = row.get("answerKey", "")
            answer = ""
            if ak in labels:
                answer = choices[labels.index(ak)]
            out.append({"question": q, "answer": answer, "domain": "science"})
        return out

    raise ValueError(f"Unknown benchmark: {name}")


BENCHMARKS = ["aa_omniscience", "triviaqa", "mmlu", "arc"]


# ---------------------------------------------------------------------------
# Coverage & scoring
# ---------------------------------------------------------------------------


REASONING_HINTS = re.compile(
    r"\b(why|explain|derive|prove|calculate|compute|how many|how much|which of|step-by-step)\b",
    re.IGNORECASE,
)


def classify_gap(question: dict) -> str:
    q = question.get("question", "").lower()
    domain = (question.get("domain") or "").lower()

    if "health" in domain or "medic" in domain or "biology" in domain:
        return "pubmed_or_taxonomy"
    if "law" in domain:
        return "legal_corpus"
    if "software" in domain or "computer" in domain or "programming" in domain:
        return "stackoverflow_or_docs"
    if "business" in domain or "econom" in domain or "finance" in domain:
        return "business_data"
    if any(w in q for w in ("film", "movie", "actor", "director", "tv show", "series")):
        return "imdb"
    if any(w in q for w in ("song", "album", "band", "musician", "singer")):
        return "musicbrainz"
    if any(w in q for w in ("city", "town", "capital", "population", "country", "river", "mountain")):
        return "geonames_or_osm"
    if any(w in q for w in ("chemical", "compound", "molecule", "element")):
        return "pubchem_chebi"
    return "wikidata_more_properties"


def _answer_matches(answer_forms: list[str], objects: list[str]) -> str | None:
    """Return the matched object if any answer form appears in any object
    (or vice versa). Case-insensitive substring match both directions."""
    if not answer_forms or not objects:
        return None
    for obj in objects:
        o = obj.strip().lower()
        if not o:
            continue
        for a in answer_forms:
            if not a:
                continue
            if a == o or (len(a) >= 3 and (a in o or o in a)):
                return obj
    return None


def analyze_questions(index: GraphIndex, questions: list[dict]) -> dict:
    total = len(questions)
    reasoning = 0
    no_entity = 0  # no capitalized spans at all
    answer_verified = 0  # strong: subject known AND answer appears among its objects
    pattern_relation = 0  # strong: regex pattern matched a known (subject, relation)
    entity_only = 0  # weak: subject known but answer can't be verified
    not_covered = 0

    covered_samples: list[dict] = []
    gap_samples: list[dict] = []
    gaps_by_source: Counter = Counter()
    gaps_by_domain: Counter = Counter()

    for q in tqdm(questions, desc="analyzing", unit="q", leave=False):
        text = q.get("question", "")
        domain = q.get("domain", "")

        if REASONING_HINTS.search(text):
            reasoning += 1
            continue

        answer_forms = normalize_answer(q.get("answer"))

        # Pass 1: regex patterns (rare but highest-confidence when they fire).
        ex = extract_entity(text)
        if ex["subject"]:
            matches = index.lookup(ex["subject"], ex["relation"])
            if matches:
                pattern_relation += 1
                if len(covered_samples) < 15:
                    covered_samples.append(
                        {**q, "subject": ex["subject"], "relation": ex["relation"],
                         "matches": matches[:3], "how": "pattern"}
                    )
                continue

        # Pass 2: proper-noun extraction. Try each candidate as subject.
        candidates = extract_proper_nouns(text)
        if not candidates:
            no_entity += 1
            continue

        verified: tuple[str, str, str] | None = None  # (subject, relation, object)
        known_subject: str | None = None

        for cand in candidates:
            hits = index.lookup(cand)
            if not hits:
                continue
            if known_subject is None:
                known_subject = cand
            matched = _answer_matches(answer_forms, [o for _r, o in hits])
            if matched:
                # Find the relation for this object.
                for r, o in hits:
                    if o == matched:
                        verified = (cand, r, o)
                        break
                if verified:
                    break

        if verified:
            answer_verified += 1
            if len(covered_samples) < 15:
                covered_samples.append(
                    {**q, "subject": verified[0], "relation": verified[1],
                     "object": verified[2], "how": "noun+answer"}
                )
            continue

        if known_subject is not None:
            entity_only += 1
            not_covered += 1  # count as gap: we have entity but no verifiable answer
            gaps_by_source[classify_gap(q)] += 1
            if domain:
                gaps_by_domain[domain] += 1
            if len(gap_samples) < 30:
                gap_samples.append(
                    {**q, "known_subject": known_subject, "reason": "entity_only"}
                )
            continue

        not_covered += 1
        gaps_by_source[classify_gap(q)] += 1
        if domain:
            gaps_by_domain[domain] += 1
        if len(gap_samples) < 30:
            gap_samples.append({**q, "candidates": candidates[:5], "reason": "no_match"})

    covered = pattern_relation + answer_verified

    return {
        "total": total,
        "covered": covered,
        "covered_by_pattern": pattern_relation,
        "covered_by_answer_verification": answer_verified,
        "entity_only_no_answer_match": entity_only,
        "not_covered": not_covered,
        "reasoning": reasoning,
        "no_entity": no_entity,
        "coverage_rate_pct": round(covered / total * 100, 1) if total else 0.0,
        "answer_verifiable_pool_pct": round(
            sum(1 for q in questions if normalize_answer(q.get("answer"))) / total * 100, 1
        ) if total else 0.0,
        "gaps_by_source": dict(gaps_by_source.most_common()),
        "gaps_by_domain": dict(gaps_by_domain.most_common()),
        "covered_samples": covered_samples,
        "gap_samples": gap_samples,
    }


def project_score(analysis: dict, benchmark: str) -> dict:
    total = analysis["total"]
    covered = analysis["covered"]
    # Assume 80% of covered questions produce the correct answer after
    # reformulation (conservative). The rest of covered questions are errors.
    correct = int(round(covered * 0.8))
    incorrect = covered - correct
    abstain = total - covered

    if benchmark == "aa_omniscience":
        # +1 / -1 / 0
        score = correct - incorrect
        return {
            "scoring": "+1 / -1 / 0",
            "correct_est": correct,
            "incorrect_est": incorrect,
            "abstain": abstain,
            "score": score,
            "max_possible": total,
            "normalized_index": round((score / total) * 100, 1) if total else 0.0,
        }

    # Default accuracy (correct / total), abstains count as incorrect
    return {
        "scoring": "accuracy",
        "correct_est": correct,
        "incorrect_est": incorrect + abstain,
        "accuracy_percent": round((correct / total) * 100, 1) if total else 0.0,
    }


# ---------------------------------------------------------------------------
# I/O helpers
# ---------------------------------------------------------------------------


def atomic_write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w") as fh:
            json.dump(payload, fh, indent=2, ensure_ascii=False, default=str)
        os.replace(tmp_name, path)
    except Exception:
        if os.path.exists(tmp_name):
            os.unlink(tmp_name)
        raise


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------


def render_dashboard(index: GraphIndex, reports: dict) -> str:
    lines = []
    bar = "=" * 72
    lines.append(bar)
    lines.append("  Benchmark Coverage Analysis")
    lines.append(bar)
    lines.append("")
    lines.append(
        f"  Graph: {index.total_pairs:,} pairs, "
        f"{len(index.by_subject):,} subjects, "
        f"{len(index.relations)} relations, "
        f"{index.files_loaded} files"
    )
    lines.append("")

    for name, r in reports.items():
        a = r["analysis"]
        s = r["projection"]
        total = a["total"]
        cov_pct = round(a["covered"] / total * 100, 1) if total else 0.0
        reasoning_pct = round(a["reasoning"] / total * 100, 1) if total else 0.0
        no_entity_pct = round(a["no_entity"] / total * 100, 1) if total else 0.0

        pool_pct = a.get("answer_verifiable_pool_pct", 0.0)
        lines.append(f"  {name}:")
        lines.append(
            f"    covered:         {a['covered']:>5} / {total:<5} ({cov_pct:>5.1f}%)   "
            f"[pattern={a['covered_by_pattern']} + answer_match={a['covered_by_answer_verification']}]"
        )
        lines.append(
            f"    entity-only:     {a['entity_only_no_answer_match']:>5}    (subject in graph, answer not verifiable)"
        )
        lines.append(
            f"    reasoning:       {a['reasoning']:>5} / {total:<5} ({reasoning_pct:>5.1f}%)"
        )
        lines.append(
            f"    no-entity:       {a['no_entity']:>5} / {total:<5} ({no_entity_pct:>5.1f}%)"
        )
        lines.append(
            f"    answerable pool: {pool_pct:>5.1f}%     (questions with a known gold answer to match against)"
        )
        if s.get("scoring") == "+1 / -1 / 0":
            lines.append(
                f"    projected:   score {s['score']:+d} / {s['max_possible']}  "
                f"(index {s['normalized_index']:+.1f})"
            )
        else:
            lines.append(f"    projected:   accuracy {s['accuracy_percent']:.1f}%")

        if a["gaps_by_source"]:
            top = list(a["gaps_by_source"].items())[:5]
            lines.append("    top gap sources:")
            for src, n in top:
                lines.append(f"      - {src:<28} {n}")
        lines.append("")

    lines.append(bar)
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=Path("../datasets/extracted"))
    parser.add_argument("--output", type=Path, default=Path("results"))
    parser.add_argument(
        "--only",
        type=str,
        default=None,
        help=f"Comma-separated benchmarks. Available: {','.join(BENCHMARKS)}",
    )
    parser.add_argument(
        "--sample",
        type=int,
        default=1000,
        help="Max questions per benchmark (ignored for AA-Omniscience which is fixed)",
    )
    args = parser.parse_args()

    data_dir = args.data_dir.resolve()
    if not data_dir.exists():
        sys.exit(f"data dir not found: {data_dir}")

    print(f"[index] loading data from {data_dir}")
    index = GraphIndex()
    index.load(data_dir)
    print(f"[index] {index.total_pairs:,} pairs, {len(index.by_subject):,} unique subjects")

    selected = (
        [b.strip() for b in args.only.split(",")] if args.only else BENCHMARKS
    )

    reports: dict[str, dict] = {}
    for name in selected:
        if name not in BENCHMARKS:
            print(f"[skip] unknown benchmark: {name}")
            continue
        print(f"[bench] loading {name}")
        try:
            questions = load_benchmark(name, None if name == "aa_omniscience" else args.sample)
        except Exception as e:
            print(f"[error] failed to load {name}: {type(e).__name__}: {e}")
            continue
        print(f"[bench] {name}: {len(questions)} questions")
        analysis = analyze_questions(index, questions)
        projection = project_score(analysis, name)
        report = {
            "benchmark": name,
            "questions": len(questions),
            "generated": datetime.now(timezone.utc).isoformat(),
            "graph": {
                "total_pairs": index.total_pairs,
                "unique_subjects": len(index.by_subject),
                "relations": len(index.relations),
            },
            "analysis": analysis,
            "projection": projection,
        }
        atomic_write_json(args.output / f"{name}_coverage.json", report)
        reports[name] = report

    summary = {
        "generated": datetime.now(timezone.utc).isoformat(),
        "graph": {
            "total_pairs": index.total_pairs,
            "unique_subjects": len(index.by_subject),
            "relations": dict(index.relations.most_common(20)),
        },
        "benchmarks": {
            name: {
                "questions": r["questions"],
                "covered": r["analysis"]["covered"],
                "reasoning": r["analysis"]["reasoning"],
                "no_entity": r["analysis"]["no_entity"],
                "projection": r["projection"],
            }
            for name, r in reports.items()
        },
    }
    atomic_write_json(args.output / "summary.json", summary)

    print()
    print(render_dashboard(index, reports))
    print(f"\n[done] reports in {args.output}")


if __name__ == "__main__":
    main()
