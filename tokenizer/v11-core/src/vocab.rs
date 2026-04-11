//! Vocabulary representation + binary (de)serialisation.
//!
//! Binary format (little-endian):
//!
//! ```text
//!     magic      "V11V"              4 bytes
//!     version    u32                 4 bytes
//!     n_pieces   u32                 4 bytes
//!     special    SpecialTokens       16 bytes (4 × u32)
//!     pieces     [Piece; n_pieces]
//!
//!     Piece {
//!         id         u32             4 bytes
//!         score      f32             4 bytes  (log-prob, 0.0 if unused)
//!         byte_len   u32             4 bytes
//!         bytes      [u8; byte_len]
//!     }
//! ```

use std::fs::File;
use std::io::{BufReader, BufWriter, Read, Write};
use std::path::Path;

use byteorder::{LittleEndian, ReadBytesExt, WriteBytesExt};
use serde::{Deserialize, Serialize};

use crate::error::{Error, Result};

pub const MAGIC: &[u8; 4] = b"V11V";
pub const VERSION: u32 = 1;

#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize, Deserialize)]
pub struct SpecialTokens {
    pub pad_id: u32,
    pub unk_id: u32,
    pub bos_id: u32,
    pub eos_id: u32,
}

impl Default for SpecialTokens {
    fn default() -> Self {
        Self {
            pad_id: crate::PAD_ID,
            unk_id: crate::UNK_ID,
            bos_id: crate::BOS_ID,
            eos_id: crate::EOS_ID,
        }
    }
}

/// One vocabulary entry.
#[derive(Clone, Debug, PartialEq, Serialize, Deserialize)]
pub struct Piece {
    pub id: u32,
    pub text: String,
    pub score: f32,
}

/// Full vocabulary — flat list of pieces plus reverse lookup.
#[derive(Clone, Debug)]
pub struct Vocab {
    pub pieces: Vec<Piece>,
    pub special: SpecialTokens,
    /// text -> id map, built once at load time for O(1) lookup during
    /// longest-match scanning.
    pub text_to_id: std::collections::HashMap<String, u32>,
}

impl Vocab {
    pub fn new(pieces: Vec<Piece>, special: SpecialTokens) -> Self {
        let mut text_to_id = std::collections::HashMap::with_capacity(pieces.len());
        for p in &pieces {
            text_to_id.insert(p.text.clone(), p.id);
        }
        Self {
            pieces,
            special,
            text_to_id,
        }
    }

    pub fn len(&self) -> usize {
        self.pieces.len()
    }

    pub fn is_empty(&self) -> bool {
        self.pieces.is_empty()
    }

    pub fn get_id(&self, text: &str) -> Option<u32> {
        self.text_to_id.get(text).copied()
    }

    pub fn get_text(&self, id: u32) -> Option<&str> {
        self.pieces.get(id as usize).map(|p| p.text.as_str())
    }

    /// Byte fallback ID for a raw u8. Byte fallback tokens are
    /// encoded as `<0xNN>` by convention and live in a reserved
    /// range right after the specials. The builder writes them.
    pub fn byte_fallback_id(&self, byte: u8) -> Option<u32> {
        let key = format!("<0x{:02X}>", byte);
        self.get_id(&key)
    }

    /// Write this vocab to a binary file in the v11 format.
    pub fn save<P: AsRef<Path>>(&self, path: P) -> Result<()> {
        let f = File::create(path)?;
        let mut w = BufWriter::new(f);
        w.write_all(MAGIC)?;
        w.write_u32::<LittleEndian>(VERSION)?;
        w.write_u32::<LittleEndian>(self.pieces.len() as u32)?;
        w.write_u32::<LittleEndian>(self.special.pad_id)?;
        w.write_u32::<LittleEndian>(self.special.unk_id)?;
        w.write_u32::<LittleEndian>(self.special.bos_id)?;
        w.write_u32::<LittleEndian>(self.special.eos_id)?;
        for p in &self.pieces {
            w.write_u32::<LittleEndian>(p.id)?;
            w.write_f32::<LittleEndian>(p.score)?;
            let bytes = p.text.as_bytes();
            w.write_u32::<LittleEndian>(bytes.len() as u32)?;
            w.write_all(bytes)?;
        }
        w.flush()?;
        Ok(())
    }

    /// Load a vocab from the binary v11 format.
    pub fn load<P: AsRef<Path>>(path: P) -> Result<Self> {
        let f = File::open(path)?;
        let mut r = BufReader::new(f);
        let mut magic = [0u8; 4];
        r.read_exact(&mut magic)?;
        if &magic != MAGIC {
            return Err(Error::InvalidVocab(format!(
                "bad magic: expected {MAGIC:?}, got {magic:?}"
            )));
        }
        let version = r.read_u32::<LittleEndian>()?;
        if version != VERSION {
            return Err(Error::InvalidVocab(format!(
                "version mismatch: expected {VERSION}, got {version}"
            )));
        }
        let n_pieces = r.read_u32::<LittleEndian>()? as usize;
        let special = SpecialTokens {
            pad_id: r.read_u32::<LittleEndian>()?,
            unk_id: r.read_u32::<LittleEndian>()?,
            bos_id: r.read_u32::<LittleEndian>()?,
            eos_id: r.read_u32::<LittleEndian>()?,
        };
        let mut pieces = Vec::with_capacity(n_pieces);
        for _ in 0..n_pieces {
            let id = r.read_u32::<LittleEndian>()?;
            let score = r.read_f32::<LittleEndian>()?;
            let byte_len = r.read_u32::<LittleEndian>()? as usize;
            let mut bytes = vec![0u8; byte_len];
            r.read_exact(&mut bytes)?;
            let text = String::from_utf8(bytes)
                .map_err(|e| Error::InvalidVocab(format!("piece not utf-8: {e}")))?;
            pieces.push(Piece { id, text, score });
        }
        Ok(Self::new(pieces, special))
    }

    /// Dump to a human-readable JSON (for inspection / debugging).
    pub fn save_json<P: AsRef<Path>>(&self, path: P) -> Result<()> {
        #[derive(Serialize)]
        struct Dump<'a> {
            version: u32,
            special: &'a SpecialTokens,
            pieces: &'a [Piece],
        }
        let dump = Dump {
            version: VERSION,
            special: &self.special,
            pieces: &self.pieces,
        };
        let f = File::create(path)?;
        serde_json::to_writer_pretty(BufWriter::new(f), &dump)?;
        Ok(())
    }
}
