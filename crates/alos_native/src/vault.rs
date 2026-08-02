use pyo3::prelude::*;
use pyo3::types::PyDict;
use rayon::prelude::*;
use regex::Regex;
use std::collections::HashSet;
use std::fs;
use std::path::Path;
use walkdir::WalkDir;

#[pyclass]
#[derive(Clone)]
pub struct PyObsidianNote {
    #[pyo3(get)]
    pub file_name: String,
    #[pyo3(get)]
    pub file_path: String,
    #[pyo3(get)]
    pub content: String,
    #[pyo3(get)]
    pub tags: Vec<String>,
    #[pyo3(get)]
    pub wiki_links: Vec<String>,
    pub frontmatter_yaml: String,
}

use pyo3::IntoPyObjectExt;

#[pymethods]
impl PyObsidianNote {
    #[getter]
    fn frontmatter<'py>(&self, py: Python<'py>) -> PyResult<Bound<'py, PyDict>> {
        let dict = PyDict::new(py);
        if let Ok(val) = serde_yaml::from_str::<serde_yaml::Value>(&self.frontmatter_yaml) {
            if let serde_yaml::Value::Mapping(map) = val {
                for (k, v) in map {
                    if let Some(k_str) = k.as_str() {
                        let py_val = match v {
                            serde_yaml::Value::String(s) => s.into_py_any(py)?,
                            serde_yaml::Value::Number(n) => {
                                if let Some(i) = n.as_i64() {
                                    i.into_py_any(py)?
                                } else if let Some(f) = n.as_f64() {
                                    f.into_py_any(py)?
                                } else {
                                    n.to_string().into_py_any(py)?
                                }
                            }
                            serde_yaml::Value::Bool(b) => b.into_py_any(py)?,
                            _ => v.to_string().into_py_any(py)?,
                        };
                        let _ = dict.set_item(k_str, py_val);
                    }
                }
            }
        }
        Ok(dict)
    }
}

#[pyclass]
pub struct FastVaultParser {
    vault_dir: String,
}

#[pymethods]
impl FastVaultParser {
    #[new]
    pub fn new(vault_dir: String) -> Self {
        FastVaultParser { vault_dir }
    }

    pub fn parse_file(&self, file_path: String) -> PyResult<PyObsidianNote> {
        parse_single_file(Path::new(&file_path))
            .ok_or_else(|| PyErr::new::<pyo3::exceptions::PyValueError, _>("Failed to parse note"))
    }

    pub fn parse_all(&self) -> PyResult<Vec<PyObsidianNote>> {
        let path = Path::new(&self.vault_dir);
        if !path.exists() {
            return Ok(Vec::new());
        }

        let entries: Vec<_> = WalkDir::new(path)
            .into_iter()
            .filter_map(|e| e.ok())
            .filter(|e| e.path().extension().and_then(|s| s.to_str()) == Some("md"))
            .map(|e| e.path().to_path_buf())
            .collect();

        let notes: Vec<PyObsidianNote> = entries
            .par_iter()
            .filter_map(|p| parse_single_file(p))
            .collect();

        Ok(notes)
    }
}

fn parse_single_file(path: &Path) -> Option<PyObsidianNote> {
    let raw_text = fs::read_to_string(path).ok()?;
    let file_name = path.file_name()?.to_str()?.to_string();
    let file_path = path.to_str()?.to_string();

    let (frontmatter_yaml, body_text, mut tags) = extract_frontmatter(&raw_text);

    // Extract inline #tags from body
    let inline_tag_re = Regex::new(r"(?:^|\s)#([a-zA-Z0-9_\-\/]+)").ok()?;
    for cap in inline_tag_re.captures_iter(&body_text) {
        if let Some(m) = cap.get(1) {
            let tag = m.as_str().to_string();
            if !tags.contains(&tag) {
                tags.push(tag);
            }
        }
    }

    // Extract [[WikiLinks]]
    let wikilink_re = Regex::new(r"\[\[(.*?)\]\]").ok()?;
    let mut wiki_links = Vec::new();
    let mut seen_links = HashSet::new();

    for cap in wikilink_re.captures_iter(&raw_text) {
        if let Some(m) = cap.get(1) {
            let full_link = m.as_str();
            let clean = full_link.split('|').next()?.split('#').next()?.trim();
            if !clean.is_empty() && seen_links.insert(clean.to_string()) {
                wiki_links.push(clean.to_string());
            }
        }
    }

    Some(PyObsidianNote {
        file_name,
        file_path,
        content: body_text,
        tags,
        wiki_links,
        frontmatter_yaml,
    })
}

fn extract_frontmatter(raw_text: &str) -> (String, String, Vec<String>) {
    let mut tags = Vec::new();
    if raw_text.starts_with("---") {
        if let Some(end_idx) = raw_text[3..].find("\n---") {
            let yaml_str = &raw_text[3..3 + end_idx];
            let body = &raw_text[3 + end_idx + 4..];

            if let Ok(val) = serde_yaml::from_str::<serde_yaml::Value>(yaml_str) {
                if let Some(t_val) = val.get("tags") {
                    match t_val {
                        serde_yaml::Value::Sequence(seq) => {
                            for item in seq {
                                if let Some(s) = item.as_str() {
                                    tags.push(s.to_string());
                                }
                            }
                        }
                        serde_yaml::Value::String(s) => {
                            tags.push(s.clone());
                        }
                        _ => {}
                    }
                }
            }
            return (yaml_str.to_string(), body.trim().to_string(), tags);
        }
    }
    (String::new(), raw_text.to_string(), tags)
}
