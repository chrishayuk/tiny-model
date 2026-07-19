//! Pre-tokenization — transforms raw input text into a stream of
//! "pieces to be vocab-matched".
//!
//! v11 inherits the SentencePiece convention: a leading space is
//! rewritten as `▁` (U+2581) and whitespace boundaries become explicit
//! word-start markers. This lets the vocab carry both `▁def` (function
//! definition at a word boundary in Python) and `def` (substring match
//! inside e.g. `undef`) as distinct tokens.
//!
//! The output of pre-tokenization is the exact byte sequence that the
//! longest-match tokenizer will scan over.
//!
//! This matches HF `Metaspace(replacement='▁', prepend_scheme=always,
//! split=true)` exactly: only the literal ASCII space character (0x20)
//! is replaced/split on. Every other character — including tab, newline,
//! CR, and non-ASCII whitespace like U+00A0 — passes through unchanged
//! and stays embedded in whichever chunk it falls in. (Verified directly
//! against the real `tokenizers` library; a prior version of this file
//! treated any `is_ascii_whitespace()` char as a split point, which is
//! not what HF's Metaspace actually does — see
//! `tokenizer/v12/pins/tok0_pins.yaml`'s `incumbent_ledger` for the
//! round-trip and Python/Rust parity bugs that divergence caused.)

use crate::WORD_START;

/// Replace literal space characters (0x20) with `▁`, one-for-one. Every
/// other character, including other whitespace, passes through
/// unchanged. The result always starts with `▁` (prepend_scheme=always),
/// unless the input is empty.
pub fn metaspace(input: &str) -> String {
    let mut out = String::with_capacity(input.len() + 1);
    for ch in input.chars() {
        out.push(if ch == ' ' { WORD_START } else { ch });
    }
    if !out.is_empty() && !out.starts_with(WORD_START) {
        out.insert(0, WORD_START);
    }
    out
}

/// Reverse the metaspace transform for decoding.
pub fn reverse_metaspace(input: &str) -> String {
    let mut out = String::with_capacity(input.len());
    let mut at_start = true;
    for ch in input.chars() {
        if ch == WORD_START {
            if !at_start {
                out.push(' ');
            }
            at_start = false;
            continue;
        }
        out.push(ch);
        at_start = false;
    }
    out
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn forward_and_reverse() {
        let cases = [
            "hello world",
            "def fibonacci(n):",
            "  leading spaces",
            "The capital of France is Paris",
        ];
        for s in cases {
            let meta = metaspace(s);
            let back = reverse_metaspace(&meta);
            // Trim because metaspace collapses leading whitespace
            assert_eq!(
                back.trim_start(),
                s.trim_start(),
                "roundtrip failed for {s:?}: meta={meta:?} back={back:?}"
            );
        }
    }

    #[test]
    fn starts_with_marker() {
        assert!(metaspace("hello").starts_with(WORD_START));
        assert!(metaspace("a b c").starts_with(WORD_START));
    }

    #[test]
    fn only_literal_space_is_replaced() {
        // Regression test for the whitespace round-trip / Python-Rust parity
        // bug: real HF Metaspace splits/replaces ONLY the literal space
        // character (0x20). Tab, newline, CR, and non-ASCII whitespace
        // (e.g. U+00A0) must pass through metaspace() untouched, embedded
        // in place rather than collapsed into a WORD_START marker.
        assert_eq!(metaspace("hello\nworld"), format!("{WORD_START}hello\nworld"));
        assert_eq!(metaspace("hello\tworld"), format!("{WORD_START}hello\tworld"));
        assert_eq!(
            metaspace("hello\u{00A0}world"),
            format!("{WORD_START}hello\u{00A0}world")
        );
        // A literal space still becomes the marker, same as before.
        assert_eq!(
            metaspace("hello world"),
            format!("{WORD_START}hello{WORD_START}world")
        );
    }

    #[test]
    fn non_space_chars_survive_round_trip() {
        // With the fix, decode(encode-equivalent-metaspace(s)) preserves
        // newlines/tabs verbatim instead of turning them into spaces.
        let cases = ["hello\nworld", "def f():\n\treturn 1", "a\rb"];
        for s in cases {
            let meta = metaspace(s);
            let back = reverse_metaspace(&meta);
            assert_eq!(back.trim_start(), s.trim_start(), "s={s:?} meta={meta:?} back={back:?}");
        }
    }
}
