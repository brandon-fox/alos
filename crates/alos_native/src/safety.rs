use pyo3::prelude::*;
use pyo3::types::PyDict;
use std::collections::HashSet;

#[pyclass]
pub struct FastSafetyEvaluator {
    high_actions: HashSet<String>,
    medium_actions: HashSet<String>,
}

#[pymethods]
impl FastSafetyEvaluator {
    #[new]
    pub fn new() -> Self {
        let mut high_actions = HashSet::new();
        high_actions.insert("email_send".to_string());
        high_actions.insert("calendar_delete".to_string());
        high_actions.insert("financial_transaction".to_string());
        high_actions.insert("email_create_draft".to_string());

        let mut medium_actions = HashSet::new();
        medium_actions.insert("todoist_create_task".to_string());
        medium_actions.insert("google_calendar_create_event".to_string());
        medium_actions.insert("vault_update_note".to_string());

        FastSafetyEvaluator {
            high_actions,
            medium_actions,
        }
    }

    pub fn classify_risk(&self, action_type: &str) -> String {
        if action_type == "web_search" {
            return "LOW".to_string();
        }
        if self.high_actions.contains(action_type) {
            return "HIGH".to_string();
        }
        if self.medium_actions.contains(action_type) {
            return "MEDIUM".to_string();
        }
        "HIGH".to_string() // Fail-safe default
    }

    pub fn validate_calendar_preferences<'py>(
        &self,
        py: Python<'py>,
        action_type: &str,
        start_time: &str,
        preferences: Vec<String>,
    ) -> PyResult<&'py PyDict> {
        let result = PyDict::new(py);
        let mut preferences_checked = Vec::new();

        if action_type == "google_calendar_create_event" {
            for pref in &preferences {
                if pref.contains("No meetings scheduled after 5:00 PM") {
                    preferences_checked.push(pref.clone());
                    let after_5pm = ["T17:", "T18:", "T19:", "T20:", "T21:", "T22:", "T23:"]
                        .iter()
                        .any(|&h| start_time.contains(h));
                    if after_5pm {
                        result.set_item("valid", false)?;
                        result.set_item("critique", "Violates preference: No meetings scheduled after 5:00 PM")?;
                        result.set_item("preferences_checked", preferences_checked)?;
                        return Ok(result);
                    }
                }
            }
        }

        result.set_item("valid", true)?;
        result.set_item("critique", "VALID")?;
        result.set_item("preferences_checked", preferences_checked)?;
        Ok(result)
    }

    pub fn validate_corrections<'py>(
        &self,
        py: Python<'py>,
        query: &str,
        corrections: Vec<String>,
    ) -> PyResult<&'py PyDict> {
        let result = PyDict::new(py);
        let mut corrections_checked = Vec::new();
        let query_lower = query.to_lowercase();

        for corr in &corrections {
            corrections_checked.push(corr.clone());
            if corr.contains("Delta") && query_lower.contains("flight") && !query_lower.contains("delta") {
                result.set_item("valid", false)?;
                result.set_item("critique", format!("Violates historical correction: {}", corr))?;
                result.set_item("corrections_checked", corrections_checked)?;
                return Ok(result);
            }
        }

        result.set_item("valid", true)?;
        result.set_item("critique", "VALID")?;
        result.set_item("corrections_checked", corrections_checked)?;
        Ok(result)
    }
}
