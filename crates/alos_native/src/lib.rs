mod bm25;
mod graph;
mod vault;

use bm25::FastBM25Indexer;
use graph::FastGraphEngine;
use pyo3::prelude::*;
use vault::{FastVaultParser, PyObsidianNote};

#[pymodule]
fn alos_native(_py: Python, m: &PyModule) -> PyResult<()> {
    m.add_class::<FastVaultParser>()?;
    m.add_class::<PyObsidianNote>()?;
    m.add_class::<FastBM25Indexer>()?;
    m.add_class::<FastGraphEngine>()?;
    Ok(())
}
