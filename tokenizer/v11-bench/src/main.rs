//! v11-bench — performance benchmark for v11 core.
//!
//! Measures:
//!   - load time     (vocab file → in-memory Tokenizer)
//!   - encode speed  (tokens/second on various input sources)
//!   - decode speed  (ids → text round-trip)
//!   - chars/token   (compression ratio per corpus subdir)
//!
//! Ecosystem comparison (gemma/llama/tiktoken/mistral vs v11) is a
//! follow-up pass — the Rust crates for those tokenizers have heavier
//! build requirements so the first pass measures v11 in isolation
//! and compares against the v10c Python benchmark results on the
//! same corpus.

use std::path::PathBuf;
use std::time::Instant;

use anyhow::{Context, Result};
use clap::Parser;
use walkdir::WalkDir;

use v11_core::Tokenizer;

#[derive(Parser, Debug)]
#[command(author, version, about)]
struct Args {
    #[arg(long, default_value = "v11/artifacts/v11.vocab.bin")]
    model: PathBuf,

    #[arg(long, default_value = "v11/corpus")]
    corpus: PathBuf,

    /// Number of warmup encode passes before measuring
    #[arg(long, default_value_t = 3)]
    warmup: usize,

    /// Number of measured encode passes
    #[arg(long, default_value_t = 10)]
    iters: usize,
}

fn main() -> Result<()> {
    let args = Args::parse();

    println!("loading tokenizer from {}", args.model.display());
    let t0 = Instant::now();
    let tok = Tokenizer::from_file(&args.model)
        .with_context(|| format!("load {}", args.model.display()))?;
    let load_ms = t0.elapsed().as_secs_f64() * 1000.0;
    println!("  load time: {:.1} ms", load_ms);
    println!("  vocab size: {}", tok.vocab_size());

    // Collect all lines in the corpus once
    println!("\ncollecting corpus lines under {}", args.corpus.display());
    let mut lines: Vec<String> = Vec::new();
    let mut total_bytes = 0usize;
    for entry in WalkDir::new(&args.corpus) {
        let entry = entry?;
        if !entry.file_type().is_file() {
            continue;
        }
        let p = entry.path();
        if p.extension().is_some_and(|e| e == "md") {
            continue;
        }
        let text = match std::fs::read_to_string(p) {
            Ok(t) => t,
            Err(_) => continue,
        };
        for line in text.lines() {
            let l = line.trim_end();
            if l.is_empty() {
                continue;
            }
            total_bytes += l.len();
            lines.push(l.to_string());
        }
    }
    println!("  {} lines, {} bytes total", lines.len(), total_bytes);

    // Warmup
    println!("\nwarmup: {} passes", args.warmup);
    for _ in 0..args.warmup {
        for line in &lines {
            let _ = tok.encode(line);
        }
    }

    // Measure encode
    println!("measuring encode: {} passes", args.iters);
    let t0 = Instant::now();
    let mut total_tokens = 0usize;
    for _ in 0..args.iters {
        for line in &lines {
            let ids = tok.encode(line);
            total_tokens += ids.len();
        }
    }
    let enc_s = t0.elapsed().as_secs_f64();
    let tok_per_iter = total_tokens / args.iters;
    let tokens_per_sec = (total_tokens as f64) / enc_s;
    let bytes_per_sec = (total_bytes as f64 * args.iters as f64) / enc_s;
    let chars_per_token = total_bytes as f64 / tok_per_iter as f64;

    println!("\n  encode throughput: {:>10.0} tok/s", tokens_per_sec);
    println!("                     {:>10.1} MB/s", bytes_per_sec / 1e6);
    println!("  chars/token (all): {:>10.2}", chars_per_token);

    // Measure decode: encode then decode a sample
    println!("\nmeasuring decode");
    let sample: Vec<Vec<u32>> = lines.iter().map(|l| tok.encode(l)).collect();
    let t0 = Instant::now();
    let mut total = 0usize;
    for _ in 0..args.iters {
        for ids in &sample {
            let _ = tok.decode(ids);
            total += ids.len();
        }
    }
    let dec_s = t0.elapsed().as_secs_f64();
    println!("  decode throughput: {:>10.0} tok/s", total as f64 / dec_s);

    Ok(())
}
