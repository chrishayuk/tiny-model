//! Demo — show code-specific single-token hits.

use anyhow::Result;
use v11_core::Tokenizer;

fn main() -> Result<()> {
    let tok = Tokenizer::from_file("v11/artifacts/v11.vocab.bin")?;

    let checks = [
        (
            "Python",
            &[
                "def", "class", "import", "return", "yield", "async", "await", "lambda",
            ][..],
        ),
        (
            "Rust",
            &[
                "fn", "let", "mut", "struct", "enum", "trait", "impl", "pub", "Vec", "String",
                "i32", "u64", "f64", "Option", "Result",
            ][..],
        ),
        (
            "JS/TS",
            &[
                "function",
                "const",
                "interface",
                "type",
                "extends",
                "implements",
            ][..],
        ),
        (
            "C",
            &[
                "int", "char", "void", "struct", "typedef", "malloc", "printf", "size_t",
                "uint32_t",
            ][..],
        ),
        ("Go", &["func", "package", "chan", "go", "defer"][..]),
        ("Acronyms", &["JSON", "HTTP", "SQL", "API", "URL"][..]),
        ("Greek", &["α", "β", "γ", "π", "σ"][..]),
        (
            "Science",
            &[
                "photosynthesis",
                "chromosome",
                "electromagnetic",
                "hydrogen",
                "thermodynamics",
                "algorithm",
            ][..],
        ),
    ];

    let mut total_hits = 0usize;
    let mut total_checks = 0usize;
    for (label, words) in checks {
        let mut hits = 0usize;
        for w in words {
            let ids = tok.encode(w);
            if ids.len() == 1 {
                hits += 1;
            }
        }
        total_hits += hits;
        total_checks += words.len();
        println!("{label:12}  {hits}/{}", words.len());
    }
    println!("{:12}  {total_hits}/{total_checks}", "TOTAL");
    Ok(())
}
