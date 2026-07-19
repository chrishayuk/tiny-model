"""TOK-1 -> Gate G1 candidate selection algorithm (doc section 5, "the funnel").

Verbatim per the design doc's own requirement ("the G1 survivor-selection
algorithm verbatim" is a TOK-0 pinned deliverable): hard rejects, then
threshold rejects, then a Pareto frontier over exactly four axes, then a
tie-break to at most one survivor per algorithm family. Incumbent and
Branch B are exempt from elimination; shadow-lane configs bypass only the
MSI-canonical floor, not the other checks.

Pure, deterministic, and free of any dependency on real TOK-1 candidates —
it operates on plain dicts, so it can (and is, in test_g1_selection.py)
be exercised with synthetic fixtures before a single real tokenizer exists.
"""

MINIMIZE_AXES = ("compression", "t_core_fertility", "t_scale_fertility")
MAXIMIZE_AXES = ("t_cell_coverage",)
ALL_AXES = MINIMIZE_AXES + MAXIMIZE_AXES


def dominates(a, b):
    """True if candidate `a` Pareto-dominates candidate `b`: at least as good
    as `b` on every one of the four frontier axes, strictly better on >=1."""
    at_least_as_good = True
    strictly_better = False
    for k in MINIMIZE_AXES:
        if a[k] > b[k]:
            at_least_as_good = False
        elif a[k] < b[k]:
            strictly_better = True
    for k in MAXIMIZE_AXES:
        if a[k] < b[k]:
            at_least_as_good = False
        elif a[k] > b[k]:
            strictly_better = True
    return at_least_as_good and strictly_better


def pareto_frontier(candidates):
    """Non-dominated subset of `candidates` over the four frontier axes."""
    return [c for c in candidates if not any(dominates(o, c) for o in candidates if o is not c)]


def select_survivors(candidates, F_max, R_max, MSI_canonical_min):
    """Run the full G1 funnel per doc section 5 step list 1-5.

    Each candidate dict must carry: id, algorithm, round_trip_pass,
    unk_count, merge_opacity_ok, parity_ok, t_core_fertility,
    category_5_fraction, msi_canonical, compression, t_cell_coverage,
    t_scale_fertility, and optionally tag in {"incumbent","branch_b","shadow"}.
    """
    exempt, hard_rejects, threshold_rejects, shadow_passthrough, pool = [], [], [], [], []

    for c in candidates:
        tag = c.get("tag")
        if tag in ("incumbent", "branch_b"):
            exempt.append(c)
            continue

        # step 1: hard rejects (§2.3) -- apply to shadow configs too, they
        # only bypass the MSI floor, not basic correctness.
        if (
            not c.get("round_trip_pass", False)
            or c.get("unk_count", 0) > 0
            or not c.get("merge_opacity_ok", True)
            or not c.get("parity_ok", True)
        ):
            hard_rejects.append(c)
            continue

        if tag == "shadow":
            shadow_passthrough.append(c)
            continue

        # step 2: threshold rejects
        if (
            c["t_core_fertility"] > F_max
            or c["category_5_fraction"] > R_max
            or c["msi_canonical"] < MSI_canonical_min
        ):
            threshold_rejects.append(c)
            continue

        pool.append(c)

    # step 3: Pareto frontier over exactly the four axes
    frontier = pareto_frontier(pool)

    # step 4: <=1 survivor per algorithm family, tie-break
    # T-core fertility -> compression -> category-5 fraction
    by_family = {}
    for c in frontier:
        by_family.setdefault(c["algorithm"], []).append(c)

    survivors, selection_trace = [], []
    for family, members in sorted(by_family.items()):
        ranked = sorted(members, key=lambda c: (c["t_core_fertility"], c["compression"], c["category_5_fraction"]))
        survivors.append(ranked[0])
        selection_trace.append({
            "family": family,
            "frontier_members": [m["id"] for m in members],
            "tie_break_applied": len(members) > 1,
            "winner": ranked[0]["id"],
        })

    return {
        "survivors": [c["id"] for c in survivors],
        "survivor_details": survivors,
        "exempt": [c["id"] for c in exempt],  # incumbent, branch_b -- step 5
        "shadow": [c["id"] for c in shadow_passthrough],  # tagged SHADOW -- step 5
        "hard_rejects": [c["id"] for c in hard_rejects],
        "threshold_rejects": [c["id"] for c in threshold_rejects],
        "pareto_frontier": [c["id"] for c in frontier],
        "selection_trace": selection_trace,
    }
