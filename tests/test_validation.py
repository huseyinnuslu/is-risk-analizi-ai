import pandas as pd
import pytest

from app.core.validation import validate_process_dataframe


def valid_row() -> dict:
    return {
        "external_id": "TEST-001",
        "process_type": "Ödeme Başvurusu",
        "current_stage": "Ön Kontrol",
        "responsible_team": "Operasyon",
        "priority": "Orta",
        "created_at": "2026-01-01",
        "as_of_date": "2026-01-05",
        "deadline": "2026-01-20",
        "revision_count": 1,
        "missing_document_count": 0,
        "stage_change_count": 1,
        "days_in_current_stage": 2,
        "historical_avg_stage_days": 3.5,
        "team_workload": 6,
        "status": "completed",
        "completed_at": "2026-01-18",
    }


def test_valid_row_is_accepted():
    result = validate_process_dataframe(pd.DataFrame([valid_row()]))
    assert len(result.valid_data) == 1
    assert result.report["rejected_rows"] == 0


def test_completed_at_before_prediction_time_is_rejected():
    row = valid_row()
    row["completed_at"] = "2026-01-03"
    result = validate_process_dataframe(pd.DataFrame([row]))
    assert len(result.rejected_data) == 1
    assert "tahmin anından önce" in result.rejected_data.iloc[0]["validation_errors"]


def test_missing_required_column_raises_error():
    row = valid_row()
    del row["priority"]
    with pytest.raises(ValueError, match="priority"):
        validate_process_dataframe(pd.DataFrame([row]))


def test_iqr_outliers_are_reported_but_not_rejected():
    rows = []
    for index, revision_count in enumerate([0, 1, 1, 2, 100]):
        row = valid_row()
        row["external_id"] = f"TEST-{index}"
        row["revision_count"] = revision_count
        rows.append(row)
    result = validate_process_dataframe(pd.DataFrame(rows))
    assert len(result.valid_data) == 5
    assert result.report["iqr_outlier_counts"]["revision_count"] == 1
