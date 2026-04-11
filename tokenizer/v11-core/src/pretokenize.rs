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

use crate::WORD_START;

/// Replace ASCII whitespace runs with `▁`. The first character of the
/// result is always `▁` (acts as a BOS marker for longest-match).
pub fn metaspace(input: &str) -> String {
    let mut out = String::with_capacity(input.len() + 4);
    let mut prev_space = true; // treat start-of-text as "after a space"
    for ch in input.chars() {
        if ch.is_ascii_whitespace() {
            prev_space = true;
            continue;
        }
        if prev_space {
            out.push(WORD_START);
            prev_space = false;
        }
        out.push(ch);
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
}
