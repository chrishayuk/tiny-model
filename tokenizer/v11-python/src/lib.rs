#![allow(clippy::useless_conversion)] // pyo3 macro expansion for PyResult<Self> trips this
//! Python bindings for the v11 knowledge-first tokenizer.
//!
//! Wraps the pure-Rust `v11-core` crate behind a small PyO3 module
//! with zero overhead beyond the FFI marshalling. All encode/decode
//! work runs in Rust — Python only sees the result.
//!
//! ```python
//! import v11
//! tok = v11.Tokenizer.from_file("v11/artifacts/v11.vocab.bin")
//! ids = tok.encode("def fibonacci(n):")
//! text = tok.decode(ids)
//! pieces = tok.encode_pieces("The capital of France is Paris")
//! print(tok.vocab_size, tok.pad_id, tok.bos_id, tok.eos_id, tok.unk_id)
//! ```

use pyo3::exceptions::PyIOError;
use pyo3::prelude::*;

use v11_core::Tokenizer as CoreTokenizer;

/// A v11 tokenizer loaded from a `.vocab.bin` file.
#[pyclass(name = "Tokenizer", module = "v11")]
pub struct PyTokenizer {
    inner: CoreTokenizer,
}

#[pymethods]
impl PyTokenizer {
    /// Load a tokenizer from a binary vocab file.
    #[staticmethod]
    #[pyo3(text_signature = "(path, /)")]
    fn from_file(path: &str) -> PyResult<Self> {
        let inner =
            CoreTokenizer::from_file(path).map_err(|e| PyIOError::new_err(format!("{e}")))?;
        Ok(Self { inner })
    }

    /// Encode text into a list of token IDs.
    #[pyo3(text_signature = "($self, text, /)")]
    fn encode(&self, text: &str) -> Vec<u32> {
        self.inner.encode(text)
    }

    /// Encode text into a list of piece strings (for inspection).
    #[pyo3(text_signature = "($self, text, /)")]
    fn encode_pieces(&self, text: &str) -> Vec<String> {
        let ids = self.inner.encode(text);
        self.inner.decode_pieces(&ids)
    }

    /// Decode a list of token IDs back to text.
    #[pyo3(text_signature = "($self, ids, /)")]
    fn decode(&self, ids: Vec<u32>) -> String {
        self.inner.decode(&ids)
    }

    /// Return the text of a single token id, or None if out of range.
    #[pyo3(text_signature = "($self, id, /)")]
    fn id_to_piece(&self, id: u32) -> Option<String> {
        self.inner.vocab().get_text(id).map(|s| s.to_string())
    }

    /// Return the id of a single piece string, or None if not in vocab.
    #[pyo3(text_signature = "($self, piece, /)")]
    fn piece_to_id(&self, piece: &str) -> Option<u32> {
        self.inner.vocab().get_id(piece)
    }

    /// Total vocabulary size (pieces including specials + byte fallbacks).
    #[getter]
    fn vocab_size(&self) -> usize {
        self.inner.vocab_size()
    }

    #[getter]
    fn pad_id(&self) -> u32 {
        self.inner.vocab().special.pad_id
    }

    #[getter]
    fn unk_id(&self) -> u32 {
        self.inner.vocab().special.unk_id
    }

    #[getter]
    fn bos_id(&self) -> u32 {
        self.inner.vocab().special.bos_id
    }

    #[getter]
    fn eos_id(&self) -> u32 {
        self.inner.vocab().special.eos_id
    }

    fn __len__(&self) -> usize {
        self.inner.vocab_size()
    }

    fn __repr__(&self) -> String {
        format!("<v11.Tokenizer vocab_size={}>", self.inner.vocab_size())
    }
}

/// The `v11` Python module.
#[pymodule]
fn v11(_py: Python<'_>, m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_class::<PyTokenizer>()?;
    m.add("__version__", "0.1.0")?;
    Ok(())
}
