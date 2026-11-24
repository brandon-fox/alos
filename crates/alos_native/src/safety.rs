use pyo3::prelude::*;
use pyo3::types::PyDict;
use std::collections::HashSet;

#[derive(Debug, PartialEq, Eq)]
pub struct ValidationOutcome {
    pub valid: bool,
    pub critique: String,
    pub checked: Vec<String>,
}

#[pyclass]
pub struct FastSafetyEvaluator {
    high_actions: HashSet<String>,
    medium_actions: HashSet<String>,
}

impl FastSafetyEvaluator {
    pub fn validate_calendar_raw(
        &self,
        action_type: &str,
        start_time: &str,
        preferences: &[String],
    ) -> ValidationOutcome {
        let mut preferences_checked = Vec::new();
        if action_type == "google_calendar_create_event" {
            for pref in preferences {
                if pref.contains("No meetings scheduled after 5:00 PM") {
                    preferences_checked.push(pref.clone());
                    let after_5pm = ["T17:", "T18:", "T19:", "T20:", "T21:", "T22:", "T23:"]
                        .iter()
                        .any(|&h| start_time.contains(h));
                    if after_5pm {
                        return ValidationOutcome {
                            valid: false,
                            critique: "Violates preference: No meetings scheduled after 5:00 PM"
                                .to_string(),
                            checked: preferences_checked,
                        };
                    }
                }
            }
        }
        ValidationOutcome {
            valid: true,
            critique: "VALID".to_string(),
            checked: preferences_checked,
        }
    }

    pub fn validate_corrections_raw(
        &self,
        query: &str,
        corrections: &[String],
    ) -> ValidationOutcome {
        let mut corrections_checked = Vec::new();
        let query_lower = query.to_lowercase();

        for corr in corrections {
            corrections_checked.push(corr.clone());
            if corr.contains("Delta")
                && query_lower.contains("flight")
                && !query_lower.contains("delta")
            {
                return ValidationOutcome {
                    valid: false,
                    critique: format!("Violates historical correction: {corr}"),
                    checked: corrections_checked,
                };
            }
        }
        ValidationOutcome {
            valid: true,
            critique: "VALID".to_string(),
            checked: corrections_checked,
        }
    }
}

#[pymethods]
impl FastSafetyEvaluator {
    #[new]
    pub fn new() -> Self {
        let high_actions = HashSet::from([
            "email_send".to_string(),
            "calendar_delete".to_string(),
            "financial_transaction".to_string(),
            "email_create_draft".to_string(),
        ]);
        let medium_actions = HashSet::from([
            "todoist_create_task".to_string(),
            "google_calendar_create_event".to_string(),
            "vault_update_note".to_string(),
        ]);
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
        "HIGH".to_string()
    }

    pub fn validate_calendar_preferences<'py>(
        &self,
        py: Python<'py>,
        action_type: &str,
        start_time: &str,
        preferences: Vec<String>,
    ) -> PyResult<Bound<'py, PyDict>> {
        let out = self.validate_calendar_raw(action_type, start_time, &preferences);
        let result = PyDict::new(py);
        result.set_item("valid", out.valid)?;
        result.set_item("critique", out.critique)?;
        result.set_item("preferences_checked", out.checked)?;
        Ok(result)
    }

    pub fn validate_corrections<'py>(
        &self,
        py: Python<'py>,
        query: &str,
        corrections: Vec<String>,
    ) -> PyResult<Bound<'py, PyDict>> {
        let out = self.validate_corrections_raw(query, &corrections);
        let result = PyDict::new(py);
        result.set_item("valid", out.valid)?;
        result.set_item("critique", out.critique)?;
        result.set_item("corrections_checked", out.checked)?;
        Ok(result)
    }
}

impl Default for FastSafetyEvaluator {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::FastSafetyEvaluator;
    use proptest::prelude::*;

    #[test]
    fn risk_matrix_and_fail_safe_default_are_exact() {
        let ev = FastSafetyEvaluator::default();
        assert_eq!(ev.classify_risk("web_search"), "LOW");
        for med in [
            "todoist_create_task",
            "google_calendar_create_event",
            "vault_update_note",
        ] {
            assert_eq!(ev.classify_risk(med), "MEDIUM");
        }
        for high in [
            "email_send",
            "calendar_delete",
            "financial_transaction",
            "email_create_draft",
            "unknown_custom_action",
            "",
        ] {
            assert_eq!(ev.classify_risk(high), "HIGH");
        }
    }

    #[test]
    fn calendar_and_corrections_validation_cover_every_hour_and_branch() {
        let ev = FastSafetyEvaluator::new();
        let prefs = vec!["No meetings scheduled after 5:00 PM".to_string()];

        for hour in 17..=23 {
            let ts = format!("2026-11-23T{hour:02}:15:00");
            let bad = ev.validate_calendar_raw("google_calendar_create_event", &ts, &prefs);
            assert!(!bad.valid);
            assert!(bad.critique.contains("Violates preference"));
            assert_eq!(bad.checked, prefs);
        }
        let ok_morning = ev.validate_calendar_raw(
            "google_calendar_create_event",
            "2026-11-23T16:30:00",
            &prefs,
        );
        assert!(ok_morning.valid);
        assert_eq!(ok_morning.critique, "VALID");

        let ignored_action =
            ev.validate_calendar_raw("todoist_create_task", "2026-11-23T20:00:00", &prefs);
        assert!(ignored_action.valid);
        assert!(ignored_action.checked.is_empty());

        let corrs = vec!["Always check Delta first".to_string()];
        let bad_flight = ev.validate_corrections_raw("Book a flight to SFO", &corrs);
        assert!(!bad_flight.valid);
        assert!(bad_flight
            .critique
            .contains("Violates historical correction"));

        let ok_delta = ev.validate_corrections_raw("Book a Delta flight to SFO", &corrs);
        assert!(ok_delta.valid);
        let ok_hotel = ev.validate_corrections_raw("Book a hotel in SFO", &corrs);
        assert!(ok_hotel.valid);
    }

    proptest! {
        #[test]
        fn safety_evaluator_never_panics_and_unknown_actions_default_high(
            action in "[\\PC]{0,40}",
            time_str in "[\\PC]{0,40}",
            query in "[\\PC]{0,60}",
            prefs in prop::collection::vec("[\\PC]{0,50}", 0..5),
        ) {
            let ev = FastSafetyEvaluator::new();
            let tier = ev.classify_risk(&action);
            prop_assert!(matches!(tier.as_str(), "LOW" | "MEDIUM" | "HIGH"));
            if action != "web_search"
                && action != "todoist_create_task"
                && action != "google_calendar_create_event"
                && action != "vault_update_note"
            {
                prop_assert_eq!(tier, "HIGH");
            }
            let _ = ev.validate_calendar_raw(&action, &time_str, &prefs);
            let _ = ev.validate_corrections_raw(&query, &prefs);
        }
    }
}
