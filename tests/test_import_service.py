import json

import pandas as pd

from app.services.import_service import import_dataframe


def test_import_dataframe_writes_valid_rows_and_rejects_invalid_rows(tmp_path):
    source = pd.DataFrame([
        {"external_id": "IMP-1", "process_type": "Belge", "current_stage": "İnceleme", "responsible_team": "Operasyon", "priority": "Orta", "created_at": "2026-01-01", "as_of_date": "2026-01-02", "deadline": "2026-01-10", "completed_at": "", "status": "open", "revision_count": 0, "missing_document_count": 0, "stage_change_count": 1, "days_in_current_stage": 1, "historical_avg_stage_days": 2, "team_workload": 4},
        {"external_id": "IMP-2", "process_type": "Belge", "current_stage": "İnceleme", "responsible_team": "Operasyon", "priority": "Orta", "created_at": "2026-01-03", "as_of_date": "2026-01-02", "deadline": "2026-01-10", "completed_at": "", "status": "open", "revision_count": 0, "missing_document_count": 0, "stage_change_count": 1, "days_in_current_stage": 1, "historical_avg_stage_days": 2, "team_workload": 4},
    ])
    report_path = tmp_path / "quality.json"
    report = import_dataframe(source, tmp_path / "local.db", report_path)
    assert report["imported_rows"] == 1
    assert report["rejected_rows"] == 1
    assert json.loads(report_path.read_text(encoding="utf-8"))["valid_rows"] == 1
