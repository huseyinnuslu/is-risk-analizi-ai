"""API testleri için gerçek proje verisinden bağımsız SQLite fixture'ı."""

from __future__ import annotations

import json
from pathlib import Path
import sqlite3

import pytest

from app.database.schema import initialise_database


@pytest.fixture(autouse=True)
def isolated_api_database(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Web/API katmanının gerçek `data/process_risk.db` dosyasına dokunmasını engeller."""
    database_path = tmp_path / "test_process_risk.db"
    initialise_database(database_path)

    artifact_dir = Path(__file__).resolve().parents[1] / "ml" / "artifacts"
    with sqlite3.connect(database_path) as connection:
        connection.execute(
            """INSERT INTO process_records (
                external_id, process_type, current_stage, responsible_team, priority,
                created_at, as_of_date, deadline, completed_at, status,
                revision_count, missing_document_count, stage_change_count,
                days_in_current_stage, historical_avg_stage_days, team_workload,
                is_delayed, total_duration_days
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            ("TEST-OPEN", "Belge", "İnceleme", "Operasyon", "Orta",
             "2026-08-01", "2026-08-10", "2026-08-20", None, "open",
             1, 0, 1, 2.0, 4.0, 25, None, None),
        )
        connection.execute(
            """INSERT INTO process_records (
                external_id, process_type, current_stage, responsible_team, priority,
                created_at, as_of_date, deadline, completed_at, status,
                revision_count, missing_document_count, stage_change_count,
                days_in_current_stage, historical_avg_stage_days, team_workload,
                is_delayed, total_duration_days
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            ("TEST-COMPLETED", "Belge", "İnceleme", "Operasyon", "Orta",
             "2026-01-01", "2026-01-05", "2026-01-12", "2026-01-10", "completed",
             0, 0, 1, 2.0, 4.0, 20, 0, 9.0),
        )
        for version, model_type, filename in (
            ("advanced-v1-classifier", "classification", "delay_classifier_advanced_v1.joblib"),
            ("advanced-v1-regressor", "regression", "duration_regressor_advanced_v1.joblib"),
        ):
            metrics = {"roc_auc": 0.78} if model_type == "classification" else {"mae": 6.7}
            connection.execute(
                """INSERT INTO model_registry
                (model_version, model_type, artifact_path, metrics_json, feature_list_json, is_active)
                VALUES (?, ?, ?, ?, ?, 1)""",
                (version, model_type, str(artifact_dir / filename), json.dumps(metrics), json.dumps([])),
            )

    import app.api.router as api_router
    import app.main as main_module
    import app.web.router as web_router

    monkeypatch.setattr(api_router, "DATABASE_PATH", database_path)
    monkeypatch.setattr(web_router, "DATABASE_PATH", database_path)
    monkeypatch.setattr(main_module, "DATABASE_PATH", database_path)
    yield database_path
