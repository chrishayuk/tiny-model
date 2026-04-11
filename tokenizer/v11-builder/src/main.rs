//! v11-build — assemble vocabulary + write binary vocab file.
//!
//! Reads:
//!
//! - config.json (layer spec, infra, function_words, morphemes, acronyms,
//!   priority_languages, language_extras, wordnet_min_zipf,
//!   wordnet_titlecase_top_n)
//! - data/wordnet_lemmas.json (frequency-ranked nltk WordNet lemmas)
//! - tree-sitter AST JSONs (from the dataset-downloader)
//! - Wikidata pair JSONs (from the dataset-downloader)
//!
//! Writes:
//!
//! - v11.vocab.bin (binary format v11-core loads at runtime)
//! - v11.vocab.json (human-readable inspection dump)
//! - knowledge_vocab.txt (user_defined_symbols list)

use std::collections::{BTreeMap, BTreeSet};
use std::fs::File;
use std::io::{BufReader, BufWriter, Write};
use std::path::{Path, PathBuf};

use anyhow::{bail, Context, Result};
use clap::Parser;
use serde::Deserialize;
use walkdir::WalkDir;

use v11_core::vocab::{Piece, SpecialTokens, Vocab};

// ─── Config schema ────────────────────────────────────────────────────

#[derive(Debug, Deserialize)]
struct Config {
    vocab_size: Option<u32>,
    max_user_syms: Option<u32>,
    #[allow(dead_code)]
    wordnet_min_zipf: Option<f32>,
    wordnet_titlecase_top_n: Option<usize>,
    infra: BTreeMap<String, Vec<String>>,
    function_words: Vec<String>,
    morpheme_prefixes: Vec<String>,
    morpheme_suffixes: Vec<String>,
    acronyms: Vec<String>,
    priority_languages: Vec<String>,
    language_extras: BTreeMap<String, Vec<String>>,
    wikidata_max_entities: Option<usize>,
    layers: Vec<LayerSpec>,
}

#[derive(Debug, Deserialize)]
struct LayerSpec {
    name: String,
    source: String,
}

#[derive(Debug, Deserialize)]
struct TreeSitterPairs {
    pairs: Option<Vec<Vec<serde_json::Value>>>,
}

#[derive(Debug, Deserialize)]
struct WordNetData {
    lemmas: Vec<WordNetLemma>,
}

#[derive(Debug, Deserialize)]
struct WordNetLemma {
    lemma: String,
    #[allow(dead_code)]
    zipf: f32,
}

// ─── Args ─────────────────────────────────────────────────────────────

#[derive(Parser, Debug)]
#[command(author, version, about)]
struct Args {
    /// Path to config.json (default: v11/config.json)
    #[arg(long, default_value = "v11/config.json")]
    config: PathBuf,

    /// Path to the root of the v11 directory (containing data/, build/)
    #[arg(long, default_value = "v11")]
    v11_dir: PathBuf,

    /// Path to the tree-sitter AST dumps
    #[arg(long, default_value = "../dataset-downloader/data/ast")]
    ast_dir: PathBuf,

    /// Path to the Wikidata domain pair dumps
    #[arg(long, default_value = "../dataset-downloader/data/knowledge/wikidata")]
    wikidata_dir: PathBuf,

    /// Output directory for build artefacts
    #[arg(long, default_value = "v11/artifacts")]
    output: PathBuf,

    /// Verbose logging
    #[arg(short, long)]
    verbose: bool,
}

// ─── Extractors ───────────────────────────────────────────────────────

fn token_ok(s: &str) -> bool {
    let bytes = s.as_bytes();
    if bytes.is_empty() || bytes.len() > 20 {
        return false;
    }
    if s.chars().next().is_none_or(|c| c.is_ascii_digit()) {
        return false;
    }
    if s.chars().all(|c| c.is_ascii_digit()) {
        return false;
    }
    s.chars().all(|c| c.is_alphanumeric() || c == '_')
}

fn extract_from_pair_file(
    path: &Path,
    include_all_positions: bool,
    max_per_file: Option<usize>,
) -> Result<Vec<String>> {
    let f = File::open(path).with_context(|| format!("open {}", path.display()))?;
    let parsed: TreeSitterPairs = serde_json::from_reader(BufReader::new(f))
        .with_context(|| format!("parse {}", path.display()))?;
    let Some(pairs) = parsed.pairs else {
        return Ok(vec![]);
    };
    let mut out: Vec<String> = Vec::new();
    let mut seen: BTreeSet<String> = BTreeSet::new();
    for pair in pairs {
        let limit = if include_all_positions {
            pair.len()
        } else {
            1.min(pair.len())
        };
        for v in pair.iter().take(limit) {
            if let Some(s) = v.as_str() {
                if token_ok(s) && seen.insert(s.to_string()) {
                    out.push(s.to_string());
                    if let Some(cap) = max_per_file {
                        if out.len() >= cap {
                            return Ok(out);
                        }
                    }
                }
            }
        }
    }
    Ok(out)
}

fn extract_code_for_lang(lang_dir: &Path, deep: bool) -> Result<Vec<String>> {
    let mut out: BTreeSet<String> = BTreeSet::new();
    let kw = lang_dir.join("keywords.json");
    if kw.exists() {
        for t in extract_from_pair_file(&kw, true, None)? {
            out.insert(t);
        }
    }
    if deep {
        for fname in ["delimiters.json", "sequences.json", "supertypes.json"] {
            let p = lang_dir.join(fname);
            if p.exists() {
                for t in extract_from_pair_file(&p, true, None)? {
                    out.insert(t);
                }
            }
        }
        let pc = lang_dir.join("parent_child.json");
        if pc.exists() {
            // parent_child has lots of AST node names — cap to top-300
            // to avoid polluting the vocabulary with grammar internals.
            for t in extract_from_pair_file(&pc, true, Some(300))? {
                out.insert(t);
            }
        }
    }
    Ok(out.into_iter().collect())
}

fn extract_priority_code(cfg: &Config, ast_root: &Path) -> Result<Vec<String>> {
    let mut out: BTreeSet<String> = BTreeSet::new();
    for lang in &cfg.priority_languages {
        let lang_dir = ast_root.join(lang);
        if !lang_dir.exists() {
            continue;
        }
        for t in extract_code_for_lang(&lang_dir, true)? {
            out.insert(t);
        }
    }
    Ok(out.into_iter().collect())
}

fn extract_other_code(cfg: &Config, ast_root: &Path) -> Result<Vec<String>> {
    let prio: BTreeSet<&str> = cfg.priority_languages.iter().map(String::as_str).collect();
    let mut out: BTreeSet<String> = BTreeSet::new();
    for entry in WalkDir::new(ast_root).min_depth(1).max_depth(1) {
        let entry = entry?;
        if !entry.file_type().is_dir() {
            continue;
        }
        let name = entry.file_name().to_string_lossy().to_string();
        if prio.contains(name.as_str()) {
            continue;
        }
        for t in extract_code_for_lang(entry.path(), true)? {
            out.insert(t);
        }
    }
    Ok(out.into_iter().collect())
}

fn extract_wikidata(cfg: &Config, wiki_root: &Path) -> Result<Vec<String>> {
    let max = cfg.wikidata_max_entities.unwrap_or(2000);
    let mut out: BTreeSet<String> = BTreeSet::new();
    for entry in WalkDir::new(wiki_root) {
        let entry = entry?;
        if !entry.file_type().is_file() {
            continue;
        }
        let name = entry.file_name().to_string_lossy();
        if name == "manifest.json" || name == ".state.json" {
            continue;
        }
        if !name.ends_with(".json") {
            continue;
        }
        let f =
            File::open(entry.path()).with_context(|| format!("open {}", entry.path().display()))?;
        let parsed: TreeSitterPairs = match serde_json::from_reader(BufReader::new(f)) {
            Ok(p) => p,
            Err(_) => continue,
        };
        let Some(pairs) = parsed.pairs else {
            continue;
        };
        for pair in pairs {
            for v in pair {
                if let Some(s) = v.as_str() {
                    let s = s.trim();
                    if s.len() < 3 || s.len() > 20 {
                        continue;
                    }
                    if s.contains(' ') {
                        continue;
                    }
                    if !s.chars().all(|c| c.is_alphabetic()) {
                        continue;
                    }
                    if !s.chars().next().is_some_and(|c| c.is_ascii_uppercase()) {
                        continue;
                    }
                    out.insert(s.to_string());
                }
            }
        }
    }
    let mut v: Vec<String> = out.into_iter().collect();
    v.truncate(max);
    Ok(v)
}

fn extract_wordnet_lemmas(cfg: &Config, data_dir: &Path) -> Result<Vec<String>> {
    let path = data_dir.join("wordnet_lemmas.json");
    if !path.exists() {
        bail!(
            "missing {}: run preprocess_wordnet.py first",
            path.display()
        );
    }
    let f = File::open(&path)?;
    let data: WordNetData = serde_json::from_reader(BufReader::new(f))?;
    let lemmas: Vec<String> = data.lemmas.into_iter().map(|l| l.lemma).collect();

    // Interleave TitleCase variants of top-N
    let titlecase_n = cfg.wordnet_titlecase_top_n.unwrap_or(0);
    let mut out = Vec::with_capacity(lemmas.len() + titlecase_n);
    for (i, w) in lemmas.iter().enumerate() {
        out.push(w.clone());
        if i < titlecase_n
            && w.chars().next().is_some_and(|c| c.is_ascii_lowercase())
            && w.len() >= 3
        {
            let mut chars = w.chars();
            let first = chars.next().unwrap().to_ascii_uppercase();
            let rest: String = chars.collect();
            let tc = format!("{first}{rest}");
            if tc != *w {
                out.push(tc);
            }
        }
    }
    Ok(out)
}

// ─── Assembly + serialization ────────────────────────────────────────

fn is_word_like(s: &str) -> bool {
    s.chars().next().is_some_and(|c| c.is_alphabetic())
}

fn assemble(cfg: &Config, args: &Args) -> Result<Vec<String>> {
    let mut vocab: Vec<String> = Vec::new();
    let mut seen: BTreeSet<String> = BTreeSet::new(); // CASE-SENSITIVE

    let add_layer =
        |label: &str, items: Vec<String>, vocab: &mut Vec<String>, seen: &mut BTreeSet<String>| {
            let mut n = 0usize;
            for t in items {
                if seen.insert(t.clone()) {
                    vocab.push(t);
                    n += 1;
                }
            }
            if args.verbose {
                println!("  {label:24}  added {n} new tokens (total {})", vocab.len());
            }
        };

    for layer in &cfg.layers {
        let items: Vec<String> = match layer.source.as_str() {
            "infra" => cfg.infra.values().flat_map(|v| v.iter().cloned()).collect(),
            "function_words" => cfg.function_words.clone(),
            "morphemes" => {
                let mut out = cfg.morpheme_prefixes.clone();
                out.extend(cfg.morpheme_suffixes.clone());
                out
            }
            "acronyms" => cfg.acronyms.clone(),
            "code_priority" => extract_priority_code(cfg, &args.ast_dir)?,
            "code_extras" => {
                let mut out = Vec::new();
                for extras in cfg.language_extras.values() {
                    for t in extras {
                        if token_ok(t) {
                            out.push(t.clone());
                        }
                    }
                }
                out
            }
            "code_other" => extract_other_code(cfg, &args.ast_dir)?,
            "wordnet_lemmas" => {
                let data_dir = args.v11_dir.join("data");
                extract_wordnet_lemmas(cfg, &data_dir)?
            }
            "wikidata_entities" => extract_wikidata(cfg, &args.wikidata_dir)?,
            other => {
                eprintln!("  ⚠ unknown source: {other}");
                continue;
            }
        };
        add_layer(&layer.name, items, &mut vocab, &mut seen);
    }

    Ok(vocab)
}

fn finalize_pieces(vocab: Vec<String>, cfg: &Config) -> Vec<String> {
    // For word-like tokens add both plain and ▁-prefixed forms. Symbols
    // stay plain. Case-sensitive dedup (Type and type coexist).
    let mut seen: BTreeSet<String> = BTreeSet::new();
    let mut out: Vec<String> = Vec::new();
    for tok in vocab {
        if tok.is_empty() || tok.contains(char::is_whitespace) {
            continue;
        }
        if tok.len() > 64 {
            continue;
        }
        if seen.insert(tok.clone()) {
            out.push(tok.clone());
        }
        if is_word_like(&tok) {
            let prefixed = format!("\u{2581}{tok}");
            if seen.insert(prefixed.clone()) {
                out.push(prefixed);
            }
        }
    }

    // Cap if too large
    if let Some(cap) = cfg.max_user_syms {
        if out.len() > cap as usize {
            out.truncate(cap as usize);
        }
    }
    out
}

fn build_vocab_artifact(user_syms: Vec<String>) -> Vocab {
    // Reserved: pad, unk, bos, eos
    let mut pieces: Vec<Piece> = Vec::with_capacity(user_syms.len() + 260);
    pieces.push(Piece {
        id: 0,
        text: "<pad>".into(),
        score: 0.0,
    });
    pieces.push(Piece {
        id: 1,
        text: "<unk>".into(),
        score: 0.0,
    });
    pieces.push(Piece {
        id: 2,
        text: "<s>".into(),
        score: 0.0,
    });
    pieces.push(Piece {
        id: 3,
        text: "</s>".into(),
        score: 0.0,
    });
    // 256 byte fallback tokens
    for b in 0u32..256 {
        let id = 4 + b;
        pieces.push(Piece {
            id,
            text: format!("<0x{:02X}>", b),
            score: 0.0,
        });
    }
    let mut next_id: u32 = pieces.len() as u32;
    let mut seen_text: BTreeSet<String> = pieces.iter().map(|p| p.text.clone()).collect();
    for t in user_syms {
        if !seen_text.insert(t.clone()) {
            continue;
        }
        pieces.push(Piece {
            id: next_id,
            text: t,
            score: 0.0,
        });
        next_id += 1;
    }
    Vocab::new(pieces, SpecialTokens::default())
}

fn write_hf_tokenizer_json(vocab: &Vocab, path: &Path) -> Result<()> {
    // Minimal HuggingFace tokenizers-compatible JSON. v11 uses Unigram
    // scoring (all scores = 0.0 for now; could be filled in later).
    let vocab_entries: Vec<serde_json::Value> = vocab
        .pieces
        .iter()
        .map(|p| serde_json::json!([p.text, p.score]))
        .collect();

    let added: Vec<serde_json::Value> = (0..=3u32)
        .map(|id| {
            let text = vocab.get_text(id).unwrap_or("<unk>").to_string();
            serde_json::json!({
                "id": id,
                "content": text,
                "single_word": false,
                "lstrip": false,
                "rstrip": false,
                "normalized": false,
                "special": true,
            })
        })
        .collect();

    let body = serde_json::json!({
        "version": "1.0",
        "truncation": serde_json::Value::Null,
        "padding": serde_json::Value::Null,
        "added_tokens": added,
        "normalizer": serde_json::Value::Null,
        "pre_tokenizer": {
            "type": "Metaspace",
            "replacement": "\u{2581}",
            "prepend_scheme": "always"
        },
        "post_processor": serde_json::Value::Null,
        "decoder": {
            "type": "Metaspace",
            "replacement": "\u{2581}",
            "prepend_scheme": "always"
        },
        "model": {
            "type": "Unigram",
            "unk_id": 1,
            "vocab": vocab_entries,
        }
    });

    let f = File::create(path)?;
    serde_json::to_writer_pretty(BufWriter::new(f), &body)?;
    Ok(())
}

fn write_tokenizer_config(path: &Path) -> Result<()> {
    let body = serde_json::json!({
        "tokenizer_class": "PreTrainedTokenizerFast",
        "model_max_length": 2048,
        "pad_token": "<pad>",
        "unk_token": "<unk>",
        "bos_token": "<s>",
        "eos_token": "</s>",
    });
    serde_json::to_writer_pretty(BufWriter::new(File::create(path)?), &body)?;
    Ok(())
}

fn write_special_tokens_map(path: &Path) -> Result<()> {
    let body = serde_json::json!({
        "pad_token": "<pad>",
        "unk_token": "<unk>",
        "bos_token": "<s>",
        "eos_token": "</s>",
    });
    serde_json::to_writer_pretty(BufWriter::new(File::create(path)?), &body)?;
    Ok(())
}

fn write_model_card(path: &Path, vocab: &Vocab) -> Result<()> {
    let mut f = BufWriter::new(File::create(path)?);
    writeln!(f, "---")?;
    writeln!(f, "library_name: tokenizers")?;
    writeln!(f, "tags:")?;
    writeln!(f, "  - tokenizer")?;
    writeln!(f, "  - knowledge-first")?;
    writeln!(f, "language:")?;
    writeln!(f, "  - en")?;
    writeln!(f, "license: apache-2.0")?;
    writeln!(f, "---")?;
    writeln!(f)?;
    writeln!(f, "# v11 — knowledge-first tokenizer")?;
    writeln!(f)?;
    writeln!(f, "Vocabulary size: **{}**", vocab.len())?;
    writeln!(f)?;
    writeln!(
        f,
        "v11 is a pure-Rust longest-match tokenizer whose vocabulary \
                is assembled from knowledge sources (WordNet, Wikidata, \
                tree-sitter AST grammars for 77 programming languages, \
                curated morphemes, Greek letters, math symbols, acronyms) \
                rather than discovered from BPE merges on a corpus."
    )?;
    writeln!(f)?;
    writeln!(
        f,
        "Every token is a potential compilation target, so language \
                keywords, scientific terms, acronyms, and Greek letters are \
                guaranteed to be single pieces for efficient compilation."
    )?;
    writeln!(f)?;
    writeln!(f, "## Load with HuggingFace")?;
    writeln!(f, "```python")?;
    writeln!(f, "from tokenizers import Tokenizer")?;
    writeln!(f, "tok = Tokenizer.from_file(\"tokenizer.json\")")?;
    writeln!(f, "tok.encode(\"def fibonacci(n):\").tokens")?;
    writeln!(f, "```")?;
    writeln!(f)?;
    writeln!(f, "## Load with v11-cli")?;
    writeln!(f, "```bash")?;
    writeln!(f, "v11 encode --text 'def fibonacci(n):'")?;
    writeln!(f, "```")?;
    f.flush()?;
    Ok(())
}

// ─── Main ─────────────────────────────────────────────────────────────

fn main() -> Result<()> {
    let args = Args::parse();

    println!("v11-build — loading config from {}", args.config.display());
    let cfg: Config = serde_json::from_reader(BufReader::new(File::open(&args.config)?))
        .with_context(|| format!("parse {}", args.config.display()))?;

    println!("\n[1/4] assembling vocabulary from sources");
    let raw = assemble(&cfg, &args)?;
    println!("  raw vocab size: {}", raw.len());

    println!("\n[2/4] finalizing pieces (plain + ▁-prefix for word-like)");
    let user_syms = finalize_pieces(raw, &cfg);
    println!("  user_syms final: {}", user_syms.len());

    println!("\n[3/4] building Vocab artefact");
    let vocab = build_vocab_artifact(user_syms);
    println!(
        "  total pieces (incl. specials + byte fallback): {}",
        vocab.len()
    );

    println!("\n[4/4] writing outputs to {}", args.output.display());
    std::fs::create_dir_all(&args.output)?;

    let bin_path = args.output.join("v11.vocab.bin");
    vocab.save(&bin_path)?;
    println!("  wrote {}", bin_path.display());

    let json_path = args.output.join("v11.vocab.json");
    vocab.save_json(&json_path)?;
    println!("  wrote {}", json_path.display());

    let syms_path = args.output.join("knowledge_vocab.txt");
    let mut f = BufWriter::new(File::create(&syms_path)?);
    for p in &vocab.pieces {
        writeln!(f, "{}", p.text)?;
    }
    f.flush()?;
    println!("  wrote {}", syms_path.display());

    let hf_path = args.output.join("tokenizer.json");
    write_hf_tokenizer_json(&vocab, &hf_path)?;
    println!("  wrote {}", hf_path.display());

    write_tokenizer_config(&args.output.join("tokenizer_config.json"))?;
    write_special_tokens_map(&args.output.join("special_tokens_map.json"))?;
    write_model_card(&args.output.join("README.md"), &vocab)?;

    println!(
        "\nv11 build complete: {} pieces @ {}",
        vocab.len(),
        args.output.display()
    );
    if let Some(target) = cfg.vocab_size {
        println!("  target vocab_size was: {target}");
    }
    Ok(())
}
