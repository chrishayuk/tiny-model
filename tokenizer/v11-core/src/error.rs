use thiserror::Error;

#[derive(Debug, Error)]
pub enum Error {
    #[error("io error: {0}")]
    Io(#[from] std::io::Error),

    #[error("bincode error: {0}")]
    Bincode(#[from] bincode::Error),

    #[error("json error: {0}")]
    Json(#[from] serde_json::Error),

    #[error("invalid vocab file: {0}")]
    InvalidVocab(String),

    #[error("unknown token id: {0}")]
    UnknownId(u32),

    #[error("byte fallback disabled and token not in vocab: {0:?}")]
    MissingToken(String),
}

pub type Result<T> = std::result::Result<T, Error>;
