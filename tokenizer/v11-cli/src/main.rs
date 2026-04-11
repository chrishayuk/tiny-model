//! v11 — knowledge-first tokenizer CLI.
//!
//! Subcommands:
//!   encode   tokenize text → ids
//!   decode   ids → text
//!   pieces   tokenize text → piece strings (for inspection)
//!   info     print vocab size, specials, sample pieces
//!   lookup   look up specific token text or id

use std::io::{self, Read};
use std::path::{Path, PathBuf};

use anyhow::{bail, Context, Result};
use clap::{Parser, Subcommand};

use v11_core::Tokenizer;

#[derive(Parser, Debug)]
#[command(name = "v11", author, version, about = "v11 knowledge-first tokenizer")]
struct Cli {
    /// Path to v11.vocab.bin. If omitted, searches a few conventional
    /// locations.
    #[arg(long, global = true)]
    model: Option<PathBuf>,

    #[command(subcommand)]
    command: Command,
}

#[derive(Subcommand, Debug)]
enum Command {
    /// Encode text to a list of token IDs
    Encode {
        /// Text to encode (use `-` or omit to read stdin)
        #[arg(long)]
        text: Option<String>,

        /// Print pieces alongside IDs
        #[arg(long)]
        show_pieces: bool,

        /// Output as JSON {"ids": [...], "pieces": [...]}
        #[arg(long)]
        json: bool,
    },

    /// Decode a comma-separated list of token IDs back to text
    Decode {
        /// Comma-separated token IDs (e.g. "2,1024,5,8")
        #[arg(long)]
        ids: String,
    },

    /// Show the piece-string form of each token for inspection
    Pieces {
        #[arg(long)]
        text: Option<String>,
    },

    /// Print vocabulary size, special tokens, and sample entries
    Info,

    /// Look up a token by text or by id
    Lookup {
        /// Token text (wraps in optional ▁ prefix if word-like)
        #[arg(long, conflicts_with = "id")]
        text: Option<String>,

        /// Token ID
        #[arg(long, conflicts_with = "text")]
        id: Option<u32>,
    },
}

fn resolve_model(explicit: Option<PathBuf>) -> Result<PathBuf> {
    if let Some(p) = explicit {
        if !p.exists() {
            bail!("model not found at {}", p.display());
        }
        return Ok(p);
    }
    let candidates = [
        "v11/artifacts/v11.vocab.bin",
        "tokenizer/v11/artifacts/v11.vocab.bin",
        "../v11/artifacts/v11.vocab.bin",
        "../tokenizer/v11/artifacts/v11.vocab.bin",
    ];
    for c in candidates {
        let p = Path::new(c);
        if p.exists() {
            return Ok(p.to_path_buf());
        }
    }
    bail!(
        "couldn't find v11.vocab.bin — pass --model <path>.\n\
         searched: {}",
        candidates.join(", ")
    );
}

fn read_text_arg(text_arg: Option<String>) -> Result<String> {
    match text_arg.as_deref() {
        Some("-") | None => {
            let mut s = String::new();
            io::stdin().read_to_string(&mut s)?;
            Ok(s.trim_end().to_string())
        }
        Some(t) => Ok(t.to_string()),
    }
}

fn main() -> Result<()> {
    let cli = Cli::parse();
    let model_path = resolve_model(cli.model)?;
    let tok = Tokenizer::from_file(&model_path)
        .with_context(|| format!("load {}", model_path.display()))?;

    match cli.command {
        Command::Encode {
            text,
            show_pieces,
            json,
        } => {
            let text = read_text_arg(text)?;
            let ids = tok.encode(&text);
            if json {
                let pieces = tok.decode_pieces(&ids);
                let body = serde_json::json!({
                    "text": text,
                    "ids": ids,
                    "pieces": pieces,
                    "n_tokens": ids.len(),
                });
                println!("{}", serde_json::to_string_pretty(&body)?);
            } else if show_pieces {
                let pieces = tok.decode_pieces(&ids);
                for (id, p) in ids.iter().zip(&pieces) {
                    println!("{id:6}  {p}");
                }
            } else {
                let s: Vec<String> = ids.iter().map(|i| i.to_string()).collect();
                println!("{}", s.join(","));
            }
        }
        Command::Decode { ids } => {
            let ids: Vec<u32> = ids
                .split(',')
                .map(|s| s.trim().parse::<u32>())
                .collect::<std::result::Result<_, _>>()
                .context("failed to parse --ids (expected comma-separated u32s)")?;
            println!("{}", tok.decode(&ids));
        }
        Command::Pieces { text } => {
            let text = read_text_arg(text)?;
            let ids = tok.encode(&text);
            let pieces = tok.decode_pieces(&ids);
            for p in pieces {
                println!("{p}");
            }
        }
        Command::Info => {
            let v = tok.vocab();
            println!("model: {}", model_path.display());
            println!("vocab_size: {}", v.len());
            println!(
                "special: pad={} unk={} bos={} eos={}",
                v.special.pad_id, v.special.unk_id, v.special.bos_id, v.special.eos_id,
            );
            println!("sample pieces:");
            for p in v.pieces.iter().take(20) {
                println!("  {:5}  {}", p.id, p.text);
            }
        }
        Command::Lookup { text, id } => {
            let v = tok.vocab();
            if let Some(text) = text {
                match v.get_id(&text) {
                    Some(id) => println!("{id}\t{text}"),
                    None => {
                        // Try ▁-prefix
                        let prefixed = format!("\u{2581}{text}");
                        match v.get_id(&prefixed) {
                            Some(id) => println!("{id}\t{prefixed}  (word-boundary form)"),
                            None => println!("not in vocab: {text}"),
                        }
                    }
                }
            } else if let Some(id) = id {
                match v.get_text(id) {
                    Some(text) => println!("{id}\t{text}"),
                    None => println!("id out of range: {id}"),
                }
            } else {
                bail!("lookup requires --text or --id");
            }
        }
    }
    Ok(())
}
