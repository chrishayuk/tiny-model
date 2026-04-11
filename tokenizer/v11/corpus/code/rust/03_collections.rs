use std::collections::HashMap;
use std::collections::BTreeMap;

pub fn word_count(text: &str) -> HashMap<String, u32> {
    let mut counts: HashMap<String, u32> = HashMap::new();
    for word in text.split_whitespace() {
        *counts.entry(word.to_string()).or_insert(0) += 1;
    }
    counts
}

pub fn sort_by_value(map: HashMap<String, i32>) -> Vec<(String, i32)> {
    let mut pairs: Vec<(String, i32)> = map.into_iter().collect();
    pairs.sort_by(|a, b| b.1.cmp(&a.1));
    pairs
}

pub fn parse_int(s: &str) -> Result<i64, String> {
    s.parse::<i64>().map_err(|e| format!("parse error: {}", e))
}

pub fn read_lines(path: &str) -> Result<Vec<String>, std::io::Error> {
    let contents = std::fs::read_to_string(path)?;
    Ok(contents.lines().map(String::from).collect())
}
