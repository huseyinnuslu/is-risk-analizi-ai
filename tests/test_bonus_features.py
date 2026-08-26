from fastapi.testclient import TestClient

from app.main import app
from app.services.drift_service import drift_report, population_stability_index


def test_uncertainty_interval_is_returned_for_a_prediction():
    with TestClient(app) as client:
        process_id = client.get("/api/processes?limit=1").json()["items"][0]["id"]
        response = client.post(f"/api/predictions/{process_id}/run")
    assert response.status_code == 200
    interval = response.json()["remaining_days_uncertainty"]
    assert interval["lower_days"] >= 1
    assert interval["upper_days"] >= interval["lower_days"]
    assert interval["mae_days"] > 0


def test_filtered_process_list_can_be_exported_as_csv():
    with TestClient(app) as client:
        response = client.get("/api/processes/export.csv?status=open&deadline_status=actionable")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/csv")
    assert "İş ID" in response.text
    assert "attachment" in response.headers["content-disposition"]


def test_drift_report_identifies_a_material_distribution_change():
    reference = [{
        "process_type": "A", "current_stage": "İnceleme", "responsible_team": "Ekip 1", "priority": "Orta",
        "revision_count": 0, "missing_document_count": 0, "days_in_current_stage": 1, "team_workload": 20,
    }] * 20
    current = [{
        "process_type": "B", "current_stage": "Onay", "responsible_team": "Ekip 2", "priority": "Yüksek",
        "revision_count": 9, "missing_document_count": 8, "days_in_current_stage": 30, "team_workload": 95,
    }] * 20
    result = drift_report(reference, current)
    assert result["severity"] == "yüksek"
    assert population_stability_index([1, 1, 1], [1, 1, 1]) == 0.0


def test_model_drift_endpoint_is_available():
    with TestClient(app) as client:
        response = client.get("/api/models/data-drift")
    assert response.status_code == 200
    assert {"reference_count", "current_count", "severity", "fields"} <= response.json().keys()
