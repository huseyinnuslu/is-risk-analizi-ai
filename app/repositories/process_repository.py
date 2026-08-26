"""Süreç, tahmin ve model kayıtları için SQLite sorguları."""

from __future__ import annotations

import json
from pathlib import Path

from app.database.connection import get_connection
from app.core.config import TEAM_CAPACITY


def get_process(database_path: Path, process_id: int) -> dict | None:
    with get_connection(database_path) as connection:
        row = connection.execute(
            "SELECT * FROM process_records WHERE id = ?", (process_id,)
        ).fetchone()
    return dict(row) if row else None


def list_processes(
    database_path: Path,
    status: str | None = "open",
    risk_level: str | None = None,
    deadline_status: str | None = None,
    limit: int = 100,
    offset: int = 0,
    process_type: str | None = None,
    current_stage: str | None = None,
    responsible_team: str | None = None,
) -> list[dict]:
    query = """
        SELECT p.*, pr.risk_score, pr.risk_level, pr.delay_probability,
               pr.predicted_remaining_days, pr.predicted_at,
               CASE WHEN pr.predicted_remaining_days IS NOT NULL THEN
                    DATE('now', '+' || CAST(pr.predicted_remaining_days + 0.999999 AS INTEGER) || ' days')
               END AS predicted_completion_date,
               CASE WHEN p.deadline < DATE('now') THEN 'overdue'
                    WHEN p.deadline <= DATE('now', '+1 day') THEN 'urgent'
                    ELSE 'within_deadline' END AS deadline_status,
               CAST(JULIANDAY(p.deadline) - JULIANDAY(DATE('now')) AS INTEGER) AS deadline_days_remaining
        FROM process_records p
        LEFT JOIN predictions pr ON pr.id = (
            SELECT id FROM predictions
            WHERE process_id = p.id
            ORDER BY predicted_at DESC, id DESC LIMIT 1
        )
        WHERE 1 = 1
    """
    parameters: list = []
    if status:
        query += " AND p.status = ?"
        parameters.append(status)
    if risk_level:
        query += " AND pr.risk_level = ?"
        parameters.append(risk_level)
    if deadline_status == "overdue":
        query += " AND p.deadline < DATE('now')"
    elif deadline_status == "actionable":
        query += " AND p.deadline >= DATE('now')"
    elif deadline_status == "urgent":
        query += " AND p.deadline >= DATE('now') AND p.deadline <= DATE('now', '+1 day')"
    elif deadline_status == "within_deadline":
        query += " AND p.deadline > DATE('now', '+1 day')"
    if process_type:
        query += " AND p.process_type = ?"
        parameters.append(process_type)
    if current_stage:
        query += " AND p.current_stage = ?"
        parameters.append(current_stage)
    if responsible_team:
        query += " AND p.responsible_team = ?"
        parameters.append(responsible_team)
    query += """
        ORDER BY
            CASE WHEN p.deadline < DATE('now') THEN 2
                 WHEN p.deadline <= DATE('now', '+1 day') THEN 0 ELSE 1 END,
            COALESCE(pr.risk_score, -1) DESC,
            p.deadline ASC
        LIMIT ? OFFSET ?
    """
    parameters.extend([limit, offset])
    with get_connection(database_path) as connection:
        rows = connection.execute(query, parameters).fetchall()
    return [dict(row) for row in rows]


def get_open_process_filter_options(database_path: Path) -> dict[str, list[str]]:
    """Açık iş listesindeki isteğe bağlı seçim kutularını yerel veriden doldurur."""
    fields = ("process_type", "current_stage", "responsible_team")
    with get_connection(database_path) as connection:
        return {
            field: [row[0] for row in connection.execute(
                f"SELECT DISTINCT {field} FROM process_records "
                "WHERE status = 'open' ORDER BY 1"
            ).fetchall()]
            for field in fields
        }


def get_prediction_history(database_path: Path, process_id: int) -> list[dict]:
    with get_connection(database_path) as connection:
        rows = connection.execute(
            "SELECT * FROM predictions WHERE process_id = ? ORDER BY predicted_at DESC, id DESC",
            (process_id,),
        ).fetchall()
    history = [dict(row) for row in rows]
    for item in history:
        item["explanation"] = json.loads(item.pop("explanation_json") or "{}")
    return history


def get_similar_completed_processes(database_path: Path, process: dict, limit: int = 5) -> list[dict]:
    """Tahmin tarihinden önce tamamlanmış, aynı türdeki en yakın işleri döndürür."""
    query = """
        SELECT external_id, current_stage, responsible_team, priority, deadline,
               completed_at, is_delayed, total_duration_days,
               CAST(JULIANDAY(completed_at) - JULIANDAY(deadline) AS INTEGER) AS deadline_difference_days,
               (CASE WHEN current_stage = ? THEN 0 ELSE 4 END
                + CASE WHEN responsible_team = ? THEN 0 ELSE 2 END
                + CASE WHEN priority = ? THEN 0 ELSE 1 END
                + ABS(revision_count - ?) * 0.6
                + ABS(missing_document_count - ?) * 0.8
                + ABS(days_in_current_stage - ?) * 0.3) AS similarity_distance
        FROM process_records
        WHERE status = 'completed' AND process_type = ?
          AND completed_at IS NOT NULL AND completed_at < ?
        ORDER BY similarity_distance ASC, completed_at DESC LIMIT ?
    """
    parameters = (
        process["current_stage"], process["responsible_team"], process["priority"],
        process["revision_count"], process["missing_document_count"],
        process["days_in_current_stage"], process["process_type"], process["as_of_date"], limit,
    )
    with get_connection(database_path) as connection:
        rows = connection.execute(query, parameters).fetchall()
    return [dict(row) for row in rows]


def get_current_team_workload(database_path: Path, team: str, current_date: str) -> int:
    """Tahmin gününde ekipteki açık iş sayısını tekrar hesaplar."""

    with get_connection(database_path) as connection:
        count = connection.execute(
            """
            SELECT COUNT(*) FROM process_records
            WHERE status = 'open' AND responsible_team = ? AND created_at <= ?
            """,
            (team, current_date),
        ).fetchone()[0]
    return min(100, round(int(count) / TEAM_CAPACITY * 100))


def save_prediction(database_path: Path, process_id: int, prediction: dict) -> int:
    with get_connection(database_path) as connection:
        cursor = connection.execute(
            """
            INSERT INTO predictions (
                process_id, model_version, delay_probability, risk_score, risk_level,
                predicted_remaining_days, explanation_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                process_id, prediction["model_version"], prediction["delay_probability"],
                prediction["risk_score"], prediction["risk_level"],
                prediction["predicted_remaining_days"],
                json.dumps(prediction["explanation"], ensure_ascii=False),
            ),
        )
        return int(cursor.lastrowid)


def save_predictions_batch(database_path: Path, predictions: list[tuple[int, dict]]) -> int:
    """Tahminleri tek SQLite işlemiyle kaydeder; toplu skorlama kilitlenmez."""
    values = [
        (
            process_id, prediction["model_version"], prediction["delay_probability"],
            prediction["risk_score"], prediction["risk_level"],
            prediction["predicted_remaining_days"],
            json.dumps(prediction["explanation"], ensure_ascii=False),
        )
        for process_id, prediction in predictions
    ]
    with get_connection(database_path) as connection:
        connection.executemany(
            """
            INSERT INTO predictions (
                process_id, model_version, delay_probability, risk_score, risk_level,
                predicted_remaining_days, explanation_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            values,
        )
    return len(values)


def get_active_models(database_path: Path) -> list[dict]:
    with get_connection(database_path) as connection:
        rows = connection.execute(
            "SELECT * FROM model_registry WHERE is_active = 1 ORDER BY model_type"
        ).fetchall()
    models = [dict(row) for row in rows]
    for model in models:
        model["metrics"] = json.loads(model.pop("metrics_json"))
        model["feature_list"] = json.loads(model.pop("feature_list_json"))
    return models


def get_drift_samples(database_path: Path, limit: int = 5_000) -> tuple[list[dict], list[dict]]:
    """Tamamlanmış eğitim bağlamı ile güncel açık işleri yerelden okur."""

    columns = "process_type, current_stage, responsible_team, priority, revision_count, missing_document_count, days_in_current_stage, team_workload"
    with get_connection(database_path) as connection:
        reference = connection.execute(
            f"SELECT {columns} FROM process_records WHERE status = 'completed' ORDER BY as_of_date DESC LIMIT ?",
            (limit,),
        ).fetchall()
        current = connection.execute(
            f"SELECT {columns} FROM process_records WHERE status = 'open' ORDER BY as_of_date DESC LIMIT ?",
            (limit,),
        ).fetchall()
    return [dict(row) for row in reference], [dict(row) for row in current]


def get_feedback_summary(database_path: Path) -> dict:
    """Kullanıcı geri bildirimlerini, model çıktısından ayrı bir izleme özeti olarak döndürür."""
    with get_connection(database_path) as connection:
        total = connection.execute("SELECT COUNT(*) FROM prediction_feedback").fetchone()[0]
        by_type = connection.execute(
            "SELECT feedback_type, COUNT(*) AS count FROM prediction_feedback GROUP BY feedback_type"
        ).fetchall()
        observed = connection.execute(
            """
            SELECT COUNT(actual_outcome) AS known_outcomes,
                   SUM(CASE WHEN actual_outcome = 1 THEN 1 ELSE 0 END) AS delayed_outcomes
            FROM prediction_feedback
            """
        ).fetchone()
        field_rows = connection.execute(
            """
            SELECT p.delay_probability, f.actual_outcome
            FROM prediction_feedback f
            INNER JOIN (
                SELECT prediction_id, MAX(id) AS latest_feedback_id
                FROM prediction_feedback
                WHERE actual_outcome IS NOT NULL
                GROUP BY prediction_id
            ) latest ON latest.latest_feedback_id = f.id
            INNER JOIN predictions p ON p.id = f.prediction_id
            """
        ).fetchall()
    outcomes = [(float(row["delay_probability"]) >= 0.5, int(row["actual_outcome"])) for row in field_rows]
    true_negative = sum(not predicted and not actual for predicted, actual in outcomes)
    false_positive = sum(predicted and not actual for predicted, actual in outcomes)
    false_negative = sum(not predicted and actual for predicted, actual in outcomes)
    true_positive = sum(predicted and actual for predicted, actual in outcomes)
    total = len(outcomes)
    precision = true_positive / (true_positive + false_positive) if true_positive + false_positive else None
    recall = true_positive / (true_positive + false_negative) if true_positive + false_negative else None
    f1 = 2 * precision * recall / (precision + recall) if precision is not None and recall is not None and precision + recall else None
    return {
        "total_feedback": total,
        "by_type": {row["feedback_type"]: row["count"] for row in by_type},
        "known_outcomes": observed["known_outcomes"],
        "delayed_outcomes": observed["delayed_outcomes"] or 0,
        "field_performance": {
            "sample_size": total,
            "threshold": 0.5,
            "accuracy": round((true_negative + true_positive) / total, 4) if total else None,
            "precision": round(precision, 4) if precision is not None else None,
            "recall": round(recall, 4) if recall is not None else None,
            "f1": round(f1, 4) if f1 is not None else None,
            "confusion_matrix": [[true_negative, false_positive], [false_negative, true_positive]],
        },
    }


def dashboard_summary(database_path: Path) -> dict:
    with get_connection(database_path) as connection:
        total_open = connection.execute(
            "SELECT COUNT(*) FROM process_records WHERE status = 'open'"
        ).fetchone()[0]
        prediction_stats = connection.execute(
            """
            SELECT
                COUNT(*) AS predicted_count,
                SUM(CASE WHEN risk_level = 'Yüksek' THEN 1 ELSE 0 END) AS high_risk_count,
                ROUND(AVG(risk_score), 1) AS average_risk
            FROM (
                SELECT pr.* FROM predictions pr
                INNER JOIN (
                    SELECT process_id, MAX(id) AS latest_id FROM predictions GROUP BY process_id
                ) latest ON latest.latest_id = pr.id
                INNER JOIN process_records p ON p.id = pr.process_id
                WHERE p.status = 'open'
            )
            """
        ).fetchone()
        deadline_stats = connection.execute(
            """
            SELECT
                SUM(CASE WHEN deadline < DATE('now') THEN 1 ELSE 0 END) AS overdue_count,
                SUM(CASE WHEN deadline >= DATE('now') AND deadline <= DATE('now', '+1 day') THEN 1 ELSE 0 END) AS urgent_count
            FROM process_records WHERE status = 'open'
            """
        ).fetchone()
        distribution = connection.execute(
            """
            SELECT process_type, COUNT(*) AS count
            FROM process_records WHERE status = 'open'
            GROUP BY process_type ORDER BY count DESC
            """
        ).fetchall()
        risk_distribution = connection.execute(
            """
            SELECT risk_level, COUNT(*) AS count
            FROM (
                SELECT pr.risk_level
                FROM predictions pr
                INNER JOIN (SELECT process_id, MAX(id) AS latest_id FROM predictions GROUP BY process_id) latest
                    ON latest.latest_id = pr.id
                INNER JOIN process_records p ON p.id = pr.process_id
                WHERE p.status = 'open'
            ) GROUP BY risk_level
            """
        ).fetchall()
    return {
        "total_open_processes": total_open,
        "predicted_open_processes": prediction_stats["predicted_count"],
        "high_risk_processes": prediction_stats["high_risk_count"] or 0,
        "average_risk_score": prediction_stats["average_risk"],
        "overdue_processes": deadline_stats["overdue_count"] or 0,
        "urgent_processes": deadline_stats["urgent_count"] or 0,
        "process_type_distribution": [dict(row) for row in distribution],
        "risk_distribution": [dict(row) for row in risk_distribution],
    }


def save_feedback(database_path: Path, feedback: dict) -> int:
    with get_connection(database_path) as connection:
        exists = connection.execute(
            "SELECT 1 FROM predictions WHERE id = ?", (feedback["prediction_id"],)
        ).fetchone()
        if not exists:
            raise ValueError("Tahmin kaydı bulunamadı.")
        cursor = connection.execute(
            """
            INSERT INTO prediction_feedback (prediction_id, feedback_type, comment, actual_outcome)
            VALUES (?, ?, ?, ?)
            """,
            (feedback["prediction_id"], feedback["feedback_type"], feedback.get("comment"), feedback.get("actual_outcome")),
        )
        return int(cursor.lastrowid)
