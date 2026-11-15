from html import escape

from src.audit_report import DISCLAIMER, build_audit_html, normalize_case_reference


def test_audit_report_has_traceability_disclaimer_and_no_direct_identifiers():
    output = {"ok": True, "probability": .61, "label": 1, "threshold": .5,
              "model": "Logistic Regression", "model_version": "abc123",
              "inputs": {"Glucose": 120, "Insulin": None}, "warnings": ["Insulin not provided"],
              "explanation": {"units": "log-odds", "additivity_error": 1e-8,
                              "contributions": [{"feature": "Glucose", "value": 120,
                                  "contribution": .27, "was_missing": False}]}}
    card = {"model_version": "abc123", "trained_at": "2026-10-20T00:00:00+00:00",
            "dataset": {"canonical_sha256": "cafe"}}
    report = build_audit_html(output, card, "CASE-01")
    assert "CASE-01" in report and "Glucose" in report
    assert "Insulin not provided" in report and "cafe" in report
    assert escape(DISCLAIMER) in report
    assert "email" not in report.lower() and "phone number" not in report.lower()


def test_invalid_prediction_cannot_generate_a_report():
    try:
        build_audit_html({"ok": False}, {})
    except ValueError as exc:
        assert "valid prediction" in str(exc)
    else:
        raise AssertionError("invalid prediction generated an audit report")


def test_non_code_reference_is_omitted_from_report():
    output = {"ok": True, "probability": .5, "label": 1, "threshold": .5,
              "model": "Gaussian Naive Bayes", "model_version": "abc",
              "inputs": {}, "warnings": [], "explanation": {"units": "probability",
                  "additivity_error": 0, "contributions": []}}
    report = build_audit_html(output, {"dataset": {}}, "person@example.com")
    assert "person@example.com" not in report
    assert "Anonymous case" in report


def test_case_reference_accepts_only_anonymized_code_shape():
    assert normalize_case_reference("CASE-014") == "CASE-014"
    assert normalize_case_reference("Person Name") is None
    assert normalize_case_reference("person@example.com") is None
