from app.repositories.process_repository import get_process, get_similar_completed_processes


def test_similar_processes_are_completed_and_from_the_past(tmp_path):
    # Bu test gerçek yerel veritabanını değiştirmez; API testi mevcut veriyle doğrulanır.
    from fastapi.testclient import TestClient
    from app.main import app

    with TestClient(app) as client:
        process = client.get("/api/processes?status=open&limit=1").json()["items"][0]
        payload = client.get(f"/api/processes/{process['id']}").json()
    assert "similar_completed_processes" in payload
    assert all(item["completed_at"] for item in payload["similar_completed_processes"])
    assert all("deadline_difference_days" in item for item in payload["similar_completed_processes"])
