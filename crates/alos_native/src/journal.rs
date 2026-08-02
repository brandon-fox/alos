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

#[pymethods]
impl FastAuditJournalWriter {
    #[new]
    pub fn new(file_path: String) -> Self {
        if let Some(parent) = Path::new(&file_path).parent() {
            let _ = std::fs::create_dir_all(parent);
        }
        FastAuditJournalWriter {
            file_path,
            lock: Mutex::new(()),
        }
    }

    pub fn append_record(&self, record_json: &str) -> PyResult<bool> {
        let _guard = self.lock.lock().unwrap();
        let mut file = OpenOptions::new()
            .create(true)
            .append(true)
            .open(&self.file_path)
            .map_err(|e| pyo3::exceptions::PyIOError::new_err(e.to_string()))?;

        writeln!(file, "{}", record_json)
            .map_err(|e| pyo3::exceptions::PyIOError::new_err(e.to_string()))?;

        Ok(true)
    }

    pub fn get_file_path(&self) -> String {
        self.file_path.clone()
    }
}
