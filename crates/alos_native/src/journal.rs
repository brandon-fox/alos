use pyo3::prelude::*;
use std::fs::OpenOptions;
use std::io::Write;
use std::path::Path;
use std::sync::Mutex;

#[pyclass]
pub struct FastAuditJournalWriter {
    file_path: String,
    lock: Mutex<()>,
}

impl FastAuditJournalWriter {
    pub fn append_raw(&self, record_json: &str) -> std::io::Result<bool> {
        let _guard = self.lock.lock().unwrap_or_else(|e| e.into_inner());
        let mut file = OpenOptions::new()
            .create(true)
            .append(true)
            .open(&self.file_path)?;

        let mut payload = String::with_capacity(record_json.len() + 1);
        payload.push_str(record_json);
        payload.push('\n');
        file.write_all(payload.as_bytes())?;
        Ok(true)
    }
}

#[pymethods]
impl FastAuditJournalWriter {
    #[new]
    pub fn new(file_path: String) -> Self {
        if let Some(parent) = Path::new(&file_path).parent() {
            if !parent.as_os_str().is_empty() {
                let _ = std::fs::create_dir_all(parent);
            }
        }
        FastAuditJournalWriter {
            file_path,
            lock: Mutex::new(()),
        }
    }

    pub fn append_record(&self, record_json: &str) -> PyResult<bool> {
        self.append_raw(record_json)
            .map_err(|e| pyo3::exceptions::PyIOError::new_err(e.to_string()))
    }

    pub fn get_file_path(&self) -> String {
        self.file_path.clone()
    }
}

#[cfg(test)]
mod tests {
    use super::FastAuditJournalWriter;
    use proptest::prelude::*;
    use std::fs;
    use std::sync::Arc;
    use std::thread;
    use tempfile::tempdir;

    #[test]
    fn concurrent_threads_append_intact_jsonl_lines() {
        let dir = tempdir().unwrap();
        let nested = dir.path().join("sub").join("audit.jsonl");
        let writer = Arc::new(FastAuditJournalWriter::new(
            nested.to_str().unwrap().to_string(),
        ));
        assert_eq!(writer.get_file_path(), nested.to_str().unwrap());

        let mut handles = Vec::new();
        for tid in 0..8 {
            let w = Arc::clone(&writer);
            handles.push(thread::spawn(move || {
                for seq in 0..25 {
                    let ok = w
                        .append_raw(&format!("{{\"tid\":{tid},\"seq\":{seq}}}"))
                        .unwrap();
                    assert!(ok);
                }
            }));
        }
        for h in handles {
            h.join().unwrap();
        }
        let lines: Vec<_> = fs::read_to_string(&nested)
            .unwrap()
            .lines()
            .map(str::to_string)
            .collect();
        assert_eq!(lines.len(), 200);
        assert!(lines.iter().all(|l| l.starts_with('{') && l.ends_with('}')));
    }

    proptest! {
        #[test]
        fn journal_writer_preserves_arbitrary_single_line_records(
            records in prop::collection::vec("[^\\r\\n]{0,120}", 1..15)
        ) {
            let dir = tempdir().unwrap();
            let path = dir.path().join("prop.jsonl");
            let writer = FastAuditJournalWriter::new(path.to_str().unwrap().to_string());
            for rec in &records {
                prop_assert!(writer.append_raw(rec).unwrap());
            }
            let content = fs::read_to_string(&path).unwrap();
            let read_back: Vec<&str> = content.split_terminator('\n').collect();
            prop_assert_eq!(read_back, records.iter().map(String::as_str).collect::<Vec<_>>());
        }
    }
}
