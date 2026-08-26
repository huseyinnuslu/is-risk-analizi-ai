"""CSV verisini modele ve SQLite'a girmeden önce doğrulayan kurallar."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


REQUIRED_COLUMNS = {
    "external_id",
    "process_type",
    "current_stage",
    "responsible_team",
    "priority",
    "created_at",
    "as_of_date",
    "deadline",
    "revision_count",
    "missing_document_count",
    "stage_change_count",
    "days_in_current_stage",
    "historical_avg_stage_days",
    "team_workload",
    "status",
    "completed_at",
}

DATE_COLUMNS = ("created_at", "as_of_date", "deadline", "completed_at")
COUNT_COLUMNS = (
    "revision_count",
    "missing_document_count",
    "stage_change_count",
    "days_in_current_stage",
    "historical_avg_stage_days",
    "team_workload",
)


@dataclass
class ValidationResult:
    """Temiz satırlar ile reddedilen satırların özetini taşır."""

    valid_data: pd.DataFrame
    rejected_data: pd.DataFrame
    report: dict


def validate_process_dataframe(dataframe: pd.DataFrame) -> ValidationResult:
    """Süreç verisini doğrular ve hatalı satırları ayırır.

    Hatalı satırı sessizce düzeltmek yerine ayırıyoruz. Böylece kalite sorunu
    görünür kalır ve sonradan gerçek veri geldiğinde yanlış kayıt gizlenmez.
    """

    missing_columns = REQUIRED_COLUMNS.difference(dataframe.columns)
    if missing_columns:
        raise ValueError(
            "Eksik zorunlu kolonlar: " + ", ".join(sorted(missing_columns))
        )

    df = dataframe.copy()
    row_errors = pd.Series("", index=df.index, dtype="object")

    for column in DATE_COLUMNS:
        df[column] = pd.to_datetime(df[column], errors="coerce")

    for column in COUNT_COLUMNS:
        df[column] = pd.to_numeric(df[column], errors="coerce")

    for column in ("external_id", "process_type", "current_stage", "responsible_team", "priority"):
        empty = df[column].isna() | df[column].astype(str).str.strip().eq("")
        row_errors.loc[empty] += f"{column} boş; "

    invalid_status = ~df["status"].isin(["open", "completed"])
    row_errors.loc[invalid_status] += "status open veya completed olmalı; "

    for column in ("created_at", "as_of_date", "deadline"):
        row_errors.loc[df[column].isna()] += f"{column} geçersiz; "

    for column in COUNT_COLUMNS:
        invalid_number = df[column].isna() | (df[column] < 0)
        row_errors.loc[invalid_number] += f"{column} negatif/geçersiz; "
    row_errors.loc[df["historical_avg_stage_days"] <= 0] += (
        "historical_avg_stage_days sıfır olamaz; "
    )

    row_errors.loc[df["created_at"] > df["as_of_date"]] += "created_at as_of_date'den sonra; "
    row_errors.loc[df["deadline"] < df["created_at"]] += "deadline created_at'ten önce; "

    completed = df["status"].eq("completed")
    row_errors.loc[completed & df["completed_at"].isna()] += "completed_at eksik; "
    row_errors.loc[completed & (df["completed_at"] < df["as_of_date"])] += (
        "completed_at tahmin anından önce; "
    )
    row_errors.loc[completed & (df["completed_at"] < df["created_at"])] += (
        "completed_at created_at'ten önce; "
    )
    row_errors.loc[~completed & df["completed_at"].notna()] += (
        "open kayıtta completed_at dolu; "
    )

    duplicates = df["external_id"].duplicated(keep=False)
    row_errors.loc[duplicates] += "external_id tekrar ediyor; "

    rejected = df.loc[row_errors.ne("")].copy()
    if not rejected.empty:
        rejected["validation_errors"] = row_errors.loc[rejected.index].str.rstrip("; ")
    valid = df.loc[row_errors.eq("")].copy()

    # IQR kontrolü kayıt silmez. Aykırı değer, hata olmak zorunda değildir;
    # örneğin çok uzun süren karmaşık bir süreç gerçek ve önemli olabilir.
    outlier_counts: dict[str, int] = {}
    for column in COUNT_COLUMNS:
        values = df.loc[row_errors.eq(""), column].dropna()
        if len(values) < 4:
            outlier_counts[column] = 0
            continue
        q1, q3 = values.quantile([0.25, 0.75])
        iqr = q3 - q1
        lower_bound, upper_bound = q1 - 1.5 * iqr, q3 + 1.5 * iqr
        outlier_counts[column] = int(((values < lower_bound) | (values > upper_bound)).sum())

    report = {
        "source_rows": int(len(df)),
        "valid_rows": int(len(valid)),
        "rejected_rows": int(len(rejected)),
        "duplicate_rows": int(duplicates.sum()),
        "missing_values": {
            column: int(dataframe[column].isna().sum()) for column in dataframe.columns
        },
        "iqr_outlier_counts": outlier_counts,
        # Bir satır birden fazla sebeple reddedilebilir; bu nedenle toplamlar
        # rejected_rows ile birebir aynı olmak zorunda değildir.
        "rejection_reason_counts": {
            "Hatalı tarih veya zaman sırası": int(rejected.get("validation_errors", pd.Series(dtype=str)).str.contains(
                "geçersiz|tahmin anından önce|created_at'ten", regex=True, na=False
            ).sum()),
            "Geçersiz ya da negatif sayısal alan": int(rejected.get("validation_errors", pd.Series(dtype=str)).str.contains(
                "negatif/geçersiz|sıfır olamaz", regex=True, na=False
            ).sum()),
            "Eksik zorunlu metin alanı": int(rejected.get("validation_errors", pd.Series(dtype=str)).str.contains(
                "boş", regex=True, na=False
            ).sum()),
            "Geçersiz durum veya çelişkili tamamlanma bilgisi": int(rejected.get("validation_errors", pd.Series(dtype=str)).str.contains(
                "status open|completed_at eksik|open kayıtta", regex=True, na=False
            ).sum()),
            "Tekrarlı kayıt kimliği": int(rejected.get("validation_errors", pd.Series(dtype=str)).str.contains(
                "tekrar ediyor", regex=True, na=False
            ).sum()),
        },
    }
    return ValidationResult(valid_data=valid, rejected_data=rejected, report=report)
