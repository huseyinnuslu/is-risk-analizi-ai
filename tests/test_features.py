import pandas as pd

from ml.features.build_features import FORBIDDEN_FEATURES, MODEL_FEATURES, build_features


def test_feature_table_never_contains_leakage_columns():
    records = pd.DataFrame([{
        "process_type": "Ödeme Başvurusu",
        "current_stage": "Uzman İnceleme",
        "responsible_team": "Operasyon",
        "priority": "Orta",
        "created_at": "2026-01-01",
        "as_of_date": "2026-01-10",
        "deadline": "2026-01-20",
        "revision_count": 2,
        "missing_document_count": 1,
        "stage_change_count": 3,
        "days_in_current_stage": 4,
        "historical_avg_stage_days": 2,
        "team_workload": 8,
        "completed_at": "2026-01-25",
        "is_delayed": 1,
        "total_duration_days": 24,
    }])
    features = build_features(records)
    assert list(features.columns) == MODEL_FEATURES
    assert FORBIDDEN_FEATURES.isdisjoint(features.columns)
    assert features.loc[0, "deadline_remaining_days"] == 10
    assert features.loc[0, "revision_intensity"] == 2 / 9
    assert features.loc[0, "stage_delay_ratio"] == 2
