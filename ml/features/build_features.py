"""Tahmin anında erişilebilir alanlardan model özellikleri üretir."""

from __future__ import annotations

import pandas as pd


# Bu alanlar sonuç bilgisidir. Model girdisine eklenmeleri yasaktır.
FORBIDDEN_FEATURES = {"completed_at", "is_delayed", "total_duration_days", "remaining_days"}

CATEGORICAL_FEATURES = [
    "process_type",
    "current_stage",
    "responsible_team",
    "priority",
]
NUMERIC_FEATURES = [
    "revision_count",
    "missing_document_count",
    "stage_change_count",
    "days_in_current_stage",
    "historical_avg_stage_days",
    "stage_delay_ratio",
    "team_workload",
    "days_since_created",
    "deadline_remaining_days",
    "revision_intensity",
    "missing_doc_flag",
    "stage_change_rate",
]
MODEL_FEATURES = CATEGORICAL_FEATURES + NUMERIC_FEATURES


def build_features(records: pd.DataFrame) -> pd.DataFrame:
    """Ham kayıtları modelin beklediği feature tablosuna dönüştürür.

    Tarih hesaplarının tamamı `as_of_date` üzerinden yapılır; bu nedenle
    gelecekteki tamamlanma tarihi hesaplamalara hiçbir şekilde karışmaz.
    """

    forbidden_present = FORBIDDEN_FEATURES.intersection(MODEL_FEATURES)
    if forbidden_present:
        raise RuntimeError(f"Leakage içeren feature tanımı: {forbidden_present}")

    frame = records.copy()
    created_at = pd.to_datetime(frame["created_at"])
    as_of_date = pd.to_datetime(frame["as_of_date"])
    deadline = pd.to_datetime(frame["deadline"])

    features = frame[CATEGORICAL_FEATURES + [
        "revision_count",
        "missing_document_count",
        "stage_change_count",
        "days_in_current_stage",
        "historical_avg_stage_days",
        "team_workload",
    ]].copy()
    features["days_since_created"] = (as_of_date - created_at).dt.days.clip(lower=0)
    features["deadline_remaining_days"] = (deadline - as_of_date).dt.days
    features["revision_intensity"] = features["revision_count"] / features[
        "days_since_created"
    ].clip(lower=1)
    features["missing_doc_flag"] = (features["missing_document_count"] > 0).astype(int)
    features["stage_delay_ratio"] = features["days_in_current_stage"] / features[
        "historical_avg_stage_days"
    ].clip(lower=0.1)
    features["stage_change_rate"] = features["stage_change_count"] / features[
        "days_since_created"
    ].clip(lower=1)
    return features[MODEL_FEATURES]


def build_remaining_days(records: pd.DataFrame) -> pd.Series:
    """Regresyon hedefini yalnız tamamlanmış eğitim kayıtlarında üretir."""

    completed_at = pd.to_datetime(records["completed_at"])
    as_of_date = pd.to_datetime(records["as_of_date"])
    remaining_days = (completed_at - as_of_date).dt.days
    if remaining_days.isna().any() or (remaining_days < 0).any():
        raise ValueError("Regresyon hedefinde geçersiz remaining_days bulundu.")
    return remaining_days.astype(float)
