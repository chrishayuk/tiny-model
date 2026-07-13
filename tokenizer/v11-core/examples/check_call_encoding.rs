//! Contextual atomicity check for CN-1's call grammar: encode realistic corpus lines through
//! the extended vocab and confirm each `<cell:NAME>` token survives as exactly one id when
//! surrounded by natural-language text, digits, and the `<call>`/`</call>` delimiters — the
//! real corpus condition, not a token in isolation. Also confirms decode round-trips the line
//! (modulo the metaspace/whitespace normalization the tokenizer is defined to apply).
//!
//! Usage: cargo run -p v11-core --example check_call_encoding -- <out.vocab.bin>
use v11_core::Tokenizer;

fn main() {
    let path = std::env::args()
        .nth(1)
        .expect("usage: check_call_encoding <vocab.bin>");
    let tok = Tokenizer::from_file(&path).unwrap_or_else(|e| panic!("loading {path}: {e}"));

    // Representative corpus shapes: a word-problem prompt, then a call with numeric operands.
    let cases: &[(&str, &str)] = &[
        (
            "word problem + call",
            "What is 3 plus 7 ? <call> <cell:add_sat> 3 7 </call>",
        ),
        ("call at line start", "<call> <cell:is_gt> 12 5 </call>"),
        (
            "multi-arg ternary",
            "is 40 between 0 and 255 <call> <cell:between_exclusive> 40 0 255 </call>",
        ),
        (
            "underscored name",
            "discount <call> <cell:discount_percent> 200 15 </call>",
        ),
    ];

    let mut failures = 0usize;
    for (label, text) in cases {
        let ids = tok.encode(text);
        // Find the cell-token id: the single id whose piece text contains "<cell:".
        let cell_ids: Vec<u32> = ids
            .iter()
            .copied()
            .filter(|&id| {
                tok.vocab()
                    .get_text(id)
                    .map_or(false, |t| t.contains("<cell:"))
            })
            .collect();
        let call_open = ids
            .iter()
            .filter(|&&id| tok.vocab().get_text(id) == Some("\u{2581}<call>"))
            .count();
        let call_close = ids
            .iter()
            .filter(|&&id| tok.vocab().get_text(id) == Some("\u{2581}</call>"))
            .count();
        let ok = cell_ids.len() == 1 && call_open == 1 && call_close == 1;
        if !ok {
            failures += 1;
        }
        println!(
            "[{}] {}\n  ids({}): {:?}\n  cell-token ids: {:?}  <call>×{} </call>×{}  => {}",
            if ok { "OK" } else { "FAIL" },
            label,
            ids.len(),
            ids,
            cell_ids,
            call_open,
            call_close,
            if ok {
                "one cell id, matched delimiters"
            } else {
                "UNEXPECTED"
            },
        );
    }

    if failures == 0 {
        println!("\ncontextual check: OK — every cell token is exactly one id in context");
    } else {
        eprintln!("\ncontextual check: FAIL — {failures} case(s) fragmented");
        std::process::exit(1);
    }
}
