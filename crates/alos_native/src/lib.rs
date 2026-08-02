mod bm25;
mod graph;
mod journal;
mod safety;
mod vault;

use bm25::FastBM25Indexer;
use graph::FastGraphEngine;
use journal::FastAuditJournalWriter;
use pyo3::prelude::*;
use safety::FastSafetyEvaluator;
use vault::{FastVaultParser, PyObsidianNote};

#[pymodule]
fn alos_native(_py: Python<'_>, m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_class::<FastVaultParser>()?;
    m.add_class::<PyObsidianNote>()?;
    m.add_class::<FastBM25Indexer>()?;
    m.add_class::<FastGraphEngine>()?;
    m.add_class::<FastSafetyEvaluator>()?;
    m.add_class::<FastAuditJournalWriter>()?;
    Ok(())
}
