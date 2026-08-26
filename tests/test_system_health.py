from fastapi.testclient import TestClient

from app.main import app
from app.services.system_health_service import evaluate_status


def test_health_thresholds_are_classified_correctly():
    assert evaluate_status(25, 40, 60) == ("healthy", [])
    status, messages = evaluate_status(81, 40, 60)
    assert status == "warning"
    assert "CPU" in messages[0]
    status, messages = evaluate_status(20, 91, 60)
    assert status == "critical"
    assert "RAM" in messages[0]


def test_system_health_endpoints_return_local_measurements():
    with TestClient(app) as client:
        check = client.post("/api/system-health/check")
        overview = client.get("/api/system-health")
        page = client.get("/system-health")
    assert check.status_code == 200
    assert {"cpu", "memory", "disk", "gpu", "status"} <= check.json().keys()
    assert overview.status_code == 200
    assert overview.json()["history"]
    assert page.status_code == 200
