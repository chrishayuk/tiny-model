//! v11 knowledge-first tokenizer — pure-Rust runtime.
//!
//! Given a pre-built vocabulary (produced by `v11-builder`), this
//! crate provides deterministic longest-match tokenization with
//! UTF-8 byte fallback for any input the vocab doesn't cover.
//!
//! ```no_run
//! use v11_core::Tokenizer;
//!
//! let tok = Tokenizer::from_file("v11/artifacts/v11.vocab.bin").unwrap();
//! let ids = tok.encode("def fibonacci(n):");
//! let text = tok.decode(&ids);
//! ```

pub mod error;
pub mod pretokenize;
pub mod tokenizer;
pub mod vocab;

pub use error::{Error, Result};
pub use tokenizer::Tokenizer;
pub use vocab::{SpecialTokens, Vocab};

/// Reserved special-token IDs. Every built vocab must have these
/// at these indices.
pub const PAD_ID: u32 = 0;
pub const UNK_ID: u32 = 1;
pub const BOS_ID: u32 = 2;
pub const EOS_ID: u32 = 3;

/// SentencePiece word-start marker. v11 inherits the convention so
/// downstream compilation gates can match tokens at word boundaries.
pub const WORD_START: char = '\u{2581}';
