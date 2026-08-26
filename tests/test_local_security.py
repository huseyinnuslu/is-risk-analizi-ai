from pathlib import Path

from fastapi.testclient import TestClient

from app.core.config import DATABASE_PATH, LOG_DIR, PROJECT_ROOT
from app.core.logging_config import configure_local_logging
from app.main import app


def test_runtime_data_and_logs_stay_inside_the_local_project():
    assert DATABASE_PATH.is_relative_to(PROJECT_ROOT)
    assert LOG_DIR.is_relative_to(PROJECT_ROOT)
    logger = configure_local_logging()
    file_handlers = [handler for handler in logger.handlers if hasattr(handler, "baseFilename")]
    assert file_handlers
    assert all(Path(handler.baseFilename).is_relative_to(PROJECT_ROOT) for handler in file_handlers)


def test_health_response_does_not_disclose_the_database_path():
    with TestClient(app) as client:
        response = client.get("/health")
    assert response.status_code == 200
    assert "database_path" not in response.json()
