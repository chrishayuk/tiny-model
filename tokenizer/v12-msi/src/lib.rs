//! Rust side of the MSI canonicalizer (C7 / doc section 2.3 Python-Rust parity
//! requirement). Mirrors `tokenizer/v12/bench/msi/canonicalizer.py`.
//!
//! Only the class-1 (identical id-level copy) case is implemented — class-2
//! (losslessly canonicalizable via a candidate's merge table) needs a real
//! TOK-1 candidate's merge table, which doesn't exist yet.

use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct CanonicalizeResult {
    pub operand_ids: Vec<i64>,
    /// 1 identical, 2 canonicalizable, 3 context-entangled
    pub segmentation_class: u8,
    pub failure_mode: Option<String>,
}

/// Class-1 case: `framed_ids` already contains `operand_ids` verbatim as a
/// contiguous subsequence. No tokenizer-specific knowledge required — class 1
/// is defined as exact id-level equality.
pub fn canonicalize_identity(framed_ids: &[i64], operand_ids: &[i64]) -> Option<CanonicalizeResult> {
    let n = operand_ids.len();
    if n > framed_ids.len() {
        return None;
    }
    for start in 0..=(framed_ids.len() - n) {
        if &framed_ids[start..start + n] == operand_ids {
            return Some(CanonicalizeResult {
                operand_ids: operand_ids.to_vec(),
                segmentation_class: 1,
                failure_mode: None,
            });
        }
    }
    None
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::fs;
    use std::path::Path;

    #[derive(Deserialize)]
    struct Vector {
        id: String,
        framed_ids: Vec<i64>,
        operand_ids: Vec<i64>,
        expect_class1: bool,
        expect_operand_ids: Option<Vec<i64>>,
    }

    /// Golden parity vectors shared with the Python implementation's test
    /// (bench/msi/test_canonicalizer_parity.py) — both must agree on every
    /// line for the class-1 case to be considered parity-checked.
    #[test]
    fn parity_vectors_identity_case() {
        let path = Path::new(env!("CARGO_MANIFEST_DIR")).join("../v12/bench/msi/parity_vectors.jsonl");
        let content = fs::read_to_string(&path)
            .unwrap_or_else(|e| panic!("read {}: {}", path.display(), e));
        let mut checked = 0;
        for line in content.lines() {
            if line.trim().is_empty() {
                continue;
            }
            let v: Vector = serde_json::from_str(line).expect("parse parity vector");
            let result = canonicalize_identity(&v.framed_ids, &v.operand_ids);
            if v.expect_class1 {
                let r = result.unwrap_or_else(|| panic!("{}: expected class-1 match", v.id));
                assert_eq!(r.segmentation_class, 1);
                assert_eq!(
                    Some(r.operand_ids),
                    v.expect_operand_ids,
                    "{}: operand_ids mismatch",
                    v.id
                );
            } else {
                assert!(result.is_none(), "{}: expected no class-1 match", v.id);
            }
            checked += 1;
        }
        assert!(checked > 0, "no parity vectors were read from {}", path.display());
    }
}
