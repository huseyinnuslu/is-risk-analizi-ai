"""Yerel CSV/XLSX dosyalarını doğrulayıp SQLite'a aktarma servisi."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pandas as pd

from app.core.validation import validate_process_dataframe
from app.database.schema import initialise_database


UPSERT_SQL = """
INSERT INTO process_records (
    external_id, process_type, current_stage, responsible_team, priority,
    created_at, as_of_date, deadline, completed_at, status,
    revision_count, missing_document_count, stage_change_count,
    days_in_current_stage, historical_avg_stage_days, team_workload,
    is_delayed, total_duration_days
) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
ON CONFLICT(external_id) DO UPDATE SET
    process_type=excluded.process_type, current_stage=excluded.current_stage,
    responsible_team=excluded.responsible_team, priority=excluded.priority,
    created_at=excluded.created_at, as_of_date=excluded.as_of_date,
    deadline=excluded.deadline, completed_at=excluded.completed_at,
    status=excluded.status, revision_count=excluded.revision_count,
    missing_document_count=excluded.missing_document_count,
    stage_change_count=excluded.stage_change_count,
    days_in_current_stage=excluded.days_in_current_stage,
    historical_avg_stage_days=excluded.historical_avg_stage_days,
    team_workload=excluded.team_workload, is_delayed=excluded.is_delayed,
    total_duration_days=excluded.total_duration_days, imported_at=CURRENT_TIMESTAMP
"""


def _iso(value: pd.Timestamp | pd.NaT) -> str | None:
    return None if pd.isna(value) else value.date().isoformat()


def import_dataframe(dataframe: pd.DataFrame, database_path: Path, report_path: Path) -> dict:
    """Geçerli satırları ekler, hatalı satırları atlar ve kalite özetini kaydeder."""
    validation = validate_process_dataframe(dataframe)
    prepared = validation.valid_data.copy()
    completed = prepared["status"].eq("completed")
    prepared["is_delayed"] = pd.NA
    prepared.loc[completed, "is_delayed"] = (
        prepared.loc[completed, "completed_at"] > prepared.loc[completed, "deadline"]
    ).astype(int)
    prepared["total_duration_days"] = pd.NA
    prepared.loc[completed, "total_duration_days"] = (
        prepared.loc[completed, "completed_at"] - prepared.loc[completed, "created_at"]
    ).dt.days.astype(float)

    values = [
        (row.external_id, row.process_type, row.current_stage, row.responsible_team,
         row.priority, _iso(row.created_at), _iso(row.as_of_date), _iso(row.deadline),
         _iso(row.completed_at), row.status, int(row.revision_count),
         int(row.missing_document_count), int(row.stage_change_count),
         float(row.days_in_current_stage), float(row.historical_avg_stage_days),
         int(row.team_workload), None if pd.isna(row.is_delayed) else int(row.is_delayed),
         None if pd.isna(row.total_duration_days) else float(row.total_duration_days))
        for row in prepared.itertuples(index=False)
    ]
    initialise_database(database_path)
    with sqlite3.connect(database_path) as connection:
        # Güncellenen sürecin eski tahmini artık o kaydın yeni alanlarını temsil etmez.
        # Tahmin geçmişini sessizce yanlış göstermemek için yalnız içe aktarılan
        # kayıtların eski tahminlerini kaldırırız; kullanıcı yeniden tahmin üretir.
        connection.executemany(
            "DELETE FROM predictions WHERE process_id IN (SELECT id FROM process_records WHERE external_id = ?)",
            [(row.external_id,) for row in prepared.itertuples(index=False)],
        )
        connection.executemany(UPSERT_SQL, values)

    report = validation.report | {
        "imported_rows": len(values), "completed_rows": int(completed.sum()),
        "open_rows": int((~completed).sum()),
        "delayed_completed_rows": int(prepared["is_delayed"].fillna(0).sum()),
    }
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report
