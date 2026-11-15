import asyncio
import json

import httpx
from fastapi.testclient import TestClient

from backend import main


client = TestClient(main.app)
GOOD = {
    "Pregnancies": 2, "Glucose": 120, "BloodPressure": 70, "SkinThickness": 25,
    "Insulin": 100, "BMI": 30, "DiabetesPedigreeFunction": 0.4, "Age": 33,
}


def test_health_liveness_is_available():
    assert client.get("/health/live").json() == {"status": "ok"}


def test_private_history_rejects_anonymous_request():
    response = client.get("/api/v1/history")
    assert response.status_code == 401
    assert "stack" not in response.text.lower()


def test_prediction_schema_rejects_unknown_fields():
    response = client.post("/api/v1/predictions", json={**GOOD, "Outcome": 1})
    assert response.status_code == 422
    assert '"input":' not in response.text.lower()


def test_report_upload_requires_authentication():
    response = client.post("/api/v1/reports/extract", files={"file": ("lab.pdf", b"%PDF-1.4", "application/pdf")})
    assert response.status_code == 401


def test_report_upload_rejects_unsupported_media_type_for_signed_in_user():
    async def signed_in_user():
        return {"id": "authenticated-test-user"}
    main.app.dependency_overrides[main.current_user] = signed_in_user
    try:
        response = client.post("/api/v1/reports/extract", files={"file": ("lab.txt", b"glucose 110", "text/plain")})
        assert response.status_code == 415
    finally:
        main.app.dependency_overrides.clear()


def test_authenticated_text_pdf_upload_returns_reviewable_observations():
    import fitz
    document = fitz.open()
    document.new_page().insert_text((72, 72), "HbA1c 6.1 %\nFasting glucose 110 mg/dL\nBMI 28.0 kg/m2")
    payload = document.tobytes()
    async def signed_in_user():
        return {"id": "authenticated-test-user"}
    main.app.dependency_overrides[main.current_user] = signed_in_user
    try:
        response = client.post("/api/v1/reports/extract", files={"file": ("private-health-report.pdf", payload, "application/pdf")})
        assert response.status_code == 200, response.text
        result = response.json()
        assert result["retained"] is False
        observations = {item["name"]: item for item in result["observations"]}
        assert observations["HbA1c"]["suggested_model_feature"] is None
        assert observations["Glucose"]["suggested_model_feature"] is None
        assert observations["BMI"]["suggested_model_feature"] == "BMI"
        assert result["source_name"] == "private-health-report.pdf"
    finally:
        main.app.dependency_overrides.clear()


def test_authenticated_report_upload_rejects_corrupt_and_unreadable_reports():
    import fitz
    async def signed_in_user():
        return {"id": "authenticated-test-user"}
    main.app.dependency_overrides[main.current_user] = signed_in_user
    try:
        corrupt = client.post("/api/v1/reports/extract", files={
            "file": ("corrupt.pdf", b"not a PDF", "application/pdf")})
        assert corrupt.status_code == 422
        assert "valid PDF" in corrupt.json()["detail"]

        blank = fitz.open()
        blank.new_page()
        unreadable = client.post("/api/v1/reports/extract", files={
            "file": ("blank-scan.pdf", blank.tobytes(), "application/pdf")})
        assert unreadable.status_code == 422
        assert any(word in unreadable.json()["detail"].lower() for word in ("ocr", "readable text", "read"))
    finally:
        main.app.dependency_overrides.clear()


def test_authenticated_synthetic_report_can_be_reviewed_corrected_and_used_for_estimate():
    import fitz
    document = fitz.open()
    document.new_page().insert_text((72, 72), "2-hour OGTT glucose 178 mg/dL\nBMI 28.0 kg/m2\nHbA1c 6.1 %")
    async def signed_in_user():
        return {"id": "authenticated-test-user"}
    main.app.dependency_overrides[main.current_user] = signed_in_user
    try:
        extracted = client.post("/api/v1/reports/extract", files={
            "file": ("synthetic-lab-report.pdf", document.tobytes(), "application/pdf")})
        assert extracted.status_code == 200, extracted.text
        report = extracted.json()
        assert report["retained"] is False
        findings = {item["name"]: item for item in report["observations"]}
        assert findings["Glucose"]["suggested_model_feature"] == "Glucose"
        assert findings["HbA1c"]["suggested_model_feature"] is None
        # Simulate the user's reviewed correction before the normal prediction call.
        corrected_inputs = {**GOOD, "Glucose": 162, "BMI": 29.2,
                            "input_sources": {"Glucose": "report", "BMI": "report"}}
        prediction = client.post("/api/v1/predictions", json=corrected_inputs)
        assert prediction.status_code == 200, prediction.text
        result = prediction.json()
        assert result["model_version"]
        assert result["inputs"]["Glucose"] == 162
        assert result["inputs"]["BMI"] == 29.2
        assert result["input_sources"] == {"Glucose": "report", "BMI": "report"}
        assert result["label"] in (0, 1)
    finally:
        main.app.dependency_overrides.clear()


def test_prediction_uses_release_and_returns_shap():
    response = client.post("/api/v1/predictions", json=GOOD)
    assert response.status_code == 200, response.text
    result = response.json()
    assert result["model"] == "Logistic Regression"
    assert result["model_version"]
    assert set(result["all_models"]) == {"Logistic Regression", "Gaussian Naive Bayes", "Random Forest",
                                         "SVM (RBF)", "Gradient Boosting"}
    assert result["explanation"]["additivity_error"] < 1e-4


def test_prediction_validates_and_returns_input_provenance():
    response = client.post("/api/v1/predictions", json={**GOOD, "input_sources": {"Glucose": "report", "Age": "manual"}})
    assert response.status_code == 200
    assert response.json()["input_sources"] == {"Glucose": "report", "Age": "manual"}
    invalid = client.post("/api/v1/predictions", json={**GOOD, "input_sources": {"HbA1c": "report"}})
    assert invalid.status_code == 422


def test_out_of_domain_prediction_is_rejected():
    response = client.post("/api/v1/predictions", json={**GOOD, "Age": 19})
    assert response.status_code == 422


def test_body_limit_rejects_streamed_request_without_content_length():
    async def verify():
        async def chunks():
            yield b" " * 12_000
            yield b" " * 5_000
        transport = httpx.ASGITransport(app=main.app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as async_client:
            return await async_client.post(
                "/api/v1/reports/assessment",
                content=chunks(),
                headers={"content-type": "application/json"},
            )

    response = asyncio.run(verify())
    assert response.status_code == 413


def test_report_endpoint_returns_generated_html_without_storage():
    response = client.post("/api/v1/reports/assessment", json={"inputs": GOOD, "case_reference": "CASE-014"})
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "CASE-014" in response.text
    assert "not a medical device" in response.text.lower()


def test_sensitivity_endpoint_uses_training_quantile_bounds_and_all_models():
    response = client.post("/api/v1/sensitivity", json={"inputs": GOOD, "feature": "Glucose", "points": 5})
    assert response.status_code == 200, response.text
    curve = response.json()
    assert curve["range"] == [80.45, 180.54999999999995]
    assert len(curve["points"]) == 5
    assert set(curve["points"][0]["models"]) == {"Logistic Regression", "Gaussian Naive Bayes", "Random Forest",
                                                   "SVM (RBF)", "Gradient Boosting"}
    assert "not causal" in curve["disclaimer"].lower()


def test_evaluation_reports_selected_test_model_only_and_release_threshold():
    response = client.get("/api/v1/evaluation")
    assert response.status_code == 200
    result = response.json()
    from src.predict import load_artifacts
    art = load_artifacts()
    metrics = art.card["test_table"][0]
    assert result["current_run_test_used_for_selection"] is False
    assert result["historical_test_exposure"] is True
    assert result["independent_test_claim"] is False
    assert result["threshold"] == art.threshold
    assert [row["model"] for row in result["test"]] == [art.selected]
    assert result["test"][0]["threshold"] == art.threshold


def test_interactive_chart_points_match_the_loaded_release_and_saved_evaluation():
    response = client.get("/api/v1/evaluation/chart-data")
    assert response.status_code == 200
    result = response.json()
    from src.predict import load_artifacts
    art = load_artifacts()
    metrics = art.card["test_table"][0]
    assert result["available"] is True
    assert result["model_version"] == art.card["model_version"]
    assert result["model"] == art.selected
    assert result["roc_auc"] == metrics["roc_auc"]
    assert len(result["roc_points"]) > 2
    assert result["roc_points"][0]["false_positive_rate"] == 0
    assert result["roc_points"][-1]["false_positive_rate"] == 1
    assert result["confusion_matrix"]["actual_negative"] == {
        "predicted_negative": metrics["tn"], "predicted_positive": metrics["fp"]}
    assert result["confusion_matrix"]["actual_positive"] == {
        "predicted_negative": metrics["fn"], "predicted_positive": metrics["tp"]}
    assert result["confusion_matrix"]["sample_count"] == sum(metrics[key] for key in ("tn", "fp", "fn", "tp"))
    assert result["calibration_bins"] == art.card["calibration_bins"]
    assert {row["feature"] for row in result["shap_importance"]} == set(art.card["features"])
    assert "descriptive visualization only" in result["provenance"]


def test_interactive_chart_data_is_hidden_when_artifact_release_differs(tmp_path, monkeypatch):
    reports = tmp_path / "reports"
    reports.mkdir()
    (reports / "interactive_charts.json").write_text(json.dumps({
        "available": True, "model_version": "stale-release", "model": "Logistic Regression",
    }))
    monkeypatch.setattr(main, "ROOT", tmp_path)
    response = client.get("/api/v1/evaluation/chart-data")
    assert response.status_code == 200
    assert response.json() == {
        "available": False,
        "reason": "Interactive chart data do not match the loaded model release.",
    }


def test_in_memory_rate_window_has_a_fixed_limit():
    window = main.RateWindow()
    assert all(window.allow("ip", now=100.0 + i * .01) for i in range(30))
    assert window.allow("other-ip", now=100.0)
    assert not window.allow("ip", now=100.31)
    assert window.allow("ip", now=161.0)


def test_history_requires_explicit_consent():
    async def signed_in_user():
        return {"id": "authenticated-test-user"}
    main.app.dependency_overrides[main.current_user] = signed_in_user
    try:
        response = client.post("/api/v1/history", headers={"Authorization": "Bearer test"},
                               json={"consent": False, "inputs": GOOD})
        assert response.status_code == 400
        assert "consent" in response.json()["detail"].lower()
    finally:
        main.app.dependency_overrides.clear()


def test_history_does_not_accept_client_computed_score():
    async def signed_in_user():
        return {"id": "authenticated-test-user"}
    main.app.dependency_overrides[main.current_user] = signed_in_user
    try:
        response = client.post("/api/v1/history", headers={"Authorization": "Bearer test"},
                               json={"consent": True, "assessment": {"probability": .01, "label": 0}})
        assert response.status_code == 422
    finally:
        main.app.dependency_overrides.clear()


def test_rls_schema_scopes_reads_inserts_and_deletes_to_the_auth_user():
    schema = (main.ROOT / "backend" / "schema.sql").read_text(encoding="utf-8").lower()
    assert "enable row level security" in schema
    assert schema.count("(select auth.uid()) = user_id") >= 3
    assert "default auth.uid()" in schema


def test_star_cors_origins_are_rejected(monkeypatch):
    monkeypatch.setenv("CORS_ORIGINS", "*")
    import pytest
    with pytest.raises(RuntimeError, match="exact origins"):
        main.env_origins()
