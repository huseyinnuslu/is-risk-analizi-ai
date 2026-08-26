"""Doğrulanmış süreç CSV'sini SQLite'a idempotent biçimde aktarır."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sqlite3
import sys

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

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
    process_type=excluded.process_type,
    current_stage=excluded.current_stage,
    responsible_team=excluded.responsible_team,
    priority=excluded.priority,
    created_at=excluded.created_at,
    as_of_date=excluded.as_of_date,
    deadline=excluded.deadline,
    completed_at=excluded.completed_at,
    status=excluded.status,
    revision_count=excluded.revision_count,
    missing_document_count=excluded.missing_document_count,
    stage_change_count=excluded.stage_change_count,
    days_in_current_stage=excluded.days_in_current_stage,
    historical_avg_stage_days=excluded.historical_avg_stage_days,
    team_workload=excluded.team_workload,
    is_delayed=excluded.is_delayed,
    total_duration_days=excluded.total_duration_days,
    imported_at=CURRENT_TIMESTAMP
"""


def _iso(value: pd.Timestamp | pd.NaT) -> str | None:
    return None if pd.isna(value) else value.date().isoformat()


def prepare_for_database(valid_data: pd.DataFrame) -> pd.DataFrame:
    """Hedefleri üretir; yasak sonuç alanlarını feature olarak kullanmaz."""

    prepared = valid_data.copy()
    completed = prepared["status"].eq("completed")
    prepared["is_delayed"] = pd.NA
    prepared.loc[completed, "is_delayed"] = (
        prepared.loc[completed, "completed_at"] > prepared.loc[completed, "deadline"]
    ).astype(int)
    prepared["total_duration_days"] = pd.NA
    prepared.loc[completed, "total_duration_days"] = (
        prepared.loc[completed, "completed_at"] - prepared.loc[completed, "created_at"]
    ).dt.days.astype(float)
    return prepared


def import_csv(csv_path: Path, database_path: Path, report_path: Path) -> dict:
    # Büyük CSV'lerde boş completed_at alanlarının tip çıkarımını kararlı tutar.
    source = pd.read_csv(csv_path, low_memory=False)
    validation = validate_process_dataframe(source)
    prepared = prepare_for_database(validation.valid_data)
    initialise_database(database_path)

    values = []
    for row in prepared.itertuples(index=False):
        values.append(
            (
                row.external_id, row.process_type, row.current_stage, row.responsible_team,
                row.priority, _iso(row.created_at), _iso(row.as_of_date), _iso(row.deadline),
                _iso(row.completed_at), row.status, int(row.revision_count),
                int(row.missing_document_count), int(row.stage_change_count),
                float(row.days_in_current_stage), float(row.historical_avg_stage_days),
                int(row.team_workload),
                None if pd.isna(row.is_delayed) else int(row.is_delayed),
                None if pd.isna(row.total_duration_days) else float(row.total_duration_days),
            )
        )

    with sqlite3.connect(database_path) as connection:
        # Yenilenen kayıtların eski tahminleri, yeni alanları temsil etmez.
        connection.executemany(
            "DELETE FROM predictions WHERE process_id IN (SELECT id FROM process_records WHERE external_id = ?)",
            [(row.external_id,) for row in prepared.itertuples(index=False)],
        )
        connection.executemany(UPSERT_SQL, values)

    report = validation.report | {
        "imported_rows": len(values),
        "completed_rows": int(prepared["status"].eq("completed").sum()),
        "open_rows": int(prepared["status"].eq("open").sum()),
        "delayed_completed_rows": int(prepared["is_delayed"].fillna(0).sum()),
    }
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Süreç CSV'sini SQLite'a aktarır.")
    parser.add_argument(
        "--input", type=Path,
        default=PROJECT_ROOT / "data" / "raw" / "synthetic_process_records.csv"
    )
    parser.add_argument(
        "--database", type=Path, default=PROJECT_ROOT / "data" / "process_risk.db"
    )
    parser.add_argument(
        "--report", type=Path,
        default=PROJECT_ROOT / "reports" / "generated" / "data_quality_report.json"
    )
    args = parser.parse_args()
    report = import_csv(args.input, args.database, args.report)
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
