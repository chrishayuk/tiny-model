//! The v11 tokenizer runtime.
//!
//! Algorithm: a faithful port of the HuggingFace `tokenizers` crate
//! Unigram `encode_optimized` — trie-based Viterbi with shortest-first
//! prefix iteration, strict `>` score comparison (first-reacher wins on
//! ties), and an unk penalty of `min_score - 10`. This guarantees that
//! `v11-core::Tokenizer::encode` produces byte-identical ids to
//! `transformers.AutoTokenizer.from_pretrained(<artifacts dir>).encode` for
//! the same vocab.
//!
//! Pretokenization matches HF `Metaspace(prepend_scheme=always, split=true)`:
//! whitespace runs split the stream into chunks, each chunk is prefixed
//! with `▁`, and Viterbi runs per chunk.

use std::collections::HashMap;
use std::path::Path;

use crate::error::Result;
use crate::pretokenize::reverse_metaspace;
use crate::vocab::Vocab;
use crate::WORD_START;

const K_UNK_PENALTY: f32 = 10.0;

pub struct Tokenizer {
    vocab: Vocab,
    trie: Trie,
    min_score: f32,
    unk_id: u32,
}

struct Trie {
    children: Vec<HashMap<u8, u32>>,
    leaf_id: Vec<Option<u32>>,
    leaf_score: Vec<f32>,
}

impl Trie {
    fn new() -> Self {
        Self {
            children: vec![HashMap::new()],
            leaf_id: vec![None],
            leaf_score: vec![0.0],
        }
    }

    fn insert(&mut self, bytes: &[u8], id: u32, score: f32) {
        let mut node = 0usize;
        for &b in bytes {
            let next = self.children[node].get(&b).copied();
            node = match next {
                Some(n) => n as usize,
                None => {
                    let new = self.children.len();
                    self.children.push(HashMap::new());
                    self.leaf_id.push(None);
                    self.leaf_score.push(0.0);
                    self.children[node].insert(b, new as u32);
                    new
                }
            };
        }
        self.leaf_id[node] = Some(id);
        self.leaf_score[node] = score;
    }
}

#[derive(Clone, Copy)]
struct BestNode {
    starts_at: Option<u32>,
    best_score: f32,
    id: u32,
}

impl Default for BestNode {
    fn default() -> Self {
        Self {
            starts_at: None,
            best_score: 0.0,
            id: 0,
        }
    }
}

impl Tokenizer {
    pub fn from_vocab(vocab: Vocab) -> Self {
        let unk_id = vocab.special.unk_id;
        let mut trie = Trie::new();
        let mut min_score = f32::MAX;
        for p in &vocab.pieces {
            // The four control specials never segment user text.
            // Everything else — including literal `<0xNN>` pieces — goes
            // into the trie as an ordinary piece, matching HF's behavior
            // for this tokenizer.json (byte_fallback is not set, so the
            // `<0xNN>` strings are opaque literals).
            if p.id == vocab.special.pad_id
                || p.id == vocab.special.bos_id
                || p.id == vocab.special.eos_id
                || p.id == vocab.special.unk_id
            {
                continue;
            }
            trie.insert(p.text.as_bytes(), p.id, p.score);
            if p.score < min_score {
                min_score = p.score;
            }
        }
        if min_score == f32::MAX {
            min_score = 0.0;
        }
        Self {
            vocab,
            trie,
            min_score,
            unk_id,
        }
    }

    pub fn from_file<P: AsRef<Path>>(path: P) -> Result<Self> {
        Ok(Self::from_vocab(Vocab::load(path)?))
    }

    pub fn vocab(&self) -> &Vocab {
        &self.vocab
    }
    pub fn vocab_size(&self) -> usize {
        self.vocab.len()
    }

    /// Encode `text` into a sequence of token IDs. Produces the same
    /// ids as HF `transformers.AutoTokenizer` on the same tokenizer.json.
    pub fn encode(&self, text: &str) -> Vec<u32> {
        let mut out = Vec::with_capacity(text.len() / 3 + 1);
        for chunk in pretokenize_chunks(text) {
            self.encode_chunk(&chunk, &mut out);
        }
        out
    }

    /// Alias kept for callers that used the old API name.
    pub fn encode_pretokenized(&self, pre: &str) -> Vec<u32> {
        // `pre` is already metaspace-form — split on ▁ into chunks and run.
        let mut out = Vec::with_capacity(pre.len() / 3 + 1);
        let marker = WORD_START.to_string();
        for chunk in pre.split(&marker).filter(|s| !s.is_empty()) {
            let mut with_marker = String::with_capacity(chunk.len() + 3);
            with_marker.push(WORD_START);
            with_marker.push_str(chunk);
            self.encode_chunk(&with_marker, &mut out);
        }
        out
    }

    fn encode_chunk(&self, sentence: &str, out: &mut Vec<u32>) {
        let bytes = sentence.as_bytes();
        let size = bytes.len();
        if size == 0 {
            return;
        }
        let mut best = vec![BestNode::default(); size + 1];
        best[0].starts_at = Some(0);
        best[0].best_score = 0.0;

        let mut starts_at = 0usize;
        while starts_at < size {
            let mblen = utf8_char_len(bytes[starts_at]);
            // If this position was never reached, we still need to advance
            // so the backtrace can finish. Seed it with a fresh path from
            // the previous char if none exists.
            if best[starts_at].starts_at.is_none() {
                starts_at += mblen;
                continue;
            }
            let best_score_till_here = best[starts_at].best_score;
            let mut has_single_node = false;

            // common_prefix_search: walk the trie along bytes, yielding
            // matches shortest-first as we descend through leaf nodes.
            let mut node = 0u32;
            let mut i = 0usize;
            while starts_at + i < size {
                let b = bytes[starts_at + i];
                match self.trie.children[node as usize].get(&b) {
                    Some(&next) => {
                        node = next;
                        i += 1;
                        if let Some(id) = self.trie.leaf_id[node as usize] {
                            let piece_score = self.trie.leaf_score[node as usize];
                            let key_pos = starts_at + i;
                            let candidate = best_score_till_here + piece_score;
                            let target = &mut best[key_pos];
                            if target.starts_at.is_none() || candidate > target.best_score {
                                target.starts_at = Some(starts_at as u32);
                                target.best_score = candidate;
                                target.id = id;
                            }
                            if !has_single_node && i == mblen {
                                has_single_node = true;
                            }
                        }
                    }
                    None => break,
                }
            }

            if !has_single_node {
                let unk_score = self.min_score - K_UNK_PENALTY;
                let key_pos = starts_at + mblen;
                let candidate = best_score_till_here + unk_score;
                let target = &mut best[key_pos];
                if target.starts_at.is_none() || candidate > target.best_score {
                    target.starts_at = Some(starts_at as u32);
                    target.best_score = candidate;
                    target.id = self.unk_id;
                }
            }
            starts_at += mblen;
        }

        // Backtrace
        let mut ends_at = size;
        let start_len = out.len();
        while ends_at > 0 {
            let node = best[ends_at];
            let sa = match node.starts_at {
                Some(v) => v as usize,
                // Safety net: if something unreachable crept through,
                // bail with unk rather than panic.
                None => {
                    out.push(self.unk_id);
                    break;
                }
            };
            out.push(node.id);
            ends_at = sa;
        }
        out[start_len..].reverse();
    }

    /// Decode a sequence of token IDs back to text. Matches HF decoding:
    /// concatenate piece texts (including literal `<0xNN>` strings if any
    /// slipped in), then reverse-metaspace.
    pub fn decode(&self, ids: &[u32]) -> String {
        let mut bytes: Vec<u8> = Vec::new();
        for &id in ids {
            if id == self.vocab.special.pad_id
                || id == self.vocab.special.bos_id
                || id == self.vocab.special.eos_id
                || id == self.vocab.special.unk_id
            {
                continue;
            }
            if let Some(text) = self.vocab.get_text(id) {
                bytes.extend_from_slice(text.as_bytes());
            }
        }
        let s = String::from_utf8_lossy(&bytes).into_owned();
        reverse_metaspace(&s)
    }

    pub fn decode_pieces(&self, ids: &[u32]) -> Vec<String> {
        ids.iter()
            .map(|&i| self.vocab.get_text(i).unwrap_or("<unk>").to_string())
            .collect()
    }
}

fn utf8_char_len(first_byte: u8) -> usize {
    // Malformed continuation bytes (0x80-0xBF) are bucketed with ASCII at 1
    // so the outer loop still makes progress on invalid UTF-8.
    if first_byte < 0xC0 {
        1
    } else if first_byte < 0xE0 {
        2
    } else if first_byte < 0xF0 {
        3
    } else {
        4
    }
}

/// Split input into HF-Metaspace chunks: whitespace runs are delimiters,
/// each non-whitespace run becomes a chunk with a leading `▁`.
fn pretokenize_chunks(input: &str) -> Vec<String> {
    let mut chunks = Vec::new();
    let mut cur = String::new();
    let mut in_word = false;
    for ch in input.chars() {
        if ch.is_ascii_whitespace() {
            if in_word {
                chunks.push(std::mem::take(&mut cur));
                in_word = false;
            }
        } else {
            if !in_word {
                cur.push(WORD_START);
                in_word = true;
            }
            cur.push(ch);
        }
    }
    if in_word {
        chunks.push(cur);
    }
    chunks
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::vocab::{Piece, SpecialTokens};

    fn mini_vocab() -> Vocab {
        let pieces = vec![
            Piece {
                id: 0,
                text: "<pad>".to_string(),
                score: 0.0,
            },
            Piece {
                id: 1,
                text: "<unk>".to_string(),
                score: 0.0,
            },
            Piece {
                id: 2,
                text: "<s>".to_string(),
                score: 0.0,
            },
            Piece {
                id: 3,
                text: "</s>".to_string(),
                score: 0.0,
            },
            Piece {
                id: 4,
                text: "\u{2581}hello".to_string(),
                score: 0.0,
            },
            Piece {
                id: 5,
                text: "\u{2581}world".to_string(),
                score: 0.0,
            },
            Piece {
                id: 6,
                text: "!".to_string(),
                score: 0.0,
            },
        ];
        Vocab::new(pieces, SpecialTokens::default())
    }

    #[test]
    fn encode_known_words() {
        let t = Tokenizer::from_vocab(mini_vocab());
        let ids = t.encode("hello world");
        assert_eq!(ids, vec![4, 5]);
    }

    #[test]
    fn encode_with_punct_chunked() {
        // "hello" and "world!" are separate chunks; within "▁world!"
        // the Viterbi path picks ▁world then !
        let t = Tokenizer::from_vocab(mini_vocab());
        let ids = t.encode("hello world!");
        assert_eq!(ids, vec![4, 5, 6]);
    }

    #[test]
    fn unknown_char_becomes_unk() {
        let t = Tokenizer::from_vocab(mini_vocab());
        let ids = t.encode("xy");
        // No piece covers 'x' or 'y' and no byte-fallback pieces in mini
        // vocab → every char becomes unk.
        assert!(ids.iter().all(|&i| i == 1));
    }

    #[test]
    fn decode_roundtrip_basic() {
        let t = Tokenizer::from_vocab(mini_vocab());
        let ids = t.encode("hello world");
        let back = t.decode(&ids);
        assert_eq!(back.trim_start(), "hello world");
    }

    #[test]
    fn empty_input_yields_empty() {
        let t = Tokenizer::from_vocab(mini_vocab());
        assert!(t.encode("").is_empty());
        assert_eq!(t.decode(&[]), "");
    }

    #[test]
    fn multiple_whitespace_collapses() {
        let t = Tokenizer::from_vocab(mini_vocab());
        let a = t.encode("hello world");
        let b = t.encode("hello    world");
        let c = t.encode("  hello\tworld  ");
        assert_eq!(a, b);
        assert_eq!(a, c);
    }

    #[test]
    fn longest_match_beats_piecewise() {
        // With "▁hello" in vocab, "hello" encodes to the single piece,
        // not to characters.
        let t = Tokenizer::from_vocab(mini_vocab());
        assert_eq!(t.encode("hello"), vec![4]);
    }

    #[test]
    fn unicode_passes_through_as_unk() {
        // mini_vocab has no multibyte chars; they become unk (not panic).
        let t = Tokenizer::from_vocab(mini_vocab());
        let ids = t.encode("α β γ");
        assert!(!ids.is_empty());
        assert!(ids.iter().all(|&i| i == 1));
    }

    #[test]
    fn tie_holds_first_reacher() {
        // Vocab has both "▁ab" and "▁a"+"b". At starts_at=0 the trie walk
        // yields "▁a" (writes position 4) then "▁ab" (writes position 5).
        // Downstream, starts_at=4 sees piece "b" which ties best[5]'s
        // existing score (0.0 == 0.0) — strict `>` means no overwrite,
        // so backtrace returns the single piece "▁ab".
        let pieces = vec![
            Piece {
                id: 0,
                text: "<pad>".to_string(),
                score: 0.0,
            },
            Piece {
                id: 1,
                text: "<unk>".to_string(),
                score: 0.0,
            },
            Piece {
                id: 2,
                text: "<s>".to_string(),
                score: 0.0,
            },
            Piece {
                id: 3,
                text: "</s>".to_string(),
                score: 0.0,
            },
            Piece {
                id: 4,
                text: "\u{2581}a".to_string(),
                score: 0.0,
            },
            Piece {
                id: 5,
                text: "b".to_string(),
                score: 0.0,
            },
            Piece {
                id: 6,
                text: "\u{2581}ab".to_string(),
                score: 0.0,
            },
        ];
        let t = Tokenizer::from_vocab(Vocab::new(pieces, SpecialTokens::default()));
        let ids = t.encode("ab");
        assert_eq!(ids, vec![6]);
    }

    #[test]
    fn long_word_stays_within_capacity() {
        // No crash on a 10kB input; all 10000 'z' chars + the leading ▁
        // marker each become unk in mini vocab → 10001 ids.
        let t = Tokenizer::from_vocab(mini_vocab());
        let big: String = "z".repeat(10_000);
        let ids = t.encode(&big);
        assert_eq!(ids.len(), 10_001);
        assert!(ids.iter().all(|&i| i == 1));
    }

    #[test]
    fn special_tokens_stripped_on_decode() {
        let t = Tokenizer::from_vocab(mini_vocab());
        // pad=0, bos=2, eos=3 — injecting them should be silent.
        let back = t.decode(&[2, 4, 5, 3]);
        assert_eq!(back.trim_start(), "hello world");
    }

    #[test]
    fn decode_pieces_preserves_markers() {
        let t = Tokenizer::from_vocab(mini_vocab());
        let ids = t.encode("hello world!");
        let pieces = t.decode_pieces(&ids);
        assert_eq!(pieces, vec!["▁hello", "▁world", "!"]);
    }
}
