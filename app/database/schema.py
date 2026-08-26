"""SQLite şeması. Eğitimden önceki tüm alanlar açıkça tanımlanır."""

from __future__ import annotations

import sqlite3
from pathlib import Path


SCHEMA_SQL = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS process_records (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    external_id TEXT UNIQUE NOT NULL,
    process_type TEXT NOT NULL,
    current_stage TEXT NOT NULL,
    responsible_team TEXT NOT NULL,
    priority TEXT NOT NULL,
    created_at TEXT NOT NULL,
    as_of_date TEXT NOT NULL,
    deadline TEXT NOT NULL,
    completed_at TEXT,
    status TEXT NOT NULL CHECK (status IN ('open', 'completed')),
    revision_count INTEGER NOT NULL DEFAULT 0 CHECK (revision_count >= 0),
    missing_document_count INTEGER NOT NULL DEFAULT 0 CHECK (missing_document_count >= 0),
    stage_change_count INTEGER NOT NULL DEFAULT 0 CHECK (stage_change_count >= 0),
    days_in_current_stage REAL NOT NULL CHECK (days_in_current_stage >= 0),
    historical_avg_stage_days REAL NOT NULL CHECK (historical_avg_stage_days > 0),
    team_workload INTEGER NOT NULL DEFAULT 0 CHECK (team_workload >= 0),
    is_delayed INTEGER CHECK (is_delayed IN (0, 1)),
    total_duration_days REAL CHECK (total_duration_days >= 0),
    imported_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_process_records_status ON process_records(status);
CREATE INDEX IF NOT EXISTS idx_process_records_as_of_date ON process_records(as_of_date);

CREATE TABLE IF NOT EXISTS predictions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    process_id INTEGER NOT NULL,
    model_version TEXT NOT NULL,
    delay_probability REAL,
    risk_score INTEGER,
    risk_level TEXT,
    predicted_remaining_days REAL,
    explanation_json TEXT,
    predicted_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (process_id) REFERENCES process_records(id)
);

-- İş listesindeki en son tahmin araması bu alanla yapıldığı için indeks zorunludur.
-- Aksi hâlde binlerce tahmin olduğunda dashboard ve risk listesi yavaşlar.
CREATE INDEX IF NOT EXISTS idx_predictions_process_id ON predictions(process_id, id DESC);

CREATE TABLE IF NOT EXISTS model_registry (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    model_version TEXT UNIQUE NOT NULL,
    model_type TEXT NOT NULL,
    artifact_path TEXT NOT NULL,
    metrics_json TEXT NOT NULL,
    feature_list_json TEXT NOT NULL,
    trained_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    is_active INTEGER NOT NULL DEFAULT 0 CHECK (is_active IN (0, 1))
);

CREATE TABLE IF NOT EXISTS prediction_feedback (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    prediction_id INTEGER NOT NULL,
    feedback_type TEXT NOT NULL,
    comment TEXT,
    actual_outcome INTEGER CHECK (actual_outcome IN (0, 1)),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (prediction_id) REFERENCES predictions(id)
);

CREATE TABLE IF NOT EXISTS system_health_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    cpu_percent REAL,
    memory_percent REAL,
    disk_percent REAL,
    gpu_percent REAL,
    status TEXT NOT NULL,
    alert_summary TEXT,
    snapshot_json TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_system_health_events_created_at ON system_health_events(created_at DESC);
"""


def initialise_database(database_path: Path) -> None:
    """SQLite dosyasını ve tablolarını güvenle oluşturur."""

    database_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(database_path) as connection:
        connection.executescript(SCHEMA_SQL)
        # Eski yerel veritabanını silmeden, yeni kolonları geriye uyumlu ekleriz.
        existing = {row[1] for row in connection.execute("PRAGMA table_info(process_records)")}
        if "historical_avg_stage_days" not in existing:
            connection.execute(
                "ALTER TABLE process_records ADD COLUMN historical_avg_stage_days REAL NOT NULL DEFAULT 1"
            )
        if "team_workload" not in existing:
            connection.execute(
                "ALTER TABLE process_records ADD COLUMN team_workload INTEGER NOT NULL DEFAULT 0"
            )
