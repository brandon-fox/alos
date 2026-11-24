use pyo3::prelude::*;
use pyo3::types::PyDict;
use rayon::prelude::*;
use regex::Regex;
use std::collections::HashSet;
use std::fs;
use std::path::Path;
use std::sync::LazyLock;
use walkdir::WalkDir;

static INLINE_TAG_RE: LazyLock<Regex> =
    LazyLock::new(|| Regex::new(r"(?:^|\s)#([a-zA-Z0-9_\-\/]+)").expect("valid inline tag regex"));
static WIKILINK_RE: LazyLock<Regex> =
    LazyLock::new(|| Regex::new(r"\[\[(.*?)\]\]").expect("valid wikilink regex"));

#[pyclass]
#[derive(Clone, Debug, PartialEq, Eq)]
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

#[pymethods]
impl PyObsidianNote {
    #[getter]
    fn frontmatter<'py>(&self, py: Python<'py>) -> PyResult<Bound<'py, PyDict>> {
        let dict = PyDict::new(py);
        if let Ok(serde_yaml::Value::Mapping(map)) =
            serde_yaml::from_str::<serde_yaml::Value>(&self.frontmatter_yaml)
        {
            for (k, v) in map {
                if let Some(key) = k.as_str() {
                    match v {
                        serde_yaml::Value::String(s) => dict.set_item(key, s)?,
                        serde_yaml::Value::Bool(b) => dict.set_item(key, b)?,
                        serde_yaml::Value::Number(n) => {
                            if let Some(i) = n.as_i64() {
                                dict.set_item(key, i)?;
                            } else if let Some(f) = n.as_f64() {
                                dict.set_item(key, f)?;
                            } else {
                                dict.set_item(key, n.to_string())?;
                            }
                        }
                        other => dict.set_item(key, yaml_text(&other))?,
                    }
                }
            }
        }
        Ok(dict)
    }
}

/// Lists, mappings and nulls are handed to Python as their YAML text.
fn yaml_text(value: &serde_yaml::Value) -> String {
    serde_yaml::to_string(value)
        .map(|text| text.trim().to_string())
        .unwrap_or_default()
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

pub fn parse_markdown_text(raw_text: &str, file_name: &str, file_path: &str) -> PyObsidianNote {
    let (frontmatter_yaml, body_text, mut tags) = extract_frontmatter(raw_text);

    for cap in INLINE_TAG_RE.captures_iter(&body_text) {
        if let Some(m) = cap.get(1) {
            let tag = m.as_str().to_string();
            if !tags.contains(&tag) {
                tags.push(tag);
            }
        }
    }

    let mut wiki_links = Vec::new();
    let mut seen_links = HashSet::new();
    for cap in WIKILINK_RE.captures_iter(raw_text) {
        if let Some(m) = cap.get(1) {
            let full_link = m.as_str();
            let base = full_link.split('|').next().unwrap_or("");
            let clean = base.split('#').next().unwrap_or("").trim();
            if !clean.is_empty() && seen_links.insert(clean.to_string()) {
                wiki_links.push(clean.to_string());
            }
        }
    }

    PyObsidianNote {
        file_name: file_name.to_string(),
        file_path: file_path.to_string(),
        content: body_text,
        tags,
        wiki_links,
        frontmatter_yaml,
    }
}

fn parse_single_file(path: &Path) -> Option<PyObsidianNote> {
    let raw_text = fs::read_to_string(path).ok()?;
    let file_name = path.file_name()?.to_str()?.to_string();
    let file_path = path.to_str()?.to_string();
    Some(parse_markdown_text(&raw_text, &file_name, &file_path))
}

fn extract_frontmatter(raw_text: &str) -> (String, String, Vec<String>) {
    let normalized = raw_text.replace("\r\n", "\n");
    let mut tags = Vec::new();
    if let Some(rest) = normalized.strip_prefix("---\n") {
        if let Some(end_idx) = rest.find("\n---") {
            let yaml_str = &rest[..end_idx];
            let after_delim = &rest[end_idx + 4..];
            if after_delim.is_empty() || after_delim.starts_with('\n') {
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
                return (yaml_str.to_string(), after_delim.trim().to_string(), tags);
            }
        }
    }
    (String::new(), normalized, tags)
}

#[cfg(test)]
mod tests {
    use super::{extract_frontmatter, parse_markdown_text, yaml_text, FastVaultParser};
    use proptest::prelude::*;
    use std::fs;
    use tempfile::tempdir;

    #[test]
    fn frontmatter_tags_crlf_and_body_are_split() {
        let (yaml, body, tags) = extract_frontmatter("---\r\ntags: [a, b]\r\n---\r\nBody text\r\n");
        assert_eq!(yaml.trim(), "tags: [a, b]");
        assert_eq!(body, "Body text");
        assert_eq!(tags, vec!["a".to_string(), "b".to_string()]);

        let (_, _, single_tag) = extract_frontmatter("---\ntags: solo\n---\nHello");
        assert_eq!(single_tag, vec!["solo".to_string()]);

        // Non-delimiter "---heading" without newline must remain body text
        let (no_yaml, raw_body, _) = extract_frontmatter("---not_frontmatter\nBody");
        assert!(no_yaml.is_empty());
        assert_eq!(raw_body, "---not_frontmatter\nBody");
    }

    #[test]
    fn inline_tags_wikilinks_and_rayon_parse_all_work() {
        let note = parse_markdown_text(
            "---\ntags: [work]\n---\nSee [[Project Alpha|Alpha]] and [[Note#Sec]] plus [[Project Alpha]] #work #focus/deep",
            "daily.md",
            "/v/daily.md",
        );
        assert_eq!(
            note.tags,
            vec!["work".to_string(), "focus/deep".to_string()]
        );
        assert_eq!(
            note.wiki_links,
            vec!["Project Alpha".to_string(), "Note".to_string()]
        );
        assert_eq!(yaml_text(&serde_yaml::Value::Sequence(vec![])), "[]");

        let dir = tempdir().unwrap();
        for idx in 0..8 {
            let p = dir.path().join(format!("n{idx}.md"));
            fs::write(&p, format!("---\ntags: [t{idx}]\n---\nLink [[n0]] #extra")).unwrap();
        }
        fs::write(dir.path().join("ignore.txt"), "not markdown").unwrap();

        let parser = FastVaultParser::new(dir.path().to_str().unwrap().to_string());
        let all = parser.parse_all().unwrap();
        assert_eq!(all.len(), 8);

        let single = parser
            .parse_file(dir.path().join("n0.md").to_str().unwrap().to_string())
            .unwrap();
        assert_eq!(single.file_name, "n0.md");

        let missing_dir = FastVaultParser::new(dir.path().join("nope").to_str().unwrap().into());
        assert!(missing_dir.parse_all().unwrap().is_empty());
    }

    proptest! {
        #[test]
        fn vault_parser_never_panics_and_deduplicates_tags_and_links(
            raw in "[\\PC\\r\\n]{0,200}"
        ) {
            let note = parse_markdown_text(&raw, "prop.md", "/prop.md");
            let unique_tags: std::collections::HashSet<_> = note.tags.iter().collect();
            let unique_links: std::collections::HashSet<_> = note.wiki_links.iter().collect();
            prop_assert_eq!(unique_tags.len(), note.tags.len());
            prop_assert_eq!(unique_links.len(), note.wiki_links.len());
            for link in &note.wiki_links {
                prop_assert!(!link.is_empty());
                prop_assert!(!link.contains('|') && !link.contains('#'));
            }
        }
    }
}
