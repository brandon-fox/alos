use pyo3::prelude::*;
use pyo3::types::PyDict;
use std::collections::{HashMap, HashSet};

#[derive(Clone, Debug, PartialEq)]
pub struct DocumentChunk {
    pub header: String,
    pub file_name: String,
    pub file_path: String,
    pub source_type: String,
    pub content: String,
    pub tokens: Vec<String>,
}

#[derive(Clone, Debug, PartialEq)]
pub struct ScoredChunk {
    pub header: String,
    pub file_name: String,
    pub file_path: String,
    pub source_type: String,
    pub content: String,
    pub score: f64,
}

#[pyclass]
pub struct FastBM25Indexer {
    chunks: Vec<DocumentChunk>,
    k1: f64,
    b: f64,
}

impl FastBM25Indexer {
    pub fn search_raw(
        &self,
        query: &str,
        top_k: usize,
        source_filter: Option<&str>,
    ) -> Vec<ScoredChunk> {
        if top_k == 0 {
            return Vec::new();
        }
        let filtered_indices: Vec<usize> = self
            .chunks
            .iter()
            .enumerate()
            .filter(|(_, c)| source_filter.is_none_or(|sf| c.source_type == sf))
            .map(|(idx, _)| idx)
            .collect();

        if filtered_indices.is_empty() {
            return Vec::new();
        }

        let query_tokens: Vec<String> =
            query.split_whitespace().map(|s| s.to_lowercase()).collect();

        if query_tokens.is_empty() {
            return filtered_indices
                .into_iter()
                .take(top_k)
                .map(|idx| {
                    let c = &self.chunks[idx];
                    ScoredChunk {
                        header: c.header.clone(),
                        file_name: c.file_name.clone(),
                        file_path: c.file_path.clone(),
                        source_type: c.source_type.clone(),
                        content: c.content.clone(),
                        score: 0.0,
                    }
                })
                .collect();
        }

        let n_docs = filtered_indices.len() as f64;
        let mut doc_freqs: HashMap<&str, usize> = HashMap::new();
        let mut total_len = 0usize;

        for &idx in &filtered_indices {
            let chunk = &self.chunks[idx];
            total_len += chunk.tokens.len();
            let unique_tokens: HashSet<&str> = chunk.tokens.iter().map(|s| s.as_str()).collect();
            for token in unique_tokens {
                *doc_freqs.entry(token).or_insert(0) += 1;
            }
        }

        if total_len == 0 {
            return Vec::new();
        }
        let avg_dl = total_len as f64 / n_docs;

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
        scored_chunks
            .into_iter()
            .take(top_k)
            .map(|(idx, score)| {
                let c = &self.chunks[idx];
                ScoredChunk {
                    header: c.header.clone(),
                    file_name: c.file_name.clone(),
                    file_path: c.file_path.clone(),
                    source_type: c.source_type.clone(),
                    content: c.content.clone(),
                    score,
                }
            })
            .collect()
    }
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
        let text_to_tokenize = format!("{header} {header} {header} {content}");
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

    #[pyo3(signature = (query, top_k=5, source_filter=None))]
    pub fn search<'py>(
        &self,
        py: Python<'py>,
        query: String,
        top_k: usize,
        source_filter: Option<String>,
    ) -> PyResult<Vec<Bound<'py, PyDict>>> {
        let hits = self.search_raw(&query, top_k, source_filter.as_deref());
        let mut results = Vec::with_capacity(hits.len());
        for hit in hits {
            let dict = PyDict::new(py);
            dict.set_item("header", &hit.header)?;
            dict.set_item("file_name", &hit.file_name)?;
            dict.set_item("file_path", &hit.file_path)?;
            dict.set_item("source_type", &hit.source_type)?;
            dict.set_item("content", &hit.content)?;
            dict.set_item("score", hit.score)?;
            results.push(dict);
        }
        Ok(results)
    }
}

#[cfg(test)]
mod tests {
    use super::FastBM25Indexer;
    use proptest::prelude::*;

    #[test]
    fn header_boost_and_term_frequency_rank_higher() {
        let mut idx = FastBM25Indexer::new(1.5, 0.75);
        idx.add_chunk(
            "Safety Matrix".into(),
            "a.md".into(),
            "/a.md".into(),
            "spec".into(),
            "general text".into(),
        );
        idx.add_chunk(
            "Other".into(),
            "b.md".into(),
            "/b.md".into(),
            "spec".into(),
            "safety mentioned once in a much longer document body with extra padding words".into(),
        );
        idx.add_chunk(
            "Unrelated".into(),
            "c.md".into(),
            "/c.md".into(),
            "vault".into(),
            "calendar notes".into(),
        );

        let hits = idx.search_raw("safety", 5, None);
        assert_eq!(hits.len(), 2);
        assert_eq!(hits[0].file_name, "a.md");
        assert!(hits[0].score > hits[1].score);
        assert!(hits[1].score > 0.0);

        let filtered = idx.search_raw("calendar", 5, Some("vault"));
        assert_eq!(filtered.len(), 1);
        assert_eq!(filtered[0].file_name, "c.md");

        let top_one = idx.search_raw("safety", 1, None);
        assert_eq!(top_one.len(), 1);
        assert_eq!(idx.search_raw("safety", 0, None).len(), 0);
    }

    #[test]
    fn empty_query_and_clear_behave_deterministically() {
        let mut idx = FastBM25Indexer::new(1.5, 0.75);
        assert!(idx.search_raw("anything", 5, None).is_empty());

        idx.add_chunk(
            "   ".into(),
            "empty.md".into(),
            "/e.md".into(),
            "spec".into(),
            "   ".into(),
        );
        assert!(idx.search_raw("missing", 5, None).is_empty());

        let blank_q = idx.search_raw("   ", 5, Some("spec"));
        assert_eq!(blank_q.len(), 1);
        assert_eq!(blank_q[0].score, 0.0);

        idx.clear();
        assert!(idx.search_raw("   ", 5, None).is_empty());
    }

    #[test]
    fn length_normalization_b_parameter_affects_score() {
        let mut idx_b0 = FastBM25Indexer::new(1.5, 0.0);
        let mut idx_b1 = FastBM25Indexer::new(1.5, 1.0);
        for idx in [&mut idx_b0, &mut idx_b1] {
            idx.add_chunk(
                "H".into(),
                "short.md".into(),
                "/s".into(),
                "spec".into(),
                "alpha".into(),
            );
            idx.add_chunk(
                "H".into(),
                "long.md".into(),
                "/l".into(),
                "spec".into(),
                "alpha pad pad pad pad pad pad pad pad pad pad".into(),
            );
        }
        let r0 = idx_b0.search_raw("alpha", 2, None);
        let r1 = idx_b1.search_raw("alpha", 2, None);
        assert!((r0[0].score - r0[1].score).abs() < 1e-9);
        assert!(r1[0].score > r1[1].score);
    }

    #[test]
    fn exact_okapi_bm25_closed_form_values_match_reference() {
        let mut idx = FastBM25Indexer::new(1.5, 0.75);
        idx.add_chunk(
            "h".into(),
            "d0.md".into(),
            "/d0".into(),
            "spec".into(),
            "alpha alpha beta".into(),
        );
        idx.add_chunk(
            "g".into(),
            "d1.md".into(),
            "/d1".into(),
            "spec".into(),
            "alpha gamma delta epsilon".into(),
        );
        idx.add_chunk(
            "z".into(),
            "d2.md".into(),
            "/d2".into(),
            "spec".into(),
            "omega".into(),
        );

        let hits = idx.search_raw("alpha beta", 5, None);
        assert_eq!(hits.len(), 2);

        let avg_dl = 17.0_f64 / 3.0_f64;
        let idf_alpha = ((3.0_f64 - 2.0 + 0.5) / (2.0 + 0.5) + 1.0).ln();
        let idf_beta = ((3.0_f64 - 1.0 + 0.5) / (1.0 + 0.5) + 1.0).ln();

        let den_a0 = 2.0 + 1.5 * (1.0 - 0.75 + 0.75 * (6.0 / avg_dl));
        let den_b0 = 1.0 + 1.5 * (1.0 - 0.75 + 0.75 * (6.0 / avg_dl));
        let expected_0 = idf_alpha * ((2.0 * 2.5) / den_a0) + idf_beta * ((1.0 * 2.5) / den_b0);

        let den_a1 = 1.0 + 1.5 * (1.0 - 0.75 + 0.75 * (7.0 / avg_dl));
        let expected_1 = idf_alpha * ((1.0 * 2.5) / den_a1);

        assert!((hits[0].score - expected_0).abs() < 1e-12);
        assert!((hits[1].score - expected_1).abs() < 1e-12);
    }

    proptest! {
        #[test]
        fn bm25_never_panics_and_scores_are_finite_sorted(
            docs in prop::collection::vec(("[\\PC]{0,40}", "[\\PC]{0,80}", prop_oneof!["spec", "vault"]), 0..12),
            query in "[\\PC]{0,40}",
            top_k in 0usize..10,
        ) {
            let mut idx = FastBM25Indexer::new(1.5, 0.75);
            for (i, (hdr, body, st)) in docs.iter().enumerate() {
                idx.add_chunk(hdr.clone(), format!("f{i}.md"), format!("/f{i}.md"), st.clone(), body.clone());
            }
            let res = idx.search_raw(&query, top_k, None);
            prop_assert!(res.len() <= top_k);
            for pair in res.windows(2) {
                prop_assert!(pair[0].score >= pair[1].score);
            }
            for item in &res {
                prop_assert!(item.score.is_finite() && item.score >= 0.0);
            }
        }
    }
}
