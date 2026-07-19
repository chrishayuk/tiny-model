#!/usr/bin/env python3
"""Python side of the class-1 canonicalizer parity check.

Loads the same golden vectors the Rust crate (tokenizer/v12-msi) tests
against and asserts canonicalize_identity agrees line-for-line. Run both
this and `cargo test -p v12-msi` — that pair together *is* the Python/Rust
parity check for the class-1 case (C7 / doc section 2.3). Class-2 parity
is not checkable yet: it needs a real TOK-1 candidate's merge table.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from canonicalizer import canonicalize_identity

VECTORS_PATH = Path(__file__).resolve().parent / "parity_vectors.jsonl"


def main():
    checked = 0
    failures = []
    for line in VECTORS_PATH.read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        v = json.loads(line)
        result = canonicalize_identity(v["framed_ids"], v["operand_ids"])
        checked += 1
        if v["expect_class1"]:
            if result is None:
                failures.append(f"{v['id']}: expected class-1 match, got None")
                continue
            if result.segmentation_class != 1:
                failures.append(f"{v['id']}: expected segmentation_class 1, got {result.segmentation_class}")
            if list(result.operand_ids) != v["expect_operand_ids"]:
                failures.append(f"{v['id']}: operand_ids mismatch: {result.operand_ids} != {v['expect_operand_ids']}")
        else:
            if result is not None:
                failures.append(f"{v['id']}: expected no class-1 match, got {result}")

    print(json.dumps({"checked": checked, "failures": failures, "pass": not failures}, indent=2))
    if failures:
        sys.exit(1)


if __name__ == "__main__":
    main()
