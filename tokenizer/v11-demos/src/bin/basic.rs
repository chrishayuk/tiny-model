//! Demo — encode + decode a few sample sentences.

use anyhow::Result;
use v11_core::Tokenizer;

fn main() -> Result<()> {
    let tok = Tokenizer::from_file("v11/artifacts/v11.vocab.bin")?;

    let samples = [
        "The capital of France is Paris.",
        "def fibonacci(n): return fibonacci(n - 1) + fibonacci(n - 2)",
        "fn main() { println!(\"Hello, world!\"); }",
        "Photosynthesis converts sunlight into chemical energy.",
        "α + β = γ",
    ];

    for s in samples {
        let ids = tok.encode(s);
        let pieces = tok.decode_pieces(&ids);
        let back = tok.decode(&ids);
        println!("\ntext:   {s}");
        println!("pieces: {pieces:?}");
        println!("ids:    {ids:?}");
        println!("back:   {back}");
    }

    Ok(())
}
