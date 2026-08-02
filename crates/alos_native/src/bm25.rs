use pyo3::prelude::*;
use pyo3::types::PyDict;
use std::collections::HashMap;

#[derive(Clone)]
pub struct DocumentChunk {
    pub header: String,
    pub file_name: String,
    pub file_path: String,
    pub source_type: String,
    pub content: String,
    pub tokens: Vec<String>,
}

#[pyclass]
pub struct FastBM25Indexer {
    chunks: Vec<DocumentChunk>,
    k1: f64,
    b: f64,
}

#[pymethods]
impl FastBM25Indexer {
    #[new]
    #[pyo3(signature = (k1=1.5, b=0.75))]
    pub fn new(k1: f64, b: f64) -> Self {
        FastBM25Indexer {
            chunks: Vec::new(),
            k1,
            b,
        }
    }

    pub fn add_chunk(
        &mut self,
        header: String,
        file_name: String,
        file_path: String,
        source_type: String,
        content: String,
    ) {
        let text_to_tokenize = format!("{} {} {} {}", header, header, header, content);
        let tokens: Vec<String> = text_to_tokenize
            .split_whitespace()
            .map(|s| s.to_lowercase())
            .collect();

        self.chunks.push(DocumentChunk {
            header,
            file_name,
            file_path,
            source_type,
            content,
            tokens,
        });
    }

    pub fn clear(&mut self) {
        self.chunks.clear();
    }

    pub fn search<'py>(
        &self,
        py: Python<'py>,
        query: String,
        top_k: usize,
        source_filter: Option<String>,
    ) -> PyResult<Vec<&'py PyDict>> {
        let filtered_indices: Vec<usize> = self
            .chunks
            .iter()
            .enumerate()
            .filter(|(_, c)| {
                if let Some(ref sf) = source_filter {
                    &c.source_type == sf
                } else {
                    true
                }
            })
            .map(|(idx, _)| idx)
            .collect();

        if filtered_indices.is_empty() {
            return Ok(Vec::new());
        }

        let query_tokens: Vec<String> =
            query.split_whitespace().map(|s| s.to_lowercase()).collect();

        if query_tokens.is_empty() {
            let mut results = Vec::new();
            for &idx in filtered_indices.iter().take(top_k) {
                let chunk = &self.chunks[idx];
                let dict = PyDict::new(py);
                dict.set_item("header", &chunk.header)?;
                dict.set_item("file_name", &chunk.file_name)?;
                dict.set_item("file_path", &chunk.file_path)?;
                dict.set_item("source_type", &chunk.source_type)?;
                dict.set_item("content", &chunk.content)?;
                dict.set_item("score", 0.0f64)?;
                results.push(dict);
            }
            return Ok(results);
        }

        let n_docs = filtered_indices.len() as f64;
        let mut doc_freqs: HashMap<&str, usize> = HashMap::new();
        let mut total_len = 0usize;

        for &idx in &filtered_indices {
            let chunk = &self.chunks[idx];
            total_len += chunk.tokens.len();
            let unique_tokens: std::collections::HashSet<&str> =
                chunk.tokens.iter().map(|s| s.as_str()).collect();
            for token in unique_tokens {
                *doc_freqs.entry(token).or_insert(0) += 1;
            }
        }

        let avg_dl = if n_docs > 0.0 {
            total_len as f64 / n_docs
        } else {
            1.0
        };

        // Score filtered chunks
        let mut scored_chunks: Vec<(usize, f64)> = Vec::new();

        for &idx in &filtered_indices {
            let chunk = &self.chunks[idx];
            let doc_len = chunk.tokens.len() as f64;
            let mut tf_map: HashMap<&str, usize> = HashMap::new();
            for token in &chunk.tokens {
                *tf_map.entry(token.as_str()).or_insert(0) += 1;
            }

            let mut score = 0.0f64;
            for q_term in &query_tokens {
                if let Some(&tf) = tf_map.get(q_term.as_str()) {
                    let df = *doc_freqs.get(q_term.as_str()).unwrap_or(&0) as f64;
                    let idf = ((n_docs - df + 0.5) / (df + 0.5) + 1.0).ln();
                    let tf_f = tf as f64;
                    let num = tf_f * (self.k1 + 1.0);
                    let den = tf_f + self.k1 * (1.0 - self.b + self.b * (doc_len / avg_dl));
                    score += idf * (num / den);
                }
            }

            if score > 0.0 {
                scored_chunks.push((idx, score));
            }
        }

        scored_chunks.sort_by(|a, b| b.1.partial_cmp(&a.1).unwrap_or(std::cmp::Ordering::Equal));

        let mut results = Vec::new();
        for &(idx, score) in scored_chunks.iter().take(top_k) {
            let chunk = &self.chunks[idx];
            let dict = PyDict::new(py);
            dict.set_item("header", &chunk.header)?;
            dict.set_item("file_name", &chunk.file_name)?;
            dict.set_item("file_path", &chunk.file_path)?;
            dict.set_item("source_type", &chunk.source_type)?;
            dict.set_item("content", &chunk.content)?;
            dict.set_item("score", score)?;
            results.push(dict);
        }

        Ok(results)
    }
}
