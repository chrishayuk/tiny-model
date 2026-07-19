#!/usr/bin/env python3
"""Unit test for the G1 selection algorithm (g1_selection.py) against
SYNTHETIC fixtures -- hand-designed numbers chosen to exercise every branch
of the funnel (dominance, tie-break, both threshold axes, both hard-reject
paths, incumbent/branch-B exemption, shadow-lane passthrough). None of this
is real TOK-1 candidate data; no real tokenizer has been trained. This only
proves the algorithm itself is correct, ready for real candidates later.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from g1_selection import select_survivors

# Lower is better: compression, t_core_fertility, t_scale_fertility.
# Higher is better: t_cell_coverage.
FIXTURES = [
    # --- unigram_sp family: three candidates, one dominated, two on the
    # frontier requiring a tie-break ---
    {"id": "unigram_a", "algorithm": "unigram_sp", "compression": 0.30, "t_core_fertility": 1.20,
     "t_cell_coverage": 0.90, "t_scale_fertility": 1.10, "category_5_fraction": 0.05,
     "msi_canonical": 0.95, "round_trip_pass": True, "unk_count": 0},
    {"id": "unigram_b", "algorithm": "unigram_sp", "compression": 0.32, "t_core_fertility": 1.25,
     "t_cell_coverage": 0.85, "t_scale_fertility": 1.15, "category_5_fraction": 0.06,
     "msi_canonical": 0.93, "round_trip_pass": True, "unk_count": 0},  # dominated by unigram_a
    {"id": "unigram_c", "algorithm": "unigram_sp", "compression": 0.28, "t_core_fertility": 1.30,
     "t_cell_coverage": 0.80, "t_scale_fertility": 1.05, "category_5_fraction": 0.04,
     "msi_canonical": 0.94, "round_trip_pass": True, "unk_count": 0},  # non-dominated tradeoff vs a

    # --- bpe_sp family: single frontier candidate ---
    {"id": "bpe_a", "algorithm": "bpe_sp", "compression": 0.33, "t_core_fertility": 1.10,
     "t_cell_coverage": 0.70, "t_scale_fertility": 1.25, "category_5_fraction": 0.07,
     "msi_canonical": 0.91, "round_trip_pass": True, "unk_count": 0},

    # --- byte_level_bpe family: single frontier candidate (best compression,
    # worst everything else -- a genuine Pareto tradeoff point) ---
    {"id": "blbpe_a", "algorithm": "byte_level_bpe", "compression": 0.25, "t_core_fertility": 1.60,
     "t_cell_coverage": 0.55, "t_scale_fertility": 1.50, "category_5_fraction": 0.12,
     "msi_canonical": 0.80, "round_trip_pass": True, "unk_count": 0},

    # --- hard rejects: intrinsically excellent stats, must still be excluded ---
    {"id": "unigram_hardreject", "algorithm": "unigram_sp", "compression": 0.20, "t_core_fertility": 1.00,
     "t_cell_coverage": 0.99, "t_scale_fertility": 0.90, "category_5_fraction": 0.01,
     "msi_canonical": 0.99, "round_trip_pass": True, "unk_count": 5},  # UNK > 0
    {"id": "shadow_bad_roundtrip", "algorithm": "bpe_sp", "compression": 0.10, "t_core_fertility": 0.90,
     "t_cell_coverage": 0.99, "t_scale_fertility": 0.80, "category_5_fraction": 0.01,
     "msi_canonical": 0.99, "round_trip_pass": False, "unk_count": 0, "tag": "shadow"},  # shadow doesn't bypass hard rejects

    # --- threshold rejects: one per axis ---
    {"id": "bpe_threshold_fertility", "algorithm": "bpe_sp", "compression": 0.10, "t_core_fertility": 2.50,
     "t_cell_coverage": 0.99, "t_scale_fertility": 0.10, "category_5_fraction": 0.01,
     "msi_canonical": 0.99, "round_trip_pass": True, "unk_count": 0},  # fertility > F_max
    {"id": "unigram_threshold_cat5", "algorithm": "unigram_sp", "compression": 0.10, "t_core_fertility": 1.00,
     "t_cell_coverage": 0.99, "t_scale_fertility": 0.10, "category_5_fraction": 0.90,
     "msi_canonical": 0.99, "round_trip_pass": True, "unk_count": 0},  # category_5 > R_max
    {"id": "bpe_threshold_msi", "algorithm": "bpe_sp", "compression": 0.10, "t_core_fertility": 1.00,
     "t_cell_coverage": 0.99, "t_scale_fertility": 0.10, "category_5_fraction": 0.01,
     "msi_canonical": 0.20, "round_trip_pass": True, "unk_count": 0},  # msi < MSI_canonical_min

    # --- shadow-lane: below the MSI floor, must pass through tagged, not rejected ---
    {"id": "shadow_low_msi", "algorithm": "unigram_sp", "compression": 0.50, "t_core_fertility": 1.50,
     "t_cell_coverage": 0.50, "t_scale_fertility": 1.50, "category_5_fraction": 0.30,
     "msi_canonical": 0.10, "round_trip_pass": True, "unk_count": 0, "tag": "shadow"},

    # --- incumbent / Branch B: deliberately terrible stats, must be exempt regardless ---
    {"id": "v11_incumbent", "algorithm": "incumbent_sp", "compression": 0.90, "t_core_fertility": 3.00,
     "t_cell_coverage": 0.30, "t_scale_fertility": 3.00, "category_5_fraction": 0.80,
     "msi_canonical": 0.10, "round_trip_pass": False, "unk_count": 999, "tag": "incumbent"},
    {"id": "pure_byte_branch_b", "algorithm": "pure_byte", "compression": 0.90, "t_core_fertility": 3.00,
     "t_cell_coverage": 0.30, "t_scale_fertility": 3.00, "category_5_fraction": 0.80,
     "msi_canonical": 0.10, "round_trip_pass": False, "unk_count": 999, "tag": "branch_b"},
]

F_MAX, R_MAX, MSI_CANONICAL_MIN = 2.0, 0.5, 0.5


def main():
    result = select_survivors(FIXTURES, F_MAX, R_MAX, MSI_CANONICAL_MIN)
    checks = []

    def check(name, actual, expected):
        ok = actual == expected
        checks.append((name, ok, actual, expected))

    check("survivors (set)", set(result["survivors"]), {"unigram_a", "bpe_a", "blbpe_a"})
    check("pareto_frontier (set)", set(result["pareto_frontier"]), {"unigram_a", "unigram_c", "bpe_a", "blbpe_a"})
    check("unigram_b excluded from frontier (dominated)", "unigram_b" in result["pareto_frontier"], False)
    check("exempt (set)", set(result["exempt"]), {"v11_incumbent", "pure_byte_branch_b"})
    check("shadow (set)", set(result["shadow"]), {"shadow_low_msi"})
    check("hard_rejects (set)", set(result["hard_rejects"]), {"unigram_hardreject", "shadow_bad_roundtrip"})
    check("threshold_rejects (set)", set(result["threshold_rejects"]),
          {"bpe_threshold_fertility", "unigram_threshold_cat5", "bpe_threshold_msi"})
    check("<=1 survivor per family", len(result["survivors"]), len({s["algorithm"] for s in result["survivor_details"]}))

    unigram_trace = next(t for t in result["selection_trace"] if t["family"] == "unigram_sp")
    check("unigram tie-break winner", unigram_trace["winner"], "unigram_a")
    check("unigram tie-break applied flag", unigram_trace["tie_break_applied"], True)
    check("unigram frontier members before tie-break", set(unigram_trace["frontier_members"]), {"unigram_a", "unigram_c"})

    failures = [(n, a, e) for n, ok, a, e in checks if not ok]
    print(json.dumps({
        "checked": len(checks),
        "failures": [{"check": n, "actual": a, "expected": list(e) if isinstance(e, set) else e} for n, a, e in failures],
        "pass": not failures,
        "full_result": result,
    }, indent=2, default=list))
    if failures:
        sys.exit(1)


if __name__ == "__main__":
    main()
