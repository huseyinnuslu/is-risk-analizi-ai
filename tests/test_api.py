from datetime import date
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.main import app


def test_health_endpoint():
    with TestClient(app) as client:
        response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_models_endpoint_returns_active_models():
    with TestClient(app) as client:
        response = client.get("/api/models/active")
    assert response.status_code == 200
    assert {item["model_type"] for item in response.json()["items"]} == {"classification", "regression"}


def test_dashboard_page_is_available():
    with TestClient(app) as client:
        response = client.get("/")
    assert response.status_code == 200
    assert "İŞTRisk" in response.text


def test_processes_reject_invalid_filter_value():
    with TestClient(app) as client:
        response = client.get("/api/processes?status=unknown")
    assert response.status_code == 422


def test_simulation_rejects_non_simulatable_field():
    with TestClient(app) as client:
        process_id = client.get("/api/processes?limit=1").json()["items"][0]["id"]
        response = client.post(
            "/api/simulate",
            json={"process_id": process_id, "overrides": {"completed_at": "2026-01-01"}},
        )
    assert response.status_code == 422
    assert response.json()["detail"][0]["type"] == "extra_forbidden"


def test_simulation_returns_same_day_baseline_for_fair_comparison():
    with TestClient(app) as client:
        process_id = client.get("/api/processes?limit=1").json()["items"][0]["id"]
        response = client.post(
            "/api/simulate",
            json={"process_id": process_id, "overrides": {"revision_count": 0}},
        )
    assert response.status_code == 200
    body = response.json()
    assert body["baseline"]["prediction_as_of_date"] == body["simulation"]["prediction_as_of_date"]


def test_batch_prediction_can_be_started_and_monitored():
    with TestClient(app) as client:
        response = client.post("/api/predictions/batch/start", json={"limit": 1})
        assert response.status_code == 202
        job_id = response.json()["job_id"]
        status = client.get(f"/api/predictions/batch/{job_id}/status")
    assert status.status_code == 200
    assert status.json()["status"] in {"queued", "running", "completed"}


def test_feedback_requires_existing_prediction():
    with TestClient(app) as client:
        response = client.post(
            "/api/feedback",
            json={"prediction_id": 999_999_999, "feedback_type": "useful"},
        )
    assert response.status_code == 404


def test_same_day_prediction_is_reused_without_duplicate_history():
    process = {"id": 7, "status": "open", "deadline": "2026-12-31"}
    latest = {
        "id": 42, "model_version": "advanced-v1-classifier",
        "predicted_at": f"{date.today().isoformat()}T08:00:00", "risk_score": 71,
        "risk_level": "Yüksek", "delay_probability": 0.71,
        "predicted_remaining_days": 4.0, "explanation": {},
    }
    with (
        patch("app.api.router.repository.get_process", return_value=process),
        patch("app.api.router.repository.get_prediction_history", return_value=[latest]),
        patch("app.api.router.repository.get_active_models", return_value=[]),
        patch(
            "app.api.router.active_artifact_paths",
            return_value=(Path("classifier.joblib"), Path("regressor.joblib"), "advanced-v1-classifier"),
        ),
        TestClient(app) as client,
    ):
        response = client.post("/api/predictions/7/run")
    assert response.status_code == 200
    assert response.json().get("reused_existing_prediction") is True
    assert response.json()["prediction_id"] == 42


def test_model_monitoring_has_field_performance_schema():
    with TestClient(app) as client:
        response = client.get("/api/models/monitoring")
    field_performance = response.json()["field_performance"]
    assert response.status_code == 200
    assert set(field_performance) == {
        "sample_size", "threshold", "accuracy", "precision", "recall", "f1", "confusion_matrix"
    }
