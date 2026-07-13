//! Append user-defined atomic tokens to a v11 vocabulary by append-only re-serialization.
//!
//! The v11 format's writer (`Vocab::save`) is public and ids are `u32` with no runtime
//! ceiling, so new tokens go in at the tail: every existing id 0..len-1 keeps its bytes and
//! its position, which is exactly what lets an already-trained embedding table survive the
//! extension (only new rows are added). This is the append path the tokenizer's own SPEC
//! calls out, done without re-running the builder (which would re-derive WordNet/Wikidata/AST
//! and could shift tail ids).
//!
//! Usage:
//!   cargo run -p v11-core --example append_user_tokens -- <base.vocab.bin> <tokens.txt> <out.vocab.bin>
//!
//! `tokens.txt` is one token *natural surface form* per line (UTF-8, no whitespace inside a
//! token — the pretokenizer splits on whitespace, so a token containing a space could never
//! be emitted as one id). The tool stores each as a `▁`-prefixed piece (`WORD_START + tok`),
//! because the pretokenizer prepends `▁` to every whitespace-delimited run: the byte string a
//! standalone `<cell:add_sat>` actually presents to the trie is `▁<cell:add_sat>`, so that is
//! the form the vocab must hold for the token to be one id. Tokens whose `▁`-form is already
//! present are skipped (reported). After writing, the tool reloads the result, builds a
//! `Tokenizer`, and self-checks that **every newly added token, encoded from its natural
//! surface, is exactly one id** — the property the whole call grammar depends on. A token
//! that fails is reported and the process exits nonzero, because a cell token that silently
//! fragments is a broken address, not a warning.
use v11_core::vocab::Piece;
use v11_core::{Tokenizer, Vocab, WORD_START};

fn main() {
    let args: Vec<String> = std::env::args().skip(1).collect();
    if args.len() < 3 || args.len() > 4 {
        eprintln!(
            "usage: append_user_tokens <base.vocab.bin> <tokens.txt> <out.vocab.bin> [map.json]"
        );
        std::process::exit(2);
    }
    let (base_path, tokens_path, out_path) = (&args[0], &args[1], &args[2]);
    let map_path = args.get(3);

    let mut vocab = Vocab::load(base_path).unwrap_or_else(|e| panic!("loading {base_path}: {e}"));
    let base_len = vocab.len();

    let raw = std::fs::read_to_string(tokens_path)
        .unwrap_or_else(|e| panic!("reading {tokens_path}: {e}"));

    // Each added piece stores the ▁-prefixed form; `added` keeps the natural surfaces so the
    // self-check can encode exactly what the corpus will contain.
    let mut added: Vec<String> = Vec::new();
    let mut skipped_present = 0usize;
    let mut seen_in_file = std::collections::HashSet::new();
    for line in raw.lines() {
        let tok = line;
        if tok.is_empty() {
            continue;
        }
        if tok.chars().any(|c| c.is_whitespace()) {
            panic!("token {tok:?} contains whitespace — it could never encode to one id");
        }
        if tok.starts_with(WORD_START) {
            panic!("token {tok:?} already starts with WORD_START — pass natural surfaces, the tool adds ▁");
        }
        if !seen_in_file.insert(tok.to_string()) {
            continue; // duplicate line in the input file
        }
        let piece_text = format!("{WORD_START}{tok}");
        if vocab.get_id(&piece_text).is_some() {
            skipped_present += 1;
            continue;
        }
        let id = (base_len + added.len()) as u32;
        vocab.pieces.push(Piece {
            id,
            text: piece_text,
            score: 0.0,
        });
        added.push(tok.to_string());
    }
    // Rebuild the text_to_id map to include the appended pieces.
    let vocab = Vocab::new(vocab.pieces, vocab.special);

    vocab
        .save(out_path)
        .unwrap_or_else(|e| panic!("saving {out_path}: {e}"));

    // Self-check: reload from disk (proves the artifact round-trips) and confirm every added
    // token encodes to exactly one id. The pretokenizer prepends WORD_START (▁) to every
    // whitespace-delimited run, so the encodable surface of a standalone token is ▁<tok>;
    // that is the form the corpus will present and the form that must be atomic.
    let tok =
        Tokenizer::from_file(out_path).unwrap_or_else(|e| panic!("reloading {out_path}: {e}"));
    let mut fragmented = Vec::new();
    for t in &added {
        let ids = tok.encode(t); // encode() applies pretokenization → ▁-prefixed chunk
        if ids.len() != 1 {
            fragmented.push((t.clone(), ids.len()));
        }
    }

    println!(
        "base pieces: {base_len}\nadded: {}\nskipped (already present): {skipped_present}\nnew total: {}\nnew id range: {}..{}",
        added.len(),
        vocab.len(),
        base_len,
        vocab.len().saturating_sub(1),
    );
    // Confirm the natural surface maps to a stable single id, and show a couple of examples.
    for t in added.iter().take(3) {
        let ids = tok.encode(t);
        println!(
            "  sample: encode({t:?}) = {ids:?}  (stored piece {:?})",
            format!("{WORD_START}{t}")
        );
    }

    // Optional sidecar: the authoritative {natural_surface -> id} map for every added token,
    // so the corpus tokenizer, W_f embedding placement, and the constrained-decode mask all
    // read one source of truth rather than re-deriving ids from file order.
    if let Some(mp) = map_path {
        let mut entries: Vec<String> = Vec::with_capacity(added.len());
        for t in &added {
            let id = tok
                .encode(t)
                .first()
                .copied()
                .unwrap_or_else(|| panic!("added token {t:?} did not encode"));
            let key = serde_json::to_string(t).unwrap_or_else(|e| panic!("json key {t:?}: {e}"));
            entries.push(format!("  {key}: {id}"));
        }
        let body = format!("{{\n{}\n}}\n", entries.join(",\n"));
        std::fs::write(mp, body).unwrap_or_else(|e| panic!("writing {mp}: {e}"));
        println!("wrote token->id map: {mp}");
    }

    if fragmented.is_empty() {
        println!(
            "self-check: OK — all {} added tokens encode to exactly one id",
            added.len()
        );
    } else {
        eprintln!(
            "self-check: FAIL — {} added tokens fragment into multiple ids (first 10):",
            fragmented.len()
        );
        for (t, n) in fragmented.iter().take(10) {
            eprintln!("  {t:?} -> {n} ids");
        }
        std::process::exit(1);
    }
}
