"""Yerel sistem sağlığı ölçümlerinin SQLite kaydı."""

from __future__ import annotations

import json
from pathlib import Path

from app.database.connection import get_connection


def save_health_event(database_path: Path, snapshot: dict) -> int:
    with get_connection(database_path) as connection:
        cursor = connection.execute(
            """
            INSERT INTO system_health_events
            (cpu_percent, memory_percent, disk_percent, gpu_percent, status, alert_summary, snapshot_json)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                snapshot.get("cpu", {}).get("percent"),
                snapshot.get("memory", {}).get("percent"),
                snapshot.get("disk", {}).get("percent"),
                snapshot.get("gpu", {}).get("percent"),
                snapshot["status"], snapshot.get("alert_summary"),
                json.dumps(snapshot, ensure_ascii=False),
            ),
        )
    return int(cursor.lastrowid)


def list_health_events(database_path: Path, limit: int = 20) -> list[dict]:
    with get_connection(database_path) as connection:
        rows = connection.execute(
            "SELECT * FROM system_health_events ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
    events = [dict(row) for row in rows]
    for event in events:
        # Eski yerel veritabanlarında kalan SMTP alanını API'ye taşımayız.
        event.pop("email_status", None)
        event["snapshot"] = json.loads(event.pop("snapshot_json"))
    return events


def latest_health_event(database_path: Path) -> dict | None:
    events = list_health_events(database_path, limit=1)
    return events[0] if events else None
